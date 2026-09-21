"""Phase 4.5: combine per-source monitor quality with per-source attack success into one table.

Inputs (synced from the VM into results/vm/): results_cross_source_auroc.json, attack_{val,mrt}_{agent,agent_random,all}.jsonl
Output: results/cross_source_table.json and a markdown table on stdout (pasted into cross_source_analysis.md).
"""
import json
import math
import os

import numpy as np

D = "results/vm"
BUD = [1, 3, 5, 10, 20]
SRC = ["injecagent", "toolemu", "r-judge", "shade-arena"]
NAME = {"injecagent": "InjecAgent", "toolemu": "ToolEmu", "r-judge": "R-Judge", "shade-arena": "SHADE-Arena (MRT)"}


def load(name):
    p = f"{D}/attack_{name}.jsonl"
    return [json.loads(l) for l in open(p)] if os.path.exists(p) else []


def src_of(r, mrt):
    return "shade-arena" if mrt else r["task"]


def wilson(k, n, z=1.96):
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0, c - h), min(1, c + h))


def succ(r, b):
    return min(r["z_hist"][: b + 1]) < r["z_thr"]


au = json.load(open(f"{D}/results_cross_source_auroc.json"))
runs = {k: (load(f"val_{k}"), load(f"mrt_{k}")) for k in ["agent", "agent_random", "all"]}
table = {}
for s in SRC:
    row = {"auroc_trained": au[s]["auroc_trained"], "ci_trained": au[s]["ci_trained"],
           "auroc_zeroshot": au[s]["auroc_zeroshot"], "ci_zeroshot": au[s]["ci_zeroshot"], "n_eval": au[s]["n"]}
    for k, (v, m) in runs.items():
        rows = [r for r in (m if s == "shade-arena" else v) if src_of(r, s == "shade-arena") == s]
        if not rows:
            continue
        n = len(rows)
        row[k] = {"n": n, "success": {b: sum(succ(r, b) for r in rows) / n for b in BUD},
                  "ci20": wilson(sum(succ(r, 20) for r in rows), n),
                  "retok_success20": sum(succ(r, 20) and r["success_retokenized"] for r in rows) / n,
                  "median_start_margin": float(np.median([r["z_hist"][0] - r["z_thr"] for r in rows])),
                  "median_start_p": float(np.median([r["p_hist"][0] for r in rows])),
                  "median_editable": float(np.median([r["n_editable"] for r in rows])),
                  "median_windows": float(np.median([r["n_windows"] for r in rows]))}
        if s == "shade-arena":
            row[k]["success_60"] = sum(min(r["z_hist"]) < r["z_thr"] for r in rows) / n
    table[s] = row
json.dump(table, open("results/cross_source_table.json", "w"), indent=1)


def f(x):
    return "–" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.2f}"


print("| Source | n eval | AUROC trained [95% CI] | AUROC zero-shot [95% CI] | attacked n | " +
      " | ".join(f"success @{b}" for b in BUD) + " | random @20 | any-token @20 | median start margin (logits) |")
print("|" + "---|" * (10 + len(BUD) - 1))
for s in SRC:
    r = table[s]
    a, rnd, al = r.get("agent"), r.get("agent_random"), r.get("all")
    cells = [NAME[s], str(r["n_eval"]),
             f"{r['auroc_trained']:.3f} [{r['ci_trained'][0]:.2f}, {r['ci_trained'][1]:.2f}]",
             f"{r['auroc_zeroshot']:.3f} [{r['ci_zeroshot'][0]:.2f}, {r['ci_zeroshot'][1]:.2f}]",
             str(a["n"]) if a else "0"]
    cells += [f(a["success"][b]) if a else "–" for b in BUD]
    cells += [f(rnd["success"][20]) if rnd else "–", f(al["success"][20]) if al else "–",
              f(a["median_start_margin"]) if a else "–"]
    print("| " + " | ".join(cells) + " |")
print()
for s in SRC:
    for k in ["agent", "agent_random", "all"]:
        if k in table[s]:
            x = table[s][k]
            print(f"{s:12s} {k:13s} n={x['n']:3d} succ={[round(x['success'][b], 2) for b in BUD]} ci20=({x['ci20'][0]:.2f},{x['ci20'][1]:.2f}) "
                  f"retok20={x['retok_success20']:.2f} start_p={x['median_start_p']:.3f} margin={x['median_start_margin']:.2f} "
                  f"edit={x['median_editable']:.0f} win={x['median_windows']:.0f}" + (f" s60={x['success_60']:.2f}" if 'success_60' in x else ""))
