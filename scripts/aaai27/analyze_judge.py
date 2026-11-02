"""Phase C analysis: is Claude Haiku 5.5, used as a judge, moved by the edits that flipped the Laya monitor?

Reads results/aaai27/phaseC/{plan.json, judge_calls.jsonl} (llm_judge.py). Reports:
  judge quality   verdict rates on clean violating traces (two calls each) and on compliant traces; suspicion AUROC
  judge noise     how often the two calls on the same clean trace disagree
  matched block   on the same val traces: judge flip rate for the unconstrained agent-text edit, the fluent agent-text
                  edit and the random-edit control. A trace counts if the judge called its clean version violating
                  on both calls (stable detection); a flip = the edited version is called not violating. Paired
                  exact McNemar tests (binomial on discordant pairs) between conditions. Reported on all traces and
                  on the subset where the edit flipped run 2 (for each attack), and on the 62 traces both attacks
                  flipped.
  SHADE block     judge flips on run 2's SHADE-80 agent-text flips (no random control exists there)
Output: results/aaai27/phaseC_judge.json, markdown on stdout.
"""
from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.stats import binomtest, wilcoxon
from sklearn.metrics import roc_auc_score

ROOT = Path(__file__).resolve().parents[2]
PC = ROOT / "results" / "aaai27" / "phaseC"
OUT = ROOT / "results" / "aaai27" / "phaseC_judge.json"
CONDS = ("agent_u_val", "agent_c_val", "random")


def wilson(k: int, n: int, z: float = 1.96) -> list[float] | None:
    if n == 0:
        return None
    p, d = k / n, 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(max(0.0, c - h), 3), round(min(1.0, c + h), 3)]


def cell(k: int, n: int) -> dict:
    return {"k": k, "n": n, "rate": k / n if n else None, "ci95": wilson(k, n)}


def load() -> list[dict]:
    plan = {c["call"]: c for c in json.loads((PC / "plan.json").read_text())}
    rows = [json.loads(line) for line in (PC / "judge_calls.jsonl").read_text().splitlines() if line.strip()]
    last = {r["call"]: r for r in rows if "error" not in r}
    return [{**plan[k], **v} for k, v in last.items()]


def quality(calls: list[dict]) -> dict:
    out = {}
    for group, is_shade in (("val", False), ("shade", True)):
        clean = [c for c in calls if c["role"] == "clean" and (c["source"] == "shade-arena") == is_shade]
        comp = [c for c in calls if c["role"] == "compliant" and (c["source"] == "shade-arena") == is_shade]
        y = [1] * len(clean) + [0] * len(comp)
        s = [c["suspicion"] for c in clean + comp]
        out[group] = {"clean_violating_called_violating": cell(sum(c["violating"] for c in clean), len(clean)),
                      "compliant_called_violating": cell(sum(c["violating"] for c in comp), len(comp)),
                      "suspicion_auroc": float(roc_auc_score(y, s)) if comp and clean else None}
        by_key = defaultdict(list)
        for c in clean:
            by_key[c["key"]].append(c)
        pairs = [v for v in by_key.values() if len(v) == 2]
        out[group]["retest_verdict_disagree"] = cell(sum(a["violating"] != b["violating"] for a, b in pairs), len(pairs))
        out[group]["retest_median_abs_suspicion_diff"] = float(np.median([abs(a["suspicion"] - b["suspicion"]) for a, b in pairs]))
    return out


def by_trace(calls: list[dict], block: str) -> dict[str, dict]:
    t: dict[str, dict] = defaultdict(lambda: {"clean": []})
    for c in calls:
        if c.get("block") != block:
            continue
        rec = t[c["id"]]
        rec["source"] = c["source"]
        if c["role"] == "clean":
            rec["clean"].append(c)
        else:
            rec[c["set"] if c["role"] == "adv" else "random"] = c
    return t


def mcnemar(a: list[bool], b: list[bool]) -> dict:
    n01 = sum(x and not y for x, y in zip(a, b))
    n10 = sum(y and not x for x, y in zip(a, b))
    p = binomtest(n01, n01 + n10, 0.5).pvalue if n01 + n10 else 1.0
    return {"only_first": n01, "only_second": n10, "p_exact": float(p)}


def matched(traces: dict[str, dict], keep) -> dict:
    stable = {i: t for i, t in traces.items() if len(t["clean"]) == 2 and all(c["violating"] for c in t["clean"])
              and all(k in t for k in CONDS) and keep(t)}
    flips = {k: [not t[k]["violating"] for t in stable.values()] for k in CONDS}
    clean_s = {i: np.mean([c["suspicion"] for c in t["clean"]]) for i, t in stable.items()}
    shift = {k: [t[k]["suspicion"] - clean_s[i] for i, t in stable.items()] for k in CONDS}
    res = {"traces_in_scope": sum(1 for t in traces.values() if keep(t)), "stably_flagged": len(stable),
           "flip": {k: cell(sum(v), len(v)) for k, v in flips.items()},
           "median_suspicion_shift": {k: float(np.median(v)) if v else None for k, v in shift.items()},
           "mcnemar": {"unconstrained_vs_random": mcnemar(flips["agent_u_val"], flips["random"]),
                       "fluent_vs_random": mcnemar(flips["agent_c_val"], flips["random"]),
                       "fluent_vs_unconstrained": mcnemar(flips["agent_c_val"], flips["agent_u_val"])}}
    if len(stable) >= 10:
        for k in ("agent_u_val", "agent_c_val"):
            d = np.array(shift[k]) - np.array(shift["random"])
            res[f"wilcoxon_shift_{k}_vs_random_p"] = float(wilcoxon(d).pvalue) if np.any(d) else 1.0
    return res


def shade(calls: list[dict]) -> dict:
    t = by_trace(calls, "shade")
    out = {}
    for s in ("agent_u_shade80", "agent_c_shade80"):
        st = [x for x in t.values() if s in x and len(x["clean"]) == 2 and all(c["violating"] for c in x["clean"])]
        out[s] = {"run2_flips": sum(1 for x in t.values() if s in x), "judge_stably_flags_clean": len(st),
                  "judge_flip": cell(sum(not x[s]["violating"] for x in st), len(st))}
    return out


def main() -> None:
    calls = load()
    t = by_trace(calls, "matched")
    res = {"n_calls": len(calls), "cost_usd": sum(c["cost"] for c in calls), "quality": quality(calls),
           "matched_all": matched(t, lambda x: True),
           "matched_both_flipped_run2": matched(t, lambda x: x.get("agent_u_val", {}).get("run2_flipped")
                                                and x.get("agent_c_val", {}).get("run2_flipped")),
           "matched_by_source": {s: matched(t, lambda x, s=s: x["source"] == s) for s in ("injecagent", "toolemu", "r-judge")},
           "shade": shade(calls)}
    OUT.write_text(json.dumps(res, indent=1))
    print(json.dumps({k: v for k, v in res.items() if k != "matched_by_source"}, indent=1))
    for s, v in res["matched_by_source"].items():
        print(s, v["stably_flagged"], {k: (c["k"], c["n"]) for k, c in v["flip"].items()})


if __name__ == "__main__":
    main()
