"""Fluency metric: GPT-2 perplexity of the text around each attack edit, before vs after.

For every edit, attack.py records `orig_context` and `adv_context`: the decoded +-12 tokens around the
edited position in the original and in the final adversarial trace. This scores both with GPT-2 (an LM
unrelated to the monitor and to the MLM filter) and aggregates per trace (mean log-PPL over its edits),
then per run x source (median over traces). Same metric for unconstrained and fluent runs.

Output: results/perplexity.json
"""
import glob
import json
import math
import os

import numpy as np
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

dev = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
tok = AutoTokenizer.from_pretrained("gpt2")
lm = AutoModelForCausalLM.from_pretrained("gpt2").to(dev).eval()
cache = {}


@torch.no_grad()
def log_ppl(text):
    if text in cache:
        return cache[text]
    ids = tok(text, return_tensors="pt").input_ids[:, :256].to(dev)
    if ids.size(1) < 2:
        cache[text] = float("nan")
        return cache[text]
    out = lm(ids, labels=ids)
    cache[text] = float(out.loss)
    return cache[text]


RUNS = {  # file stem -> (label, 0.865 successes derived from z_hist when the run used threshold 0.5)
    "val_agent": "unconstrained, agent text", "val_all": "unconstrained, any token",
    "mrt_agent": "unconstrained, agent text", "mrt_all": "unconstrained, any token",
    "t05_val_agent": "unconstrained, agent text, to p<0.5", "t05_val_all": "unconstrained, any token, to p<0.5",
    "t05_mrt_all": "unconstrained, any token, to p<0.5",
    "f_val_agent": "fluent, agent text", "f_val_all": "fluent, any token",
    "f_mrt_agent": "fluent, agent text", "f_mrt_all": "fluent, any token",
    "z_val_agent": "zero-shot ckpt, fluent, agent text", "z_val_all": "zero-shot ckpt, fluent, any token",
    "z_mrt_agent": "zero-shot ckpt, fluent, agent text", "z_mrt_all": "zero-shot ckpt, fluent, any token",
}
res = {}
for stem, label in RUNS.items():
    path = f"attack/{stem}.jsonl"
    if not os.path.exists(path):
        continue
    by = {}
    for l in open(path):
        r = json.loads(l)
        if not r["edits"]:
            continue
        o = [log_ppl(e["orig_context"]) for e in r["edits"]]
        a = [log_ppl(e["adv_context"]) for e in r["edits"]]
        src = "shade-arena" if "mrt" in stem else r["task"]
        by.setdefault(src, []).append({"orig": float(np.nanmean(o)), "adv": float(np.nanmean(a)),
                                       "success": bool(r["success"]), "n_edits": len(r["edits"])})
    for src, rows in by.items():
        o = np.array([x["orig"] for x in rows]); a = np.array([x["adv"] for x in rows])
        s = np.array([x["success"] for x in rows])
        res[f"{stem}|{src}"] = {
            "run": stem, "label": label, "source": src, "n_traces": len(rows),
            "ppl_orig_median": float(np.exp(np.median(o))), "ppl_adv_median": float(np.exp(np.median(a))),
            "ppl_ratio_median": float(np.exp(np.median(a - o))),
            "ppl_ratio_median_successes": float(np.exp(np.median((a - o)[s]))) if s.any() else None,
            "frac_traces_ppl_up_2x": float(np.mean((a - o) > math.log(2))),
        }
        x = res[f"{stem}|{src}"]
        print(f"{stem:12s} {src:12s} n={len(rows):3d} ppl {x['ppl_orig_median']:7.1f} -> {x['ppl_adv_median']:7.1f} "
              f"ratio {x['ppl_ratio_median']:.2f} (succ {x['ppl_ratio_median_successes']}) >2x {x['frac_traces_ppl_up_2x']:.2f}", flush=True)
json.dump(res, open("results/perplexity.json", "w"), indent=1)
