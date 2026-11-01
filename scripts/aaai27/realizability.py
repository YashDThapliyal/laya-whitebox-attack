"""Are the attack's successes realizable as text? The attack edits token ids; an agent writes text.

For every attacked target and its first successful state (first z below the p = 0.865 bar, the "op" point of
build_score_inputs.py), decode the edited ids to text, re-tokenize, and rescore (job 6 run-2 scores, TF32 like the
attack). A success is text-realizable when the re-tokenized text is still below the bar. Reported per set and source:
recorded successes, successes whose text round-trips to the same ids, and text-realizable successes. Only the first
crossing is checked, so the realizable count is a lower bound (a later state on the path might survive).

Output: results/aaai27/job6_realizability.json
"""
from __future__ import annotations

import json
from collections import defaultdict

from adv_lib import ROOT, Rebuilder, load_calib, read_jsonl

MANIFEST = ROOT / "results" / "aaai27" / "inputs" / "manifest.jsonl"
SCORES = ROOT / "results" / "aaai27" / "job6" / "scores_run2.jsonl"
OUT = ROOT / "results" / "aaai27" / "job6_realizability.json"


def load_states() -> dict[str, dict]:
    return {r["id"]: r for name in ("train_pool.jsonl", "eval_heldout.jsonl") for r in read_jsonl(ROOT / "data" / name)}


def main() -> None:
    rb = Rebuilder(ROOT / "monitor" / "laya-monitor")
    z_op = load_calib(ROOT / "monitor" / "calibration.json").z_thr
    z = {r["key"]: r["z_max"] for r in read_jsonl(SCORES)}
    states = load_states()
    attacks: dict[str, dict[str, dict]] = {}
    counts: dict[tuple[str, str], dict[str, int]] = defaultdict(lambda: defaultdict(int))
    clean_dz = []
    for r in read_jsonl(MANIFEST):
        if r["kind"] != "adv" or r["view"] != "full" or r["point"] not in ("clean", "op"):
            continue
        if r["file"] not in attacks:
            attacks[r["file"]] = {a["id"]: a for a in read_jsonl(ROOT / "attack" / f"{r['file']}.jsonl")}
        a = attacks[r["file"]][r["id"]]
        if r["point"] == "clean":
            clean_dz.append(abs(z[r["key"]] - a["z_hist"][0]))
            continue
        for src in (r["source"], "all"):
            c = counts[(r["set"], src)]
            c["n"] += 1
            if not r["success_op"]:
                continue
            c["recorded"] += 1
            src_state = states[r["id"]]
            sids = rb.replay(src_state["state"], a["edits"], r["k"])
            text = rb.render(src_state["state"], src_state["source"], sids, "full")
            c["roundtrip_same_ids"] += list(rb.state_ids(text)) == list(sids)
            c["text_realizable"] += z[r["key"]] < z_op
    out = {"meta": {"z_op": z_op, "clean_points_max_abs_dz": max(clean_dz), "n_clean_points": len(clean_dz),
                    "note": "clean points rescore to the attack's recorded margin, so any gap at 'op' is re-tokenization"},
           "sets": {f"{s}|{src}": dict(c) for (s, src), c in sorted(counts.items())}}
    OUT.write_text(json.dumps(out, indent=1))
    for k, c in out["sets"].items():
        print(f"{k:32s} n={c['n']:3d} recorded={c.get('recorded', 0):3d} same_ids={c.get('roundtrip_same_ids', 0):3d} "
              f"realizable={c.get('text_realizable', 0):3d}")
    print(f"clean points: max |rescored - recorded| = {out['meta']['clean_points_max_abs_dz']:.4f}")


if __name__ == "__main__":
    main()
