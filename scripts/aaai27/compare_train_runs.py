"""Compare two train_monitor.py runs for the resume test.

Usage: python compare_train_runs.py RUN_A RUN_B      (each RUN is a directory holding resume/best.pt,
                                                       work/train_log.jsonl, work/order_log.jsonl, calibration.json)
         Prints JSON: whether both runs saw the same batches in the same order (order_log.jsonl, written with
         --deterministic), each run's best-epoch val metrics (per-source AUROC and val loss, from train_log.jsonl at
         the calibration's best_epoch), and, for information only, max |dw| over the best weights.
       python compare_train_runs.py --gate OUT        reads OUT/cmp_A_{B,C,A2}.json; exits 0 only if each resumed run
         (B, C) (a) saw exactly A's batches in A's order and (b) has every best-epoch metric within the A vs A2
         spread: |X - A| <= |A2 - A|. Weight equality is not required. A missing comparison (the run crashed) fails.
         Prints RESUME_TEST PASS/FAIL.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import torch

SPREAD_EPS = 1e-12  # float slack only: "within the spread" is |X - A| <= |A2 - A| + SPREAD_EPS


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def load_order(run: Path) -> dict[int, list[int]]:
    """micro step -> item ids; a resumed run replays steps after its checkpoint, so the last record wins."""
    path = run / "work" / "order_log.jsonl"
    return {r["micro"]: r["ids"] for r in read_jsonl(path)} if path.exists() else {}


def best_metrics(run: Path) -> dict[str, float]:
    """Per-source val AUROC and val loss (nll) at the best epoch, i.e. the evaluation of the model the run keeps.
    A resumed run's log holds a row per epoch (rows after its checkpoint were truncated and replayed); the last
    row for an epoch wins."""
    best_ep = json.loads((run / "calibration.json").read_text())["best_epoch"]
    rows = {r["epoch"]: r["val"] for r in read_jsonl(run / "work" / "train_log.jsonl") if "val" in r}  # eval rows only
    val = rows[best_ep]
    return {k: v for k, v in val.items() if k.startswith("auroc_") or k == "nll"}


def weight_diff(a: Path, b: Path) -> float | None:
    if not ((a / "resume" / "best.pt").exists() and (b / "resume" / "best.pt").exists()):
        return None  # information only; the gate does not use it
    wa = torch.load(a / "resume" / "best.pt", map_location="cpu")
    wb = torch.load(b / "resume" / "best.pt", map_location="cpu")
    return max((wa[k].double() - wb[k].double()).abs().max().item() for k in wa if wa[k].is_floating_point())


def compare(a: Path, b: Path) -> dict:
    oa, ob = load_order(a), load_order(b)
    ca, cb = (json.loads((r / "calibration.json").read_text()) for r in (a, b))
    return {"order_steps": [len(oa), len(ob)], "order_identical": bool(oa) and oa == ob,
            "best_epoch": [ca["best_epoch"], cb["best_epoch"]],
            "metrics_a": best_metrics(a), "metrics_b": best_metrics(b),
            "max_abs_weight_diff_info_only": weight_diff(a, b)}


def check(x: dict, ref: dict) -> list[str]:
    """Reasons resumed run x fails the gate, given ref = the A vs A2 comparison (empty list = pass)."""
    bad = [] if x["order_identical"] else [f"batch order differs ({x['order_steps']} steps)"]
    for k, a in x["metrics_a"].items():
        spread = abs(ref["metrics_b"][k] - ref["metrics_a"][k])
        dev = abs(x["metrics_b"][k] - a)
        if dev > spread + SPREAD_EPS:
            bad.append(f"{k} off by {dev:.4g} > A-A2 spread {spread:.4g}")
    return bad


def gate(out: Path) -> None:
    ref = json.loads((out / "cmp_A_A2.json").read_text())
    fails = {}
    for x in ("B", "C"):
        path = out / f"cmp_A_{x}.json"
        text = path.read_text().strip() if path.exists() else ""
        fails[x] = check(json.loads(text), ref) if text else [f"no comparison: run {x} did not finish"]
    ok = not any(fails.values())
    spread = {k: round(abs(ref["metrics_b"][k] - v), 6) for k, v in ref["metrics_a"].items()}
    print(f"RESUME_TEST {'PASS' if ok else 'FAIL'} A-A2 spread={spread} A-A2 best_epoch={ref['best_epoch']} "
          + " ".join(f"{x}:{v or 'ok'}" for x, v in fails.items()))
    sys.exit(0 if ok else 1)


def main() -> None:
    if sys.argv[1] == "--gate":
        gate(Path(sys.argv[2]))
    print(json.dumps(compare(Path(sys.argv[1]), Path(sys.argv[2])), indent=1))


if __name__ == "__main__":
    main()
