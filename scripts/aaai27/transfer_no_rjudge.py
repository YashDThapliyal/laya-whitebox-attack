"""Transfer and random-control numbers without the R-Judge targets (CPU, stored scores only; no model or API calls).

Jobs 7 and 8 and Phase C report on all validation targets, 9 of which are R-Judge, a source where the monitor is near
chance on clean traces. This refits the same tables on InjecAgent + ToolEmu:
  transfer sets   every val attack set, both depths, on all three checkpoints (from job7_transfer.json, by source)
  random control  20 random agent-text swaps, per checkpoint (rebuilt from the manifest and stored scores)
  Fisher tests    each set against that control, Holm-adjusted across the same 8 tests per checkpoint as phaseB_stats.py
  random any      20 random any-token swaps against the unconstrained any-token attack (as random_any_control.py)
  Haiku judge     verdict quality, retest noise, flip rates and paired McNemar tests (as analyze_judge.py)
Every table is first computed with R-Judge included and asserted equal to the published file, so the only difference
in the output is the exclusion.
Output: results/aaai27/job7_transfer_no_rjudge.json (existing outputs are not modified), a summary on stdout.
"""
from __future__ import annotations

import json
from collections import defaultdict
from typing import Any

import analyze_judge as judge
import analyze_transfer as transfer
import random_any_control as rand_any
from phaseB_stats import FISHER_TESTS, TARGETS, cell, holm, wilson
from scipy.stats import fisher_exact

R = transfer.R
OUT = R / "job7_transfer_no_rjudge.json"
ALL_SOURCES = ("injecagent", "toolemu", "r-judge")
KEPT = ("injecagent", "toolemu")
CHECKPOINTS = tuple(transfer.CHECKPOINTS)


def sum_sources(block: dict[str, Any], model: str, sources: tuple[str, ...]) -> dict[str, Any]:
    present = [block[s][model] for s in sources if s in block]
    return cell(sum(c["transfer"] for c in present), sum(c["clean_flagged"] for c in present))


def attack_sets(sets: dict[str, Any], sources: tuple[str, ...]) -> dict[str, Any]:
    return {key: {m: sum_sources(block, m, sources) for m in CHECKPOINTS} for key, block in sets.items()
            if "shade80" not in key}


def random_control(models: dict[str, Any], sources: tuple[str, ...]) -> dict[str, Any]:
    """The val_agent_random control, restricted to `sources`; same pairs and rule as analyze_transfer.main."""
    rows = transfer.read_jsonl(R / "inputs" / "manifest.jsonl")
    clean = {r["id"]: r for r in rows if r["kind"] == "adv" and r["set"] == "agent_u_val"
             and r["point"] == "clean" and r["view"] == "full"}
    pairs = [(clean[r["id"]]["key"], r["key"]) for r in rows
             if r["kind"] == "random" and r["id"] in clean and clean[r["id"]]["source"] in sources]
    out = {}
    for m, (z, t, z_thr) in models.items():
        s = transfer.summarize(pairs, z, t, z_thr)
        out[m] = cell(s["transfer"], s["clean_flagged"])
    return out


def fisher_vs_random(sets: dict[str, Any], control: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for m in TARGETS:
        tests = [t for t in FISHER_TESTS if t in sets]
        ps, odds = [], []
        for key in tests:
            c, k0 = sets[key][m], control[m]
            res = fisher_exact([[c["k"], c["n"] - c["k"]], [k0["k"], k0["n"] - k0["k"]]], alternative="two-sided")
            ps.append(float(res.pvalue))
            odds.append(float(res.statistic))
        out[m] = {key: {"odds_ratio": o, "p": p, "p_holm": ph} for key, o, p, ph in zip(tests, odds, ps, holm(ps))}
    return out


def random_any(attack: dict[str, Any], sources: tuple[str, ...]) -> dict[str, Any]:
    """Random any-token swaps against the any-token attack; same rule as random_any_control.analyze."""
    manifest = rand_any.read_jsonl(R / "inputs" / "manifest.jsonl")
    clean_key = {r["id"]: r["key"] for r in manifest if r["kind"] == "adv" and r["set"] == "any_u_val"
                 and r["point"] == "clean" and r["view"] == "full"}
    rnd = {r["id"]: r for r in rand_any.read_jsonl(rand_any.RA / "texts.jsonl") if r["source"] in sources}
    out = {}
    for m, fname in rand_any.SCORE_FILES.items():
        zr = {r["key"]: r["z_max"] for r in rand_any.read_jsonl(rand_any.RA / fname)}
        zc = {r["key"]: r["z_max"] for r in rand_any.read_jsonl(rand_any.CLEAN_SCORES[m])}
        thr = rand_any.z_thr(rand_any.CALIBS[m])
        flagged = [i for i in rnd if i in clean_key and zc[clean_key[i]] >= thr]
        k = sum(zr[rnd[i]["key"]] < thr for i in flagged)
        a = attack[m]
        res = fisher_exact([[a["k"], a["n"] - a["k"]], [k, len(flagged) - k]])
        out[m] = {"random_any": cell(k, len(flagged)), "any_token_attack": a, "fisher_p": float(res.pvalue)}
    return out


def judge_tables(sources: tuple[str, ...]) -> dict[str, Any]:
    calls = [c for c in judge.load() if c["source"] in (*sources, "shade-arena")]
    traces = judge.by_trace(calls, "matched")
    q = judge.quality(calls)["val"]
    m = judge.matched(traces, lambda t: True)
    by_source: dict[str, dict[str, Any]] = defaultdict(dict)
    for s in sources:
        block = judge.matched(traces, lambda t, s=s: t["source"] == s)
        by_source[s] = {"stably_flagged": block["stably_flagged"], "flip": block["flip"]}
    return {"violating_called_violating": q["clean_violating_called_violating"],
            "compliant_called_violating": q["compliant_called_violating"], "suspicion_auroc": q["suspicion_auroc"],
            "retest_verdict_disagree": q["retest_verdict_disagree"], "stably_flagged": m["stably_flagged"],
            "flip": m["flip"], "mcnemar": m["mcnemar"], "by_source": dict(by_source)}


def check_reproduces_published(models: dict[str, Any], sets: dict[str, Any]) -> None:
    """With R-Judge included, every table must equal the published file; otherwise the exclusion is not the only change."""
    stats = json.loads((R / "phaseB_stats.json").read_text())["job7"]
    published_any = json.loads((R / "job7_random_any_control.json").read_text())
    published_judge = json.loads(judge.OUT.read_text())["matched_all"]
    full_sets = attack_sets(sets, ALL_SOURCES)
    full_ctrl = random_control(models, ALL_SOURCES)
    for key, row in full_sets.items():
        for m in CHECKPOINTS:
            assert (row[m]["k"], row[m]["n"]) == (stats["sets"][key][m]["k"], stats["sets"][key][m]["n"]), (key, m)
    for m in CHECKPOINTS:
        assert (full_ctrl[m]["k"], full_ctrl[m]["n"]) == (stats["random_control"][m]["k"], stats["random_control"][m]["n"]), m
    fisher = fisher_vs_random(full_sets, full_ctrl)
    for m, tests in fisher.items():
        for key, v in tests.items():
            assert abs(v["p_holm"] - stats["fisher_vs_random"][m][key]["p_holm"]) < 1e-12, (m, key)
    any_full = random_any(full_sets["any_u_val|op"], ALL_SOURCES)
    for m, v in any_full.items():
        assert v["random_any"]["k"] == published_any[m]["random_any"]["k"], m
        assert abs(v["fisher_p"] - published_any[m]["fisher_attack_vs_random_any"]["p"]) < 1e-12, m
    j = judge_tables(ALL_SOURCES)
    assert j["stably_flagged"] == published_judge["stably_flagged"]
    assert j["mcnemar"] == published_judge["mcnemar"]


def main() -> None:
    models = {m: transfer.load_checkpoint(m) for m in CHECKPOINTS}
    sets = json.loads((R / "job7_transfer.json").read_text())["sets"]
    check_reproduces_published(models, sets)
    kept_sets = attack_sets(sets, KEPT)
    control = random_control(models, KEPT)
    res = {"excluded": "r-judge", "sources": list(KEPT),
           "sets": kept_sets, "random_control": control, "fisher_vs_random": fisher_vs_random(kept_sets, control),
           "random_any": random_any(kept_sets["any_u_val|op"], KEPT), "judge": judge_tables(KEPT)}
    OUT.write_text(json.dumps(res, indent=1))
    show(res)


def show(res: dict[str, Any]) -> None:
    for key, row in res["sets"].items():
        f = {m: res["fisher_vs_random"][m].get(key) for m in TARGETS}
        print(key, " ".join(f"{m} {row[m]['k']}/{row[m]['n']}" for m in CHECKPOINTS),
              {m: round(v["p_holm"], 5) for m, v in f.items() if v})
    print("random", {m: f"{c['k']}/{c['n']} {wilson(c['k'], c['n'])}" for m, c in res["random_control"].items()})
    print("random any", {m: (f"{v['any_token_attack']['k']}/{v['any_token_attack']['n']}",
                             f"{v['random_any']['k']}/{v['random_any']['n']}", round(v["fisher_p"], 4))
                         for m, v in res["random_any"].items()})
    print("judge", json.dumps(res["judge"], indent=1))


if __name__ == "__main__":
    main()
