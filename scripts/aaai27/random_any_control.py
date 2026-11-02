"""Random any-token control for job 7: random substitutions over the any-token attack's editable set.

The job 7 control (val_agent_random) only edits agent text, a narrower surface than the any-token attack. This
control uses the any-token attack's editable set, budget and candidate vocabulary on the same 117 val targets:
`attack.py --scope all --random_baseline --budget 20` against run 2 (like val_agent_random, a path stops early once
it drops below run 2's bar). Its final states are scored by run 2, zero-shot Laya and run 1 (inference only).

  render RECORDS OUT [--model_dir DIR]   (on the VM) replay each record's edits, write {key, id, text} jsonl
  analyze                                (locally) transfer of the random states to each checkpoint, against
                                         the any-token attack's transfer, with Wilson CIs and Fisher tests
Inputs for analyze: results/aaai27/job8/out/rand_any/{val_all_random.jsonl, texts.jsonl, scores_*.jsonl},
job 6/7 clean scores. Output: results/aaai27/job7_random_any_control.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from adv_lib import ROOT, Rebuilder, read_jsonl
from scipy.stats import fisher_exact

R = ROOT / "results" / "aaai27"
RA = R / "job8" / "out" / "rand_any"
SCORE_FILES = {"run2": "scores_laya-monitor.jsonl", "zeroshot": "scores_base.jsonl", "run1": "scores_run1.jsonl"}
CALIBS = {"run2": ROOT / "monitor" / "calibration.json", "zeroshot": ROOT / "monitor" / "zeroshot_calibration.json",
          "run1": ROOT / "results" / "run1_model_v1" / "calibration_v1.json"}
CLEAN_SCORES = {"run2": R / "job6" / "scores_run2.jsonl", "zeroshot": R / "job7" / "scores_zeroshot.jsonl",
                "run1": R / "job7" / "scores_run1.jsonl"}


def text_key(text: str) -> str:
    return hashlib.sha1(text.encode()).hexdigest()[:16]


def render(records: Path, out: Path, model_dir: Path) -> None:
    rb = Rebuilder(model_dir)
    states = {r["id"]: r for r in read_jsonl(ROOT / "data" / "train_pool.jsonl")}
    rows = []
    for a in read_jsonl(records):
        st = states[a["id"]]
        sids = rb.replay(st["state"], a["edits"], len(a["edits"]))
        text = rb.render(st["state"], st["source"], sids, "full")
        rows.append({"key": text_key(text), "id": a["id"], "source": st["source"], "edits": len(a["edits"]), "text": text})
    out.write_text("".join(json.dumps(r) + "\n" for r in rows))
    print(f"rendered {len(rows)} random any-token states to {out}")


def z_thr(path: Path) -> float:
    c = json.loads(path.read_text())
    t, thr = float(c["temperature"]), float(c["threshold"])
    return t * math.log(thr / (1 - thr))


def wilson(k: int, n: int, z: float = 1.96) -> list[float] | None:
    if n == 0:
        return None
    p, d = k / n, 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(max(0.0, c - h), 3), round(min(1.0, c + h), 3)]


def analyze() -> None:
    manifest = read_jsonl(R / "inputs" / "manifest.jsonl")
    clean_key = {r["id"]: r["key"] for r in manifest
                 if r["kind"] == "adv" and r["set"] == "any_u_val" and r["point"] == "clean" and r["view"] == "full"}
    rnd = {r["id"]: r["key"] for r in read_jsonl(RA / "texts.jsonl")}
    stats = json.loads((R / "phaseB_stats.json").read_text())["job7"]
    out = {}
    for m, fname in SCORE_FILES.items():
        zr = {r["key"]: r["z_max"] for r in read_jsonl(RA / fname)}
        zc = {r["key"]: r["z_max"] for r in read_jsonl(CLEAN_SCORES[m])}
        thr = z_thr(CALIBS[m])
        ids = [i for i in rnd if i in clean_key]
        flagged = [i for i in ids if zc[clean_key[i]] >= thr]
        k = sum(zr[rnd[i]] < thr for i in flagged)
        attack = stats["sets"]["any_u_val|op"][m]
        res = fisher_exact([[attack["k"], attack["n"] - attack["k"]], [k, len(flagged) - k]])
        out[m] = {"random_any": {"k": k, "n": len(flagged), "ci95": wilson(k, len(flagged))},
                  "any_token_attack": {"k": attack["k"], "n": attack["n"], "ci95": attack["ci95"]},
                  "fisher_attack_vs_random_any": {"odds_ratio": float(res.statistic), "p": float(res.pvalue)}}
    (R / "job7_random_any_control.json").write_text(json.dumps(out, indent=1))
    for m, v in out.items():
        print(m, v)


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("render")
    r.add_argument("records", type=Path)
    r.add_argument("out", type=Path)
    r.add_argument("--model_dir", type=Path, default=ROOT / "monitor" / "laya-monitor")
    sub.add_parser("analyze")
    a = ap.parse_args()
    if a.cmd == "render":
        render(a.records, a.out, a.model_dir)
    else:
        analyze()


if __name__ == "__main__":
    main()
