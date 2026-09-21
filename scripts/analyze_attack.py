"""Phase 5: attack success vs budget, random baseline, retokenization check, qualitative examples.

Reads attack/*.jsonl (from attack.py) and writes attack/summary.json + attack/success_vs_budget.png.
attack_eval.md is written by hand from these numbers.
"""
import glob
import json
import os

import numpy as np

BUDGETS = [1, 3, 5, 10, 20, 40, 60]


def load(path):
    return [json.loads(l) for l in open(path)] if os.path.exists(path) else []


def success_at(r, b):
    h = r["z_hist"][: b + 1]
    return min(h) < r["z_thr"]


def summarize(rows, max_budget):
    if not rows:
        return None
    out = {"n": len(rows), "budgets": {}}
    for b in [b for b in BUDGETS if b <= max_budget]:
        out["budgets"][b] = float(np.mean([success_at(r, b) for r in rows]))
    out["success_any"] = float(np.mean([r["success"] for r in rows]))
    out["success_retokenized"] = float(np.mean([r["success"] and r["success_retokenized"] for r in rows]))
    ps = [r["p_hist"][0] for r in rows]
    pb = [min(r["p_hist"]) for r in rows]
    out["p_before_median"] = float(np.median(ps))
    out["p_best_median"] = float(np.median(pb))
    out["delta_p_median"] = float(np.median(np.array(ps) - np.array(pb)))
    succ = [r for r in rows if r["success"]]
    out["swaps_to_success_median"] = float(np.median([next(b for b in range(len(r["z_hist"])) if r["z_hist"][b] < r["z_thr"]) for r in succ])) if succ else None
    out["z_margin_above_thr_median"] = float(np.median([r["z_hist"][0] - r["z_thr"] for r in rows]))
    out["n_editable_median"] = float(np.median([r["n_editable"] for r in rows]))
    out["n_windows_median"] = float(np.median([r["n_windows"] for r in rows]))
    out["seconds_median"] = float(np.median([r["seconds"] for r in rows]))
    by = {}
    for r in rows:
        by.setdefault(r["task"], []).append(r)
    out["by_group"] = {k: {"n": len(v), "success": float(np.mean([x["success"] for x in v])),
                           "success@5": float(np.mean([success_at(x, 5) for x in v]))} for k, v in sorted(by.items())}
    return out


runs = {
    "val_agent": (load("attack/val_agent.jsonl"), 20),
    "val_agent_random": (load("attack/val_agent_random.jsonl"), 20),
    "val_all": (load("attack/val_all.jsonl"), 20),
    "mrt_agent": (load("attack/mrt_agent.jsonl"), 60),
    "mrt_agent_random": (load("attack/mrt_agent_random.jsonl"), 60),
    "mrt_all": (load("attack/mrt_all.jsonl"), 60),
}
summary = {k: summarize(rows, mb) for k, (rows, mb) in runs.items()}
json.dump(summary, open("attack/summary.json", "w"), indent=1)
print(json.dumps({k: {kk: vv for kk, vv in (v or {}).items() if kk != "by_group"} for k, v in summary.items()}, indent=1))

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    au = json.load(open("results/cross_source_auroc.json"))
    srcs = [("injecagent", "InjecAgent", False), ("toolemu", "ToolEmu", False), ("r-judge", "R-Judge", False), ("shade-arena", "SHADE-Arena (MRT)", True)]
    fig, axes = plt.subplots(1, 4, figsize=(17, 4), sharey=True)
    for ax, (key, title, mrt) in zip(axes, srcs):
        for k, style, lab in [("agent", "o-", "HotFlip, agent text"), ("agent_random", "s--", "random, agent text"), ("all", "^-", "HotFlip, any token")]:
            rows = [r for r in runs[f"{'mrt' if mrt else 'val'}_{k}"][0] if mrt or r["task"] == key]
            if not rows:
                continue
            xs = [b for b in BUDGETS if b <= (60 if mrt else 20)]
            ax.plot(xs, [np.mean([success_at(r, b) for r in rows]) for b in xs], style, label=f"{lab} (n={len(rows)})")
        ax.set_xscale("log"); ax.set_xlabel("token substitutions"); ax.grid(alpha=.3); ax.legend(fontsize=7)
        ax.set_title(f"{title}\nmonitor AUROC {au[key]['auroc_trained']:.2f}", fontsize=10); ax.set_ylim(-0.02, 1.02)
    axes[0].set_ylabel("attack success (flagged -> below threshold)")
    fig.tight_layout(); fig.savefig("attack/success_vs_budget.png", dpi=120)
except Exception as e:
    print("plot failed", e)

# qualitative picks
ex = {}
va = runs["val_agent"][0]
ex["val_fast_success"] = sorted([r for r in va if r["success"]], key=lambda r: (r["swaps_used"], -r["p_hist"][0]))[:4]
ex["val_fail_full_budget"] = sorted([r for r in va if not r["success"]], key=lambda r: -min(r["p_hist"]))[:3]
ma = runs["mrt_agent"][0]
ex["mrt_success"] = sorted([r for r in ma if r["success"]], key=lambda r: r["swaps_used"])[:3]
ex["mrt_fail"] = sorted([r for r in ma if not r["success"]], key=lambda r: -min(r["p_hist"]))[:3]
json.dump(ex, open("attack/qualitative_examples.json", "w"), indent=1)
