"""Sensitivity of the job 8 regressions to R-Judge: the same fits without its rows (CPU only).

R-Judge is near chance on clean traces and is not used for claims, but its targets are rows in the `seed_regressions.py`
fits (9, 19 and 18 of them). This refits per seed and pooled on InjecAgent + ToolEmu: Firth logistic, success ~
editable_frac + clean_margin + ToolEmu indicator, plus seed fixed effects and trace-clustered SEs when pooled, then
per seed with window count added (section 2's full model). The
editable-fraction unit stays the pooled SD of all rows (0.11), so odds ratios are comparable with job8_regressions.json;
clean margin is z-scored within seed on the remaining rows.
Output: results/aaai27/job8_regressions_no_rjudge.json, one line per fit on stdout.
"""
from __future__ import annotations

import json
from typing import Any

import numpy as np
from adv_lib import ROOT, Rebuilder
from seed_regressions import R, RNG_SEED, SEEDS, fit_block, load_rows, pooled_block

OUT = R / "job8_regressions_no_rjudge.json"
KW = {"sources": False, "extra": ("is_toolemu",)}


def line(name: str, block: dict) -> str:
    def fmt(c: dict) -> str:
        return f"{c['or']:.2f} [{c['ci95'][0]:.2f}, {c['ci95'][1]:.2f}] p={c['p']:.2g}"
    return f"{name} n={block['n']} succ={block['successes']} editable {fmt(block['coef']['editable_frac'])} margin {fmt(block['coef']['clean_margin'])}"


def main() -> None:
    all_rows = load_rows(Rebuilder(ROOT / "monitor" / "laya-monitor"))
    unit = float(np.array([r["editable_frac"] for r in all_rows]).std())
    rows = [{**r, "is_toolemu": float(r["source"] == "toolemu")} for r in all_rows if r["source"] != "r-judge"]
    rng = np.random.default_rng(RNG_SEED)
    res: dict[str, Any] = {"meta": {"editable_frac_unit_pooled_sd_all_rows": unit, "rows_dropped": len(all_rows) - len(rows)},
           "per_seed": {s: fit_block([r for r in rows if r["seed"] == s], unit, **KW) for s in SEEDS},
           "pooled": pooled_block(rows, unit, rng, **KW),
           "per_seed_with_windows": {s: fit_block([r for r in rows if r["seed"] == s], unit, sources=False,
                                                  extra=("is_toolemu", "n_windows")) for s in SEEDS}}
    OUT.write_text(json.dumps(res, indent=1))
    for s, b in res["per_seed"].items():
        print(line(f"seed {s}", b))
    print(line("pooled", res["pooled"]), "cluster boot", res["pooled"]["editable_or_cluster_boot_ci95"])
    for s, b in res["per_seed_with_windows"].items():
        w = b["coef"]["n_windows"]
        print(line(f"seed {s} with windows", b), f"windows {w['or']:.2f} [{w['ci95'][0]:.2f}, {w['ci95'][1]:.2f}] p={w['p']:.2g}")


if __name__ == "__main__":
    main()
