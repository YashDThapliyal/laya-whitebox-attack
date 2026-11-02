"""Do the section 2 regressions hold on seeds 1 and 2? Fits at the common bar p < 0.5 (CPU only).

Data: agent-text unconstrained attack, budget 20, val targets (InjecAgent, ToolEmu, R-Judge). Seed 0 = run 2's
threshold-0.5 run (t05_val_agent); seeds 1 and 2 = job 8 (results/aaai27/job8/out/seed{1,2}/attack/val_agent.jsonl).
Seeds 1 and 2 were not attacked on SHADE, so no fit here includes SHADE-80.

Outcome: the max-window score drops below p = 0.5 (z < 0) within 20 swaps, among targets with clean z >= 0.
Predictors:
  editable_frac  editable tokens / state tokens; scaled by one SD of the pooled rows, the same unit in every fit
  clean_margin   clean z minus the bar, in the attack's logit units (z = T logit p), so here simply clean z;
                 z-scored within seed, since temperature and score scale differ by seed
Models:
  per seed       Firth logistic: success ~ editable_frac + clean_margin + source FE. Wald CIs as in section 2, plus a
                 percentile bootstrap resampling traces within source
  pooled         the same plus seed FE. Firth estimate with a cluster-robust sandwich by trace (primary); ML logit
                 with clustered SEs and a trace-cluster bootstrap of the Firth fit as checks; a Wald test of
                 editable_frac x seed for slope differences
  InjecAgent     per seed and pooled: success ~ editable_frac + clean_margin, then adding the data-stealing indicator
                 (editable fraction is tied to direct harm vs data stealing, so this is the confound check)
Sensitivities: adding window count (section 2's full model); restricting seeds 1 and 2 to clean p >= 0.865 on their
own scale (run 2's t05 run only attacked traces it flags at 0.865). Bridge: from section 2's published fit to the seed
0 fit, one change at a time.
Output: results/aaai27/job8_regressions.json, tables on stdout.
"""
from __future__ import annotations

import json
import math
from collections.abc import Callable
from pathlib import Path

import numpy as np
import statsmodels.api as sm
from adv_lib import ROOT, Rebuilder, read_jsonl
from scipy.stats import chi2
from structure_stats import firth

R = ROOT / "results" / "aaai27"
OUT = R / "job8_regressions.json"
SEEDS = (0, 1, 2)
BUDGET = 20
N_BOOT = 2000
N_BOOT_CLUSTER = 1000
RNG_SEED = 0


def seed_file(seed: int) -> Path:
    return ROOT / "attack" / "t05_val_agent.jsonl" if seed == 0 else R / "job8" / "out" / f"seed{seed}" / "attack" / "val_agent.jsonl"


def temperature(seed: int) -> float:
    path = ROOT / "monitor" / "calibration.json" if seed == 0 else R / "job8" / "monitor" / f"seed{seed}" / "calibration.json"
    return float(json.loads(path.read_text())["temperature"])


def load_rows(rb: Rebuilder) -> list[dict]:
    states = {r["id"]: r["state"] for r in read_jsonl(ROOT / "data" / "train_pool.jsonl")}
    n_tok: dict[str, int] = {}
    rows = []
    for seed in SEEDS:
        z865 = temperature(seed) * math.log(0.865 / 0.135)
        for a in read_jsonl(seed_file(seed)):
            z0 = a["z_hist"][0]
            if z0 < 0:  # seed 1 attacked down to 0.368, so a few targets start below the common bar
                continue
            n_tok.setdefault(a["id"], len(rb.state_ids(states[a["id"]])))
            rows.append({"seed": seed, "id": a["id"], "source": a["task"], "y": float(min(a["z_hist"][: BUDGET + 1]) < 0),
                         "editable_frac": a["n_editable"] / n_tok[a["id"]], "n_editable": a["n_editable"],
                         "margin": z0, "n_windows": a["n_windows"], "at_865": z0 >= z865,
                         "data_stealing": float("_ds_" in a["id"])})
    return rows


def check_features(rows: list[dict]) -> dict:
    """editable_frac must equal section 2's feature table on the traces both cover, and not vary by seed."""
    table = {r["id"]: r for r in read_jsonl(R / "trace_features.jsonl") if r["attack"] == "unconstrained" and r["set"] == "val"}
    worst = max(abs(r["editable_frac"] - table[r["id"]]["editable_frac"]) for r in rows if r["id"] in table)
    by_id: dict[str, set] = {}
    for r in rows:
        by_id.setdefault(r["id"], set()).add(r["n_editable"])
    return {"max_abs_diff_vs_feature_table": worst, "traces_with_editable_count_varying_by_seed": sum(len(v) > 1 for v in by_id.values())}


def zscore(x: np.ndarray) -> np.ndarray:
    return (x - x.mean()) / x.std()


def within_seed_z(rows: list[dict], key: str) -> np.ndarray:
    out = np.zeros(len(rows))
    seeds = np.array([r["seed"] for r in rows])
    x = np.array([r[key] for r in rows], float)
    for s in set(seeds.tolist()):
        out[seeds == s] = zscore(x[seeds == s])
    return out


def design(rows: list[dict], unit: float, extra: tuple[str, ...] = (), seed_fe: bool = False,
           sources: bool = True) -> tuple[np.ndarray, list[str]]:
    ef = np.array([r["editable_frac"] for r in rows])
    cols = [np.ones(len(rows)), (ef - ef.mean()) / unit, within_seed_z(rows, "margin")]
    names = ["const", "editable_frac", "clean_margin"]
    if sources:
        for s in ("toolemu", "r-judge"):
            cols.append(np.array([r["source"] == s for r in rows], float))
            names.append(f"src_{s}")
    if seed_fe:
        for s in (1, 2):
            cols.append(np.array([r["seed"] == s for r in rows], float))
            names.append(f"seed_{s}")
    for k in extra:
        cols.append(within_seed_z(rows, k) if k == "n_windows" else np.array([r[k] for r in rows], float))
        names.append(k)
    return np.column_stack(cols), names


def odds(beta: float, se: float) -> dict:
    return {"or": math.exp(beta), "ci95": [math.exp(beta - 1.96 * se), math.exp(beta + 1.96 * se)], "beta": beta, "se": se,
            "p": float(chi2.sf((beta / se) ** 2, 1)) if se > 0 else None}


def boot_ci(rows: list[dict], fit: Callable[[list[dict]], float], groups: list[str], n: int, rng: np.random.Generator) -> list[float]:
    """Percentile CI of exp(coef), resampling rows within each group."""
    idx = {g: [i for i, r in enumerate(rows) if r["source"] == g] for g in groups}
    vals = []
    for _ in range(n):
        sample = [rows[j] for g in groups for j in rng.choice(idx[g], len(idx[g]))]
        try:
            vals.append(fit(sample))
        except (RuntimeError, np.linalg.LinAlgError, FloatingPointError):
            continue
    return [float(np.exp(np.percentile(vals, 2.5))), float(np.exp(np.percentile(vals, 97.5)))]


def fit_block(rows: list[dict], unit: float, rng: np.random.Generator | None = None, **kw) -> dict:
    X, names = design(rows, unit, **kw)
    y = np.array([r["y"] for r in rows])
    beta, se = firth(X, y)
    res = {"n": len(rows), "successes": int(y.sum()), "coef": {nm: odds(b, s) for nm, b, s in zip(names, beta, se)}}
    if rng is not None:
        groups = sorted({r["source"] for r in rows})
        res["editable_or_boot_ci95"] = boot_ci(rows, lambda rs: firth(design(rs, unit, **kw)[0], np.array([r["y"] for r in rs]))[0][1],
                                               groups, N_BOOT, rng)
    return res


def firth_sandwich(X: np.ndarray, y: np.ndarray, clusters: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Firth estimate with a cluster-robust covariance built from the modified score contributions."""
    beta, _ = firth(X, y)
    p = 1 / (1 + np.exp(-X @ beta))
    w = p * (1 - p)
    bread = np.linalg.inv(X.T @ (X * w[:, None]))
    h = np.einsum("ij,jk,ik->i", X * np.sqrt(w)[:, None], bread, X * np.sqrt(w)[:, None])
    scores = X * (y - p + h * (0.5 - p))[:, None]
    meat = np.zeros_like(bread)
    groups = np.unique(clusters)
    for g in groups:
        s = scores[clusters == g].sum(0)
        meat += np.outer(s, s)
    c = len(groups)
    return beta, (c / (c - 1)) * bread @ meat @ bread


def cluster_boot(rows: list[dict], unit: float, rng: np.random.Generator, **kw) -> list[float]:
    by_id: dict[str, list[dict]] = {}
    for r in rows:
        by_id.setdefault(r["id"], []).append(r)
    ids = sorted(by_id)
    vals = []
    for _ in range(N_BOOT_CLUSTER):
        sample = [r for i in rng.choice(len(ids), len(ids)) for r in by_id[ids[i]]]
        try:
            X = design(sample, unit, **kw)[0]
            vals.append(firth(X, np.array([r["y"] for r in sample]))[0][1])
        except (RuntimeError, np.linalg.LinAlgError, FloatingPointError):
            continue
    return [float(np.exp(np.percentile(vals, 2.5))), float(np.exp(np.percentile(vals, 97.5)))]


def pooled_block(rows: list[dict], unit: float, rng: np.random.Generator, **kw) -> dict:
    X, names = design(rows, unit, seed_fe=True, **kw)
    y = np.array([r["y"] for r in rows])
    ids = sorted({r["id"] for r in rows})
    clusters = np.array([ids.index(r["id"]) for r in rows])
    beta, cov = firth_sandwich(X, y, clusters)
    se = np.sqrt(np.diag(cov))
    ml = sm.Logit(y, X).fit(disp=0, maxiter=200, cov_type="cluster", cov_kwds={"groups": clusters})
    return {"n": len(rows), "n_traces": len(ids), "successes": int(y.sum()),
            "coef": {nm: odds(b, s) for nm, b, s in zip(names, beta, se)},
            "editable_or_ml_clustered": odds(float(ml.params[1]), float(ml.bse[1])),
            "editable_or_cluster_boot_ci95": cluster_boot(rows, unit, rng, seed_fe=True, **kw)}


def slope_heterogeneity(rows: list[dict], unit: float) -> dict:
    X, names = design(rows, unit, seed_fe=True)
    y = np.array([r["y"] for r in rows])
    ef = X[:, names.index("editable_frac")]
    inter = np.column_stack([ef * (np.array([r["seed"] for r in rows]) == s) for s in (1, 2)])
    Xi = np.column_stack([X, inter])
    ids = sorted({r["id"] for r in rows})
    beta, cov = firth_sandwich(Xi, y, np.array([ids.index(r["id"]) for r in rows]))
    b, V = beta[-2:], cov[-2:, -2:]
    stat = float(b @ np.linalg.inv(V) @ b)
    return {"wald_chi2_df2": stat, "p": float(chi2.sf(stat, 2))}


def bridge(rows: list[dict]) -> dict:
    """Section 2's published fit (n = 197) to the seed 0 fit here, one change at a time. Predictors z-scored in sample."""
    table = [r for r in read_jsonl(R / "trace_features.jsonl") if r["attack"] == "unconstrained" and r["set"] in ("val", "shade80")]
    t05 = {r["id"]: r["y"] for r in rows if r["seed"] == 0}

    def fit(rs: list[dict], ykey: Callable[[dict], float], windows: bool) -> dict:
        cols = [np.ones(len(rs)), zscore(np.array([r["editable_frac"] for r in rs])), zscore(np.array([r["clean_margin"] for r in rs]))]
        if windows:
            cols.append(zscore(np.array([r["n_windows"] for r in rs], float)))
        for s in ("toolemu", "r-judge", "shade-arena"):
            if any(r["source"] == s for r in rs):
                cols.append(np.array([r["source"] == s for r in rs], float))
        beta, se = firth(np.column_stack(cols), np.array([ykey(r) for r in rs], float))
        return {"n": len(rs), **odds(beta[1], se[1])}
    val = [r for r in table if r["set"] == "val"]
    op = lambda r: float(r["success_20_op"])
    return {"A published: val + SHADE-80, p<0.865, with windows": fit(table, op, True),
            "B val only, p<0.865, with windows": fit(val, op, True),
            "C val only, p<0.865, no windows": fit(val, op, False),
            "D val only, p<0.5, no windows (seed 0 fit)": fit([r for r in val if r["id"] in t05], lambda r: t05[r["id"]], False)}


def main() -> None:
    rb = Rebuilder(ROOT / "monitor" / "laya-monitor")
    rows = load_rows(rb)
    rng = np.random.default_rng(RNG_SEED)
    unit = float(np.array([r["editable_frac"] for r in rows]).std())
    per = {s: [r for r in rows if r["seed"] == s] for s in SEEDS}
    inj = [r for r in rows if r["source"] == "injecagent"]
    res = {"meta": {"editable_frac_unit_pooled_sd": unit, "bar": "p < 0.5", "budget": BUDGET,
                    "margin_sd_by_seed": {s: float(np.std([r["margin"] for r in per[s]])) for s in SEEDS},
                    "injecagent_editable_sd": float(np.std([r["editable_frac"] for r in inj])),
                    "feature_check": check_features(rows)},
           "bridge": bridge(rows),
           "per_seed": {s: fit_block(per[s], unit, rng) for s in SEEDS},
           "per_seed_with_windows": {s: fit_block(per[s], unit, extra=("n_windows",)) for s in SEEDS},
           "per_seed_matched_selection_p865": {s: fit_block([r for r in per[s] if r["at_865"]], unit) for s in SEEDS},
           "pooled": pooled_block(rows, unit, rng),
           "pooled_slope_heterogeneity": slope_heterogeneity(rows, unit),
           "injecagent": {s: fit_block([r for r in per[s] if r["source"] == "injecagent"], unit, rng, sources=False) for s in SEEDS},
           "injecagent_with_kind": {s: fit_block([r for r in per[s] if r["source"] == "injecagent"], unit, sources=False,
                                                 extra=("data_stealing",)) for s in SEEDS},
           "injecagent_pooled": pooled_block(inj, unit, rng, sources=False),
           "injecagent_pooled_with_kind": pooled_block(inj, unit, rng, sources=False, extra=("data_stealing",))}
    OUT.write_text(json.dumps(res, indent=1))
    print(json.dumps(res["meta"], indent=1))
    for k, v in res["bridge"].items():
        print(f"{k}: n={v['n']} OR {v['or']:.2f} [{v['ci95'][0]:.2f}, {v['ci95'][1]:.2f}] p={v['p']:.2g}")
    for name in ("per_seed", "per_seed_with_windows", "per_seed_matched_selection_p865", "injecagent", "injecagent_with_kind"):
        print(f"== {name}")
        for s, b in res[name].items():
            line = {k: f"{c['or']:.3g} [{c['ci95'][0]:.3g}, {c['ci95'][1]:.3g}] p={c['p']:.2g}" for k, c in b["coef"].items() if k != "const"}
            print(f"  seed {s} n={b['n']} succ={b['successes']} {line} boot={b.get('editable_or_boot_ci95')}")
    for name in ("pooled", "injecagent_pooled", "injecagent_pooled_with_kind"):
        b = res[name]
        print(f"== {name} n={b['n']} traces={b['n_traces']} succ={b['successes']}")
        for k, c in b["coef"].items():
            if k != "const":
                print(f"  {k}: OR {c['or']:.3g} [{c['ci95'][0]:.3g}, {c['ci95'][1]:.3g}] p={c['p']:.2g}")
        m = b["editable_or_ml_clustered"]
        print(f"  ML clustered editable OR {m['or']:.3g} [{m['ci95'][0]:.3g}, {m['ci95'][1]:.3g}]; cluster boot {b['editable_or_cluster_boot_ci95']}")
    print("slope heterogeneity", res["pooled_slope_heterogeneity"])


if __name__ == "__main__":
    main()
