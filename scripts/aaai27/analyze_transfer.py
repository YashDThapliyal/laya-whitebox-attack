"""Job 7 analysis: do run-2 adversarial edits transfer to other checkpoints (zero-shot Laya, run 1)?

For every attacked target that flipped run 2 (crossed p = 0.865, "op" state), score clean and adversarial text
with each other checkpoint. Transfer = that checkpoint flags the clean trace at its own operating threshold and
does not flag the adversarial one. Also reported: the shift in calibrated logit (z / T) per checkpoint, and the
same shift for random-substitution edits (val_agent_random, full budget) as a control. "half" = the deeper
state that crossed p < 0.5 on run 2, where the attack ran that far.
Inputs: results/aaai27/inputs/manifest.jsonl, results/aaai27/job6/scores_run2.jsonl,
        results/aaai27/job7/scores_{zeroshot,run1}.jsonl
Output: results/aaai27/job7_transfer.json
"""
from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
R = ROOT / "results" / "aaai27"
CHECKPOINTS = {
    "run2": (R / "job6" / "scores_run2.jsonl", ROOT / "monitor" / "calibration.json"),
    "zeroshot": (R / "job7" / "scores_zeroshot.jsonl", ROOT / "monitor" / "zeroshot_calibration.json"),
    "run1": (R / "job7" / "scores_run1.jsonl", ROOT / "results" / "run1_model_v1" / "calibration_v1.json"),
}


def read_jsonl(p: Path) -> list[dict]:
    with p.open() as fh:
        return [json.loads(line) for line in fh if line.strip()]


def load_checkpoint(name: str) -> tuple[dict[str, float], float, float]:
    scores, calib = CHECKPOINTS[name]
    c = json.loads(calib.read_text())
    t, thr = float(c["temperature"]), float(c["threshold"])
    return {r["key"]: r["z_max"] for r in read_jsonl(scores)}, t, t * math.log(thr / (1 - thr))


def summarize(pairs: list[tuple[str, str]], z: dict[str, float], t: float, z_thr: float) -> dict:
    zc = np.array([z[c] for c, _ in pairs])
    za = np.array([z[a] for _, a in pairs])
    flagged = zc >= z_thr
    flipped = flagged & (za < z_thr)
    shift = (za - zc) / t
    return {"n": len(pairs), "clean_flagged": int(flagged.sum()), "transfer": int(flipped.sum()),
            "transfer_rate_of_flagged": float(flipped.sum() / flagged.sum()) if flagged.any() else None,
            "median_logit_shift": float(np.median(shift)) if len(pairs) else None,
            "frac_shift_down": float(np.mean(shift < 0)) if len(pairs) else None}


def main() -> None:
    rows = read_jsonl(R / "inputs" / "manifest.jsonl")
    models = {m: load_checkpoint(m) for m in CHECKPOINTS}
    by = defaultdict(dict)
    for r in rows:
        if r["kind"] == "adv" and r["view"] == "full":
            by[(r["set"], r["id"], r["source"])][r["point"]] = r
    random_rows = {r["id"]: r for r in rows if r["kind"] == "random"}
    clean_val = {r["id"]: r for r in rows if r["kind"] == "adv" and r["set"] == "agent_u_val"
                 and r["point"] == "clean" and r["view"] == "full"}
    out: dict = {"meta": {m: {"temperature": t, "z_thr": zt} for m, (_, t, zt) in models.items()}, "sets": {}}
    for point in ("op", "half"):
        groups = defaultdict(list)
        for (set_name, _, src), pts in by.items():
            a = pts.get(point)
            if a is None or not a["success_op"] or (point == "half" and not a["success_half"]):
                continue
            pair = (pts["clean"]["key"], a["key"])
            groups[(set_name, src)].append(pair)
            groups[(set_name, "all")].append(pair)
        for (set_name, src), pairs in sorted(groups.items()):
            out["sets"].setdefault(f"{set_name}|{point}", {})[src] = {
                m: summarize(pairs, z, t, zt) for m, (z, t, zt) in models.items()}
    ctrl = [(clean_val[i]["key"], r["key"]) for i, r in random_rows.items() if i in clean_val]
    out["random_control"] = {m: summarize(ctrl, z, t, zt) for m, (z, t, zt) in models.items()}
    (R / "job7_transfer.json").write_text(json.dumps(out, indent=1))
    for k, v in out["sets"].items():
        a = v["all"]
        print(f"{k:24s} n={a['run2']['n']:3d}  " + "  ".join(
            f"{m}: {a[m]['transfer']}/{a[m]['clean_flagged']} shift {a[m]['median_logit_shift']:+.2f}" for m in ("run2", "zeroshot", "run1")))
    print("random control:", {m: (v["transfer"], v["clean_flagged"], round(v["median_logit_shift"], 2)) for m, v in out["random_control"].items()})


if __name__ == "__main__":
    main()
