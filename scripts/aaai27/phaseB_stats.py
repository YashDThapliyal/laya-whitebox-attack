"""Phase B statistics for analysis.md (CPU only): Wilson CIs, Fisher tests, and what masking leaves editable.

1. Job 6 attack table with 95% Wilson CIs, split into sources where the clean monitor works (InjecAgent, ToolEmu)
   and sources where it is near chance on clean traces in every view (R-Judge, SHADE).
2. Editable surface under masking: for the any-token attacks, the share of editable tokens and of the edits up to
   the "op" state that lie outside agent-prose blocks (those survive the mask and remove views).
3. Job 7 transfer table with 95% Wilson CIs, and a two-sided Fisher exact test of each val attack set's transfer
   rate against the random-edit control, per target checkpoint, with Holm adjustment across the sets tested on
   that checkpoint.
Inputs: job6_masking.json, job7_transfer.json, inputs/manifest.jsonl, attack/*.jsonl, data/*.jsonl.
Output: results/aaai27/phaseB_stats.json, markdown tables on stdout.
"""
from __future__ import annotations

import json
import math
import re
from collections import defaultdict

import numpy as np
from adv_lib import ROOT, Rebuilder, first_cross, load_calib, read_jsonl
from scipy.stats import fisher_exact

R = ROOT / "results" / "aaai27"
OUT = R / "phaseB_stats.json"
CONTEXT_TAGS = r"USER|AGENT PROFILE|AVAILABLE TOOLKITS"  # never editable (attack.py)
WORKS, NEAR_CHANCE = ("injecagent", "toolemu"), ("r-judge", "shade-arena")
JOB6_SETS = ("agent_u_val", "agent_c_val", "any_u_val", "any_c_val", "agent_u_shade80", "agent_c_shade80",
             "any_u_shade80", "any_c_shade80")
# Fisher tests vs the random control: the four val attacks at the operating point, and at p < 0.5 the same four,
# taking the unconstrained ones from their dedicated threshold-0.5 runs (the unconstrained runs to 0.865 reach
# p < 0.5 on only 8 and 21 targets, a biased subset). Holm-adjusted across these 8 tests per checkpoint.
FISHER_TESTS = ("agent_u_val|op", "agent_c_val|op", "any_u_val|op", "any_c_val|op",
                "agent_u_val_t05|half", "agent_c_val|half", "any_u_val_t05|half", "any_c_val|half")
TARGETS = ("zeroshot", "run1")


def wilson(k: int, n: int, z: float = 1.96) -> list[float] | None:
    if n == 0:
        return None
    p, d = k / n, 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(max(0.0, c - h), 3), round(min(1.0, c + h), 3)]


def cell(k: int, n: int) -> dict:
    return {"k": k, "n": n, "rate": k / n if n else None, "ci95": wilson(k, n)}


def fmt(c: dict) -> str:
    if not c["n"]:
        return "0 / 0"
    lo, hi = c["ci95"]
    return f"{c['k']} / {c['n']} [{100 * lo:.0f}, {100 * hi:.0f}]%"


# ---------- 1. job 6 attack table
def job6_table() -> dict:
    views = json.loads((R / "job6_masking.json").read_text())["views"]
    out: dict = {}
    for view in ("mask", "remove"):
        for s in JOB6_SETS:
            blk = views[view]["attack_recal_thr"].get(s)
            if not blk:
                continue
            groups = {"injecagent+toolemu": WORKS, "r-judge": ("r-judge",), "shade-arena": ("shade-arena",)}
            for g, srcs in groups.items():
                k = sum(blk[x]["flipped"] for x in srcs if x in blk)
                n = sum(blk[x]["clean_flagged"] for x in srcs if x in blk)
                if any(x in blk for x in srcs):
                    out.setdefault(s, {}).setdefault(g, {})[view] = cell(k, n)
    return out


# ---------- 2. editable surface under masking
def any_scope_editable(rb: Rebuilder, text: str, n_ids: int) -> np.ndarray:
    """Re-implements attack.py's --scope all mask: every token outside USER/profile/toolkit lines, with the
    shared window prefix frozen on multi-window traces."""
    offs = rb.tok(text.replace(rb.tok.mask_token, " "), add_special_tokens=False,
                  return_offsets_mapping=True)["offset_mapping"]
    spans = [(m.start(0), min(len(text), m.end(0) + 1))
             for m in re.finditer(rf"^\[({CONTEXT_TAGS})\] (.*)$", text, flags=re.MULTILINE)]
    ctx = np.zeros(n_ids, bool)
    for i, (a, b) in enumerate(offs):
        ctx[i] = any(s <= a and b <= e for s, e in spans)
    m = ~ctx
    if n_ids > rb.enc.budget:
        m[: 96] = False  # monitor_lib.PREFIX_TOKENS
    return m


def editable_surface(rb: Rebuilder) -> dict:
    states = {r["id"]: r for f in ("train_pool.jsonl", "eval_heldout.jsonl") for r in read_jsonl(ROOT / "data" / f)}
    z_op = load_calib(ROOT / "monitor" / "calibration.json").z_thr
    acc: dict = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    checked = mismatched = 0
    for set_name, stem in (("any_u_val", "val_all"), ("any_u_shade80", None)):
        rows = [r for r in read_jsonl(R / "inputs" / "manifest.jsonl")
                if r["kind"] == "adv" and r["set"] == set_name and r["point"] == "op" and r["view"] == "full"]
        recs = {}
        for r in rows:
            if r["file"] not in recs:
                recs[r["file"]] = {a["id"]: a for a in read_jsonl(ROOT / "attack" / f"{r['file']}.jsonl")}
            a, st = recs[r["file"]][r["id"]], states[r["id"]]
            text, src = st["state"], st["source"]
            sids = rb.state_ids(text)
            edit = any_scope_editable(rb, text, len(sids))
            checked += 1
            mismatched += int(edit.sum()) != a["n_editable"]
            outside = rb.token_block_ids(text, src) < 0
            k = first_cross(a["z_hist"], z_op)
            k = len(a["edits"]) if k is None else k
            pos = [e["pos"] for e in a["edits"][:k]]
            for key in (src, "all"):
                g = acc[set_name][key]
                g["editable_outside_share"].append(float((edit & outside).sum() / max(1, edit.sum())))
                g["edits"].append(len(pos))
                g["edits_outside"].append(sum(bool(outside[p]) for p in pos))
    out = {"n_editable_check": {"traces": checked, "mismatch_with_attack_record": mismatched}}
    for set_name, by_src in acc.items():
        for src, g in by_src.items():
            n_e, n_o = sum(g["edits"]), sum(g["edits_outside"])
            out.setdefault(set_name, {})[src] = {
                "traces": len(g["edits"]),
                "median_share_of_editable_tokens_outside_prose": float(np.median(g["editable_outside_share"])),
                "traces_with_nothing_editable_outside_prose": int(sum(x == 0 for x in g["editable_outside_share"])),
                "edits_to_op": n_e, "edits_outside_prose": n_o, "share_of_edits_outside_prose": n_o / n_e if n_e else None}
    return out


# ---------- 3. job 7 transfer table and Fisher tests
def holm(ps: list[float]) -> list[float]:
    order = sorted(range(len(ps)), key=lambda i: ps[i])
    adj, run = [0.0] * len(ps), 0.0
    for rank, i in enumerate(order):
        run = max(run, min(1.0, (len(ps) - rank) * ps[i]))
        adj[i] = run
    return adj


def job7_tables() -> dict:
    d = json.loads((R / "job7_transfer.json").read_text())
    ctrl = d["random_control"]
    out: dict = {"random_control": {m: cell(ctrl[m]["transfer"], ctrl[m]["clean_flagged"]) for m in ("run2", *TARGETS)},
                 "sets": {}, "fisher_vs_random": {}}
    for key, v in d["sets"].items():
        a = v["all"]
        out["sets"][key] = {m: cell(a[m]["transfer"], a[m]["clean_flagged"]) for m in ("run2", *TARGETS)}
    for m in TARGETS:
        k0, n0 = ctrl[m]["transfer"], ctrl[m]["clean_flagged"]
        tests = [t for t in FISHER_TESTS if t in out["sets"]]
        ps, odds = [], []
        for key in tests:
            c = out["sets"][key][m]
            res = fisher_exact([[c["k"], c["n"] - c["k"]], [k0, n0 - k0]], alternative="two-sided")
            odds.append(float(res.statistic))
            ps.append(float(res.pvalue))
        for key, o, p, ph in zip(tests, odds, ps, holm(ps)):
            out["fisher_vs_random"].setdefault(m, {})[key] = {"odds_ratio": o, "p": p, "p_holm": ph}
    return out


def main() -> None:
    rb = Rebuilder(ROOT / "monitor" / "laya-monitor")
    res = {"job6_attacks": job6_table(), "editable_surface": editable_surface(rb), "job7": job7_tables()}
    OUT.write_text(json.dumps(res, indent=1))
    print("## job 6")
    for s, groups in res["job6_attacks"].items():
        for g, views in groups.items():
            print(f"| {s} | {g} | " + " | ".join(fmt(views[v]) if v in views else "-" for v in ("mask", "remove")) + " |")
    print("## editable surface")
    print(json.dumps(res["editable_surface"], indent=1))
    print("## job 7")
    j7 = res["job7"]
    for key, c in j7["sets"].items():
        f = {m: j7["fisher_vs_random"].get(m, {}).get(key) for m in TARGETS}
        print(f"| {key} | {fmt(c['run2'])} | " + " | ".join(
            fmt(c[m]) + (f" p={f[m]['p']:.2g} (Holm {f[m]['p_holm']:.2g})" if f[m] else "") for m in TARGETS) + " |")
    print("| random | " + " | ".join(fmt(j7["random_control"][m]) for m in ("run2", *TARGETS)) + " |")
    print("## fisher tests run:", {m: len(v) for m, v in j7["fisher_vs_random"].items()})
    print(f"wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
