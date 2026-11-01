"""Shared CPU-side helpers for AAAI-27 Phase B: replay attack edits and build prose-masked views.

Adversarial traces are rebuilt by replaying each attack record's token substitutions on the original state
token ids (as scripts/edit_review.py does). Masked views remove or redact the agent's own prose using the
ORIGINAL trace's role structure, applied by token position. An attacker who edits tag tokens therefore can't
forge roles: a real defender would take roles from the agent API, not from the text.

Agent prose = blocks whose tag is AGENT, AGENT THOUGHT or AGENT FINAL ANSWER (plus AGENT ACTION for ToolEmu,
whose pseudo-traces narrate actions instead of calling tools). A block is a tagged line plus the untagged
continuation lines that follow it. This covers every token the agent-text attack could edit.
"""
from __future__ import annotations

import json
import math
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import monitor_lib as ml

AGENT_PROSE_TAGS = frozenset({"AGENT", "AGENT THOUGHT", "AGENT FINAL ANSWER"})
TAG_RE = re.compile(r"^\[([A-Z][A-Z ]*)\] ?")
VIEWS = ("full", "mask", "remove")


@dataclass(frozen=True)
class Calib:
    temperature: float
    threshold: float

    @property
    def z_thr(self) -> float:
        return self.temperature * math.log(self.threshold / (1 - self.threshold))


def load_calib(path: Path) -> Calib:
    c = json.loads(path.read_text())
    return Calib(float(c["temperature"]), float(c["threshold"]))


def read_jsonl(path: Path) -> list[dict]:
    with path.open() as fh:
        return [json.loads(line) for line in fh if line.strip()]


class Rebuilder:
    """Tokenizer-bound helpers: replay edits, compute agent-prose token masks, render views."""

    def __init__(self, model_dir: Path) -> None:
        self.tok = ml.load_tokenizer(str(model_dir))
        self.enc = ml.Encoder(self.tok)
        self.str2id: dict[str, int] = {}
        for i in range(len(self.tok)):
            self.str2id.setdefault(self.tok.decode([i]), i)
        self._placeholder: dict[str, list[int]] = {}

    def state_ids(self, text: str) -> list[int]:
        return list(self.enc.state_ids(text))

    def replay(self, text: str, edits: list[dict], k: int) -> list[int]:
        """Apply the first k edits to the state ids of text. Raises on any mismatch with the record."""
        sids = self.state_ids(text)
        for e in edits[:k]:
            if self.tok.decode([sids[e["pos"]]]) != e["from"]:
                raise ValueError(f"replay mismatch at pos {e['pos']}: {self.tok.decode([sids[e['pos']]])!r} != {e['from']!r}")
            if e["to"] not in self.str2id:
                raise ValueError(f"edit target {e['to']!r} not in vocab")
            sids[e["pos"]] = self.str2id[e["to"]]
        return sids

    def prose_blocks(self, text: str, source: str) -> list[tuple[int, int, str]]:
        """Char spans (start, end, tag) of agent-prose blocks in the original text."""
        tags = AGENT_PROSE_TAGS | ({"AGENT ACTION"} if source == "toolemu" else set())
        blocks, cur, pos = [], None, 0
        for line in text.splitlines(keepends=True):
            m = TAG_RE.match(line)
            if m:
                if cur is not None:
                    blocks.append(cur)
                cur = [pos, pos + len(line), m.group(1)]
            elif cur is not None:
                cur[1] = pos + len(line)
            pos += len(line)
        if cur is not None:
            blocks.append(cur)
        return [(a, b, t) for a, b, t in blocks if t in tags]

    def token_block_ids(self, text: str, source: str) -> np.ndarray:
        """Per state token: index of the agent-prose block it lies fully inside, else -1."""
        offs = self.tok(text.replace(self.tok.mask_token, " "), add_special_tokens=False,
                        return_offsets_mapping=True)["offset_mapping"]
        blocks = self.prose_blocks(text, source)  # sorted, non-overlapping
        out, j = np.full(len(offs), -1), 0
        for i, (s, e) in enumerate(offs):
            while j < len(blocks) and blocks[j][1] <= s:
                j += 1
            if j < len(blocks) and blocks[j][0] <= s and e <= blocks[j][1] and e > s:
                out[i] = j
        return out

    def placeholder(self, tag: str) -> list[int]:
        if tag not in self._placeholder:
            self._placeholder[tag] = self.state_ids(f"[{tag}] [withheld]\n")
        return self._placeholder[tag]

    def render(self, text: str, source: str, sids: list[int], view: str) -> str:
        """Decode sids (aligned to text's tokenization) under a view: full, mask (redact), remove."""
        if view == "full":
            return self.tok.decode(sids)
        block_of = self.token_block_ids(text, source)
        if len(block_of) != len(sids):
            raise ValueError("sids are not aligned with the original tokenization")
        tags = [t for _, _, t in self.prose_blocks(text, source)]
        out, last = [], -1
        for tid, b in zip(sids, block_of):
            if b < 0:
                out.append(tid)
                last = -1
            elif view == "mask" and b != last:
                out.extend(self.placeholder(tags[b]))
                last = b
            else:
                last = b
        return self.tok.decode(out)


def first_cross(z_hist: list[float], z_bar: float) -> int | None:
    """Index of the first path state below z_bar (number of edits applied), or None."""
    return next((i for i, z in enumerate(z_hist) if z < z_bar), None)


def best_index(z_hist: list[float]) -> int:
    return int(np.argmin(z_hist))
