"""Score texts with a Laya monitor checkpoint: windowed max margin, as everywhere else in this repo.

Runs on the GPU VM (also works on CPU/MPS for smoke tests). Input: texts.jsonl ({key, text}); optional
--keys file restricts which keys to score. Output: JSONL {key, z_max, z_top3, n_windows}, appended in
chunks and flushed, and resumable (keys already in --out are skipped), so a disconnect loses at most one chunk.
Margins are fp32 (TF32 matmuls) like the attack, so threshold crossings are comparable with the attack's.

Usage: python score_texts.py --model monitor/laya-monitor --texts texts.jsonl --out scores.jsonl [--keys k.txt] [--limit 5]
       --model base  loads the released zero-shot checkpoint from Hugging Face.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import monitor_lib as ml

CHUNK_TEXTS = 64


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--model", required=True, help="checkpoint dir, or 'base' for the zero-shot checkpoint")
    p.add_argument("--texts", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--keys", default=None)
    p.add_argument("--limit", type=int, default=0, help="smoke test: score only the first N pending texts")
    p.add_argument("--bs", type=int, default=64)
    return p.parse_args()


def pending_texts(args: argparse.Namespace) -> list[tuple[str, str]]:
    wanted = set(Path(args.keys).read_text().split()) if args.keys else None
    done = set()
    if Path(args.out).exists():
        with open(args.out) as fh:
            done = {json.loads(line)["key"] for line in fh if line.strip()}
    todo = []
    with open(args.texts) as fh:
        for line in fh:
            r = json.loads(line)
            if (wanted is None or r["key"] in wanted) and r["key"] not in done:
                todo.append((r["key"], r["text"]))
    if wanted is not None:
        missing = wanted - done - {k for k, _ in todo}
        if missing:
            raise SystemExit(f"{len(missing)} requested keys not found in {args.texts}")
    return todo[: args.limit] if args.limit else todo


def main() -> None:
    args = parse_args()
    ml.AMP = False  # fp32 with TF32 matmuls, exactly as scripts/attack.py
    torch.backends.cuda.matmul.allow_tf32 = True
    torch.backends.cudnn.allow_tf32 = True
    dev = ml.device()
    model_dir = ml.base_dir() if args.model == "base" else args.model
    model, _ = ml.load_model(model_dir, dev)
    tok = ml.load_tokenizer(model_dir)
    enc = ml.Encoder(tok)
    todo = pending_texts(args)
    print(f"device {dev}  model {args.model}  pending {len(todo)}", flush=True)
    t0, n_win = time.time(), 0
    with open(args.out, "a") as out:
        for c in range(0, len(todo), CHUNK_TEXTS):
            chunk = todo[c:c + CHUNK_TEXTS]
            items, owner = [], []
            for i, (_, text) in enumerate(chunk):
                wins, _ = enc.windows(enc.state_ids(text))
                items.extend(enc.item(w) for w in wins)
                owner.extend([i] * len(wins))
            zw, owner = ml.logits_for(model, items, tok.pad_token_id, dev, bs=args.bs), np.array(owner)
            for i, (key, _) in enumerate(chunk):
                z = np.sort(zw[owner == i])[::-1]
                out.write(json.dumps({"key": key, "z_max": float(z[0]), "z_top3": float(z[:3].mean()),
                                      "n_windows": int(z.size)}) + "\n")
            out.flush()
            n_win += len(items)
            el = time.time() - t0
            print(f"{c + len(chunk)}/{len(todo)} texts  {n_win} windows  {n_win / max(el, 1e-9):.1f} win/s  {el / 60:.1f} min", flush=True)
    print("done", flush=True)


if __name__ == "__main__":
    main()
