"""Build the texts scored on the GPU for Phase B jobs 6 (prose masking) and 7 (transfer).

Outputs (results/aaai27/inputs/):
  texts.jsonl     {key, text}: unique texts (key = sha1 prefix), so identical views are scored once
  manifest.jsonl  one row per (kind, set, trace, point, view) -> key
  keys_job7.txt   keys the transfer checkpoints (zero-shot, run 1) must score; run 2 scores every key

Kinds:
  clean_eval  every val trace (InjecAgent, ToolEmu, R-Judge) and every held-out SHADE trace, views full/mask/remove
  adv         attacked targets: point "clean" (original, decoded), "op" (first state below p = 0.865, else the
              path's best state), "half" (first state below p = 0.5, when reached); views full/mask/remove
              ("half" is full view only)
  random      random-substitution baseline: the final state after the full budget (full view only)
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from adv_lib import ROOT, VIEWS, Rebuilder, best_index, first_cross, load_calib, read_jsonl

OUT_DIR = ROOT / "results" / "aaai27" / "inputs"
N_SHADE_RERUNS = 3  # leading rows of x_u_mrt_agent re-run original targets (see widen_analysis.py)
SETS: dict[str, list[tuple[str, int]]] = {
    "agent_u_val": [("val_agent", 0)],
    "agent_u_val_t05": [("t05_val_agent", 0)],
    "agent_c_val": [("f_val_agent", 0)],
    "agent_u_shade80": [("mrt_agent", 0), ("x_u_mrt_agent", N_SHADE_RERUNS)],
    "agent_c_shade80": [("f_mrt_agent", 0), ("x_f_mrt_agent", 0)],
    "any_u_val": [("val_all", 0)],
    "any_u_val_t05": [("t05_val_all", 0)],
    "any_c_val": [("f_val_all", 0)],
    "any_u_shade80": [("mrt_all", 0), ("x_u_mrt_all", 0)],
    "any_c_shade80": [("f_mrt_all", 0), ("x_f_mrt_all", 0)],
}
RANDOM_SET = ("random_val", "val_agent_random")


class Store:
    def __init__(self) -> None:
        self.texts: dict[str, str] = {}
        self.rows: list[dict] = []
        self.job7: set[str] = set()

    def add(self, text: str, job7: bool, **meta) -> str:
        key = hashlib.sha1(text.encode()).hexdigest()[:16]
        prev = self.texts.setdefault(key, text)
        if prev != text:
            raise ValueError(f"sha1 prefix collision on {key}")
        self.rows.append({**meta, "key": key})
        if job7:
            self.job7.add(key)
        return key


def load_records() -> dict[str, dict]:
    recs = {}
    for name in ("train_pool.jsonl", "eval_heldout.jsonl"):
        for r in read_jsonl(ROOT / "data" / name):
            recs[r["id"]] = r
    return recs


def add_clean_eval(store: Store, rb: Rebuilder, recs: dict[str, dict]) -> None:
    pool = [r for r in recs.values() if r.get("split") == "val" or r["source"] == "shade-arena"]
    for r in pool:
        sids = rb.state_ids(r["state"])
        for view in VIEWS:
            text = r["state"] if view == "full" else rb.render(r["state"], r["source"], sids, view)
            store.add(text, False, kind="clean_eval", id=r["id"], source=r["source"], label=r["label"], view=view)


def add_attack_set(store: Store, rb: Rebuilder, recs: dict, set_name: str, parts: list, z_op: float) -> int:
    n_mask_equal = 0
    scope = set_name.split("_")[0]
    for stem, skip in parts:
        for a in read_jsonl(ROOT / "attack" / f"{stem}.jsonl")[skip:]:
            r = recs[a["id"]]
            base = {"kind": "adv", "set": set_name, "file": stem, "id": a["id"], "source": r["source"]}
            k_op = first_cross(a["z_hist"], z_op)
            k_half = first_cross(a["z_hist"], 0.0)
            points = {"clean": (0, VIEWS), "op": (k_op if k_op is not None else best_index(a["z_hist"]), VIEWS)}
            if k_half is not None:
                points["half"] = (k_half, ("full",))
            masked = {}
            for point, (k, views) in points.items():
                sids = rb.replay(r["state"], a["edits"], k)
                for view in views:
                    text = rb.render(r["state"], r["source"], sids, view)
                    store.add(text, view == "full", **base, point=point, k=k, success_op=k_op is not None,
                              success_half=k_half is not None, view=view)
                    masked[(point, view)] = text
            if scope == "agent":
                same = all(masked[("clean", v)] == masked[("op", v)] for v in ("mask", "remove"))
                if not same:
                    raise AssertionError(f"agent-scope edit survived masking: {set_name} {a['id']}")
                n_mask_equal += 1
    return n_mask_equal


def add_random(store: Store, rb: Rebuilder, recs: dict) -> None:
    set_name, stem = RANDOM_SET
    for a in read_jsonl(ROOT / "attack" / f"{stem}.jsonl"):
        r = recs[a["id"]]
        k = len(a["z_hist"]) - 1
        sids = rb.replay(r["state"], a["edits"], k)
        store.add(rb.render(r["state"], r["source"], sids, "full"), True, kind="random", set=set_name, file=stem,
                  id=a["id"], source=r["source"], point="random", k=k, view="full")


def main() -> None:
    rb = Rebuilder(ROOT / "monitor" / "laya-monitor")
    z_op = load_calib(ROOT / "monitor" / "calibration.json").z_thr
    recs = load_records()
    store = Store()
    add_clean_eval(store, rb, recs)
    print(f"clean_eval rows {len(store.rows)}", flush=True)
    for set_name, parts in SETS.items():
        n_eq = add_attack_set(store, rb, recs, set_name, parts, z_op)
        print(f"{set_name:18s} rows so far {len(store.rows)}  agent-scope masked==clean checked: {n_eq}", flush=True)
    add_random(store, rb, recs)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with (OUT_DIR / "texts.jsonl").open("w") as fh:
        fh.writelines(json.dumps({"key": k, "text": t}) + "\n" for k, t in store.texts.items())
    with (OUT_DIR / "manifest.jsonl").open("w") as fh:
        fh.writelines(json.dumps(r) + "\n" for r in store.rows)
    (OUT_DIR / "keys_job7.txt").write_text("\n".join(sorted(store.job7)) + "\n")
    print(f"rows {len(store.rows)}  unique texts {len(store.texts)}  job7 keys {len(store.job7)}")


if __name__ == "__main__":
    main()
