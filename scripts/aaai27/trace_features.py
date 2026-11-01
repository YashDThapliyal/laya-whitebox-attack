"""Per-trace feature table for the agent-text attacks (AAAI-27 Phase A).

One row per attacked trace: source, InjecAgent attack type, state length in tokens, editable tokens,
editable fraction, window count, clean-score margin over the operating threshold, and success at
budgets 20 / 60 for both bars (p < 0.865, p < 0.5). Reads existing attack/*.jsonl; writes only to
results/aaai27/.

Runs covered (agent-text scope, fine-tuned run 2):
  unconstrained: val_agent (117 in-distribution) + SHADE-80 = mrt_agent (original 20) + x_u_mrt_agent[3:]
                 (the first 3 rows of x_u_mrt_agent are p<0.5 reruns of original targets, see widen_analysis.py)
  constrained:   f_val_agent (117) + SHADE-80 = f_mrt_agent (20) + x_f_mrt_agent (60)

Editable fraction = n_editable / len(state token ids), matching scripts/attack.py (Trace.sids, Trace.edit).
Clean margin = z_hist[0] - z_thr(0.865), in the calibrated logit units the attack uses (z = T * logit(p)).
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import monitor_lib as ml

OUT = ROOT / "results" / "aaai27" / "trace_features.jsonl"
CALIB = json.loads((ROOT / "monitor" / "calibration.json").read_text())
Z_OP = CALIB["temperature"] * math.log(CALIB["threshold"] / (1 - CALIB["threshold"]))
Z_HALF = 0.0
N_SHADE_RERUNS = 3  # leading rows of x_u_mrt_agent that re-run original targets to p < 0.5

RUNS: dict[str, dict[str, list[tuple[str, int]]]] = {
    # attack -> set name -> list of (attack file stem, rows to skip at the start)
    "unconstrained": {"val": [("val_agent", 0)],
                      "shade20": [("mrt_agent", 0)],
                      "shade80": [("mrt_agent", 0), ("x_u_mrt_agent", N_SHADE_RERUNS)]},
    "constrained": {"val": [("f_val_agent", 0)],
                    "shade20": [("f_mrt_agent", 0)],
                    "shade80": [("f_mrt_agent", 0), ("x_f_mrt_agent", 0)]},
}


def read_jsonl(path: Path) -> list[dict]:
    with path.open() as fh:
        return [json.loads(line) for line in fh if line.strip()]


def load_states() -> dict[str, dict]:
    states = {}
    for name in ("train_pool.jsonl", "eval_heldout.jsonl"):
        for r in read_jsonl(ROOT / "data" / name):
            states[r["id"]] = {"state": r["state"], "source": r["source"]}
    return states


def succeeded(rec: dict, budget: int, z_bar: float) -> bool:
    return min(rec["z_hist"][: budget + 1]) < z_bar


def injecagent_type(trace_id: str) -> str | None:
    if not trace_id.startswith("injecagent_"):
        return None
    kind = trace_id.split("_")[1]
    return {"dh": "direct_harm", "ds": "data_stealing"}.get(kind, kind)


def feature_row(rec: dict, attack: str, set_name: str, states: dict, enc: ml.Encoder) -> dict:
    if rec["id"] not in states:
        raise KeyError(f"trace {rec['id']} not found in data/*.jsonl")
    info = states[rec["id"]]
    n_tokens = len(enc.state_ids(info["state"]))
    if n_tokens <= 0:
        raise ValueError(f"empty state for {rec['id']}")
    return {
        "id": rec["id"], "attack": attack, "set": set_name, "source": info["source"],
        "injecagent_type": injecagent_type(rec["id"]),
        "n_tokens": n_tokens, "n_editable": rec["n_editable"],
        "editable_frac": rec["n_editable"] / n_tokens, "n_windows": rec["n_windows"],
        "clean_margin": rec["z_hist"][0] - Z_OP, "start_p": rec["p_hist"][0],
        "budget_run": len(rec["z_hist"]) - 1,
        **{f"success_{b}_{tag}": succeeded(rec, b, zb)
           for b in (20, 60) for tag, zb in (("op", Z_OP), ("half", Z_HALF))},
        "success_retok_op": rec["z_retokenized"] < Z_OP,
    }


def main() -> None:
    enc = ml.Encoder(ml.load_tokenizer(str(ROOT / "monitor" / "laya-monitor")))
    states = load_states()
    rows = []
    for attack, sets in RUNS.items():
        for set_name, parts in sets.items():
            recs = [r for stem, skip in parts for r in read_jsonl(ROOT / "attack" / f"{stem}.jsonl")[skip:]]
            ids = [r["id"] for r in recs]
            if len(ids) != len(set(ids)):
                raise ValueError(f"duplicate ids in {attack}/{set_name}")
            rows.extend(feature_row(r, attack, set_name, states, enc) for r in recs)
            print(f"{attack:14s} {set_name:8s} n={len(recs)}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w") as fh:
        fh.writelines(json.dumps(r) + "\n" for r in rows)
    print(f"wrote {len(rows)} rows -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
