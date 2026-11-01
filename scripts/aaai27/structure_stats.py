"""AAAI-27 Phase A statistics on the per-trace feature table (results/aaai27/trace_features.jsonl).

1. Spearman correlations of attack success with editable fraction, window count and clean margin,
   pooled over in-distribution val (117) + SHADE-80, with source-stratified bootstrap 95% CIs.
   Also: the original 137-trace set (val + SHADE-20) for comparison, and within-source correlations.
2. Logistic regression: success ~ editable_frac + n_windows + clean_margin + source fixed effects.
   Continuous predictors are z-scored on the fitted sample, so coefficients are log-odds per SD.
   ML fit with Wald and stratified-bootstrap CIs, plus a Firth-penalized fit (robust to the
   separation that occurs when a source succeeds on every trace).
3. InjecAgent direct-harm vs data-stealing group sizes and success rates with Wilson CIs.

Success at the operating threshold (p < 0.865). Budget 20 for every source (primary); SHADE at 60 as
a sensitivity check (in-distribution traces were only run to 20).
Output: results/aaai27/phaseA_stats.json
"""
from __future__ import annotations

import json
import math
import warnings
from pathlib import Path

import numpy as np
import statsmodels.api as sm
from scipy.stats import norm, spearmanr
from statsmodels.tools.sm_exceptions import PerfectSeparationError

ROOT = Path(__file__).resolve().parents[2]
FEATURES = ROOT / "results" / "aaai27" / "trace_features.jsonl"
OUT = ROOT / "results" / "aaai27" / "phaseA_stats.json"
SEED = 0
N_BOOT_RHO = 10_000
N_BOOT_REG = 2_000
SOURCES = ("injecagent", "toolemu", "r-judge", "shade-arena")  # injecagent = reference level
PREDICTORS = ("editable_frac", "n_windows", "clean_margin")


def load(attack: str, sets: tuple[str, ...]) -> list[dict]:
    with FEATURES.open() as fh:
        rows = [json.loads(line) for line in fh]
    return [r for r in rows if r["attack"] == attack and r["set"] in sets]


def outcome(rows: list[dict], shade_budget: int) -> np.ndarray:
    return np.array([r[f"success_{shade_budget if r['source'] == 'shade-arena' else 20}_op"] for r in rows], float)


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def strata_indices(rows: list[dict]) -> list[np.ndarray]:
    src = np.array([r["source"] for r in rows])
    return [np.flatnonzero(src == s) for s in SOURCES if (src == s).any()]


def stratified_sample(strata: list[np.ndarray], rng: np.random.Generator) -> np.ndarray:
    return np.concatenate([rng.choice(ix, size=len(ix), replace=True) for ix in strata])


def safe_rho(y: np.ndarray, x: np.ndarray) -> float:
    if np.ptp(y) == 0 or np.ptp(x) == 0:
        return float("nan")
    return float(spearmanr(y, x).statistic)


def spearman_block(rows: list[dict], y: np.ndarray, stratified: bool) -> dict:
    rng = np.random.default_rng(SEED)
    strata = strata_indices(rows) if stratified else [np.arange(len(rows))]
    boots = [stratified_sample(strata, rng) for _ in range(N_BOOT_RHO)]
    out = {"n": len(rows), "n_success": int(y.sum())}
    for k in PREDICTORS:
        x = np.array([r[k] for r in rows], float)
        if np.ptp(x) == 0:
            out[k] = {"rho": None, "note": "constant within this set"}
            continue
        res = spearmanr(y, x)
        bs = np.array([safe_rho(y[b], x[b]) for b in boots])
        bs = bs[~np.isnan(bs)]
        out[k] = {"rho": float(res.statistic), "p": float(res.pvalue),
                  "ci95": [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))],
                  "n_boot_valid": int(bs.size)}
    return out


def design(rows: list[dict], idx: np.ndarray | None = None) -> tuple[np.ndarray, list[str]]:
    idx = np.arange(len(rows)) if idx is None else idx
    sub = [rows[i] for i in idx]
    cols, names = [np.ones(len(sub))], ["const"]
    for k in PREDICTORS:
        x = np.array([r[k] for r in sub], float)
        cols.append((x - x.mean()) / x.std())
        names.append(f"{k}_z")
    for s in SOURCES[1:]:
        cols.append(np.array([r["source"] == s for r in sub], float))
        names.append(f"src_{s}")
    return np.column_stack(cols), names


def firth(X: np.ndarray, y: np.ndarray, iters: int = 200, tol: float = 1e-8) -> tuple[np.ndarray, np.ndarray]:
    """Firth-penalized logistic regression (Jeffreys prior). Returns (beta, se)."""
    beta = np.zeros(X.shape[1])
    for _ in range(iters):
        p = 1 / (1 + np.exp(-X @ beta))
        w = p * (1 - p)
        info = X.T @ (X * w[:, None])
        cov = np.linalg.inv(info)
        h = np.einsum("ij,jk,ik->i", X * np.sqrt(w)[:, None], cov, X * np.sqrt(w)[:, None])
        step = cov @ (X.T @ (y - p + h * (0.5 - p)))
        beta = beta + step
        if np.max(np.abs(step)) < tol:
            break
    else:
        raise RuntimeError("Firth fit did not converge")
    p = 1 / (1 + np.exp(-X @ beta))
    cov = np.linalg.inv(X.T @ (X * (p * (1 - p))[:, None]))
    return beta, np.sqrt(np.diag(cov))


def ml_fit(X: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray] | None:
    """Unpenalized ML; None if it fails or shows separation (huge coefficients)."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            res = sm.Logit(y, X).fit(disp=0, maxiter=200)
        except (PerfectSeparationError, np.linalg.LinAlgError, ValueError):  # degenerate resamples
            return None
    if not res.mle_retvals.get("converged", False) or np.any(np.abs(res.params) > 15):
        return None
    return np.asarray(res.params), np.asarray(res.bse)


def coef_table(names: list[str], beta: np.ndarray, se: np.ndarray, boot: np.ndarray | None) -> dict:
    z = norm.ppf(0.975)
    tab = {}
    for i, n in enumerate(names):
        row = {"beta": float(beta[i]), "wald_ci95": [float(beta[i] - z * se[i]), float(beta[i] + z * se[i])],
               "p_wald": float(2 * norm.sf(abs(beta[i] / se[i]))), "odds_ratio": float(np.exp(beta[i]))}
        if boot is not None and boot.size:
            row["boot_ci95"] = [float(np.percentile(boot[:, i], 2.5)), float(np.percentile(boot[:, i], 97.5))]
        tab[n] = row
    return tab


def regression(rows: list[dict], y: np.ndarray, method: str) -> dict:
    X, names = design(rows)
    fit = ml_fit(X, y) if method == "ml" else firth(X, y)
    if fit is None:
        return {"method": method, "status": "ML did not converge (separation); see Firth fit"}
    beta, se = fit
    rng = np.random.default_rng(SEED)
    strata = strata_indices(rows)
    boots, failed = [], 0
    for _ in range(N_BOOT_REG):
        b = stratified_sample(strata, rng)
        Xb, _ = design(rows, b)
        try:
            fb = ml_fit(Xb, y[b]) if method == "ml" else firth(Xb, y[b])
        except (RuntimeError, np.linalg.LinAlgError):
            fb = None
        if fb is None:
            failed += 1
        else:
            boots.append(fb[0])
    sd = {k: float(np.std([r[k] for r in rows])) for k in PREDICTORS}
    return {"method": method, "n": len(rows), "n_success": int(y.sum()), "predictor_sd": sd,
            "coefficients": coef_table(names, beta, se, np.array(boots)),
            "n_boot": N_BOOT_REG, "n_boot_failed": failed}


def injecagent_split(rows: list[dict]) -> dict:
    out = {}
    for t in ("direct_harm", "data_stealing"):
        g = [r for r in rows if r["source"] == "injecagent" and r["injecagent_type"] == t]
        k = sum(r["success_20_op"] for r in g)
        out[t] = {"n": len(g), "success_20": k, "rate": k / len(g) if g else None, "wilson95": wilson(k, len(g)),
                  "median_editable_frac": float(np.median([r["editable_frac"] for r in g])),
                  "median_n_windows": float(np.median([r["n_windows"] for r in g]))}
    return out


def main() -> None:
    out: dict = {"meta": {"bar": "p < 0.865 (operating threshold)", "seed": SEED,
                          "bootstrap": "percentile; resample traces within source (stratified)",
                          "n_boot_spearman": N_BOOT_RHO, "n_boot_regression": N_BOOT_REG}}
    for attack in ("unconstrained", "constrained"):
        a: dict = {}
        orig = load(attack, ("val", "shade20"))
        a["spearman_original137_b20"] = spearman_block(orig, outcome(orig, 20), stratified=True)
        pooled = load(attack, ("val", "shade80"))
        for sb in (20, 60):
            y = outcome(pooled, sb)
            a[f"spearman_pooled_shade80_b{sb}"] = spearman_block(pooled, y, stratified=True)
            shade = [r for r in pooled if r["source"] == "shade-arena"]
            a[f"spearman_within_shade80_b{sb}"] = spearman_block(shade, outcome(shade, sb), stratified=False)
            for method in ("ml", "firth"):
                a[f"logit_{method}_shade_b{sb}"] = regression(pooled, y, method)
        inj = [r for r in pooled if r["source"] == "injecagent"]
        a["spearman_within_injecagent_b20"] = spearman_block(inj, outcome(inj, 20), stratified=False)
        a["injecagent_split"] = injecagent_split(pooled)
        out[attack] = a
        print(f"{attack}: done")
    OUT.write_text(json.dumps(out, indent=1))
    print(f"wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
