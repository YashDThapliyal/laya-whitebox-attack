"""Phase 4.5: per-source monitor quality, trained vs zero-shot, on the EXISTING Phase-2 val slices.

Uses the `split` field already in data/train_pool.jsonl (R-Judge grouped by scenario file, InjecAgent by
user tool, ToolEmu by case) -- no new splits. Scoring = the same windowed max-margin used everywhere else.
AUROC 95% CIs by stratified bootstrap (1,000 resamples). SHADE rows are read from the Phase-3 score files.
"""
import json

import numpy as np
from sklearn.metrics import roc_auc_score

import monitor_lib as ml

rng = np.random.default_rng(0)


def boot_ci(y, s, n=1000):
    y, s = np.asarray(y), np.asarray(s)
    pos, neg = np.where(y == 1)[0], np.where(y == 0)[0]
    vals = []
    for _ in range(n):
        idx = np.concatenate([rng.choice(pos, len(pos)), rng.choice(neg, len(neg))])
        vals.append(roc_auc_score(y[idx], s[idx]))
    return [float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))]


def score(model_dir, recs):
    dev = ml.device()
    model, _ = ml.load_model(model_dir, dev)
    tok = ml.load_tokenizer(model_dir)
    enc = ml.Encoder(tok)
    items, owner = [], []
    for i, r in enumerate(recs):
        wins, _ = enc.windows(enc.state_ids(r["state"]))
        for w in wins:
            items.append(enc.item(w)); owner.append(i)
    zw = ml.logits_for(model, items, tok.pad_token_id, dev, bs=64)
    owner = np.array(owner)
    return np.array([zw[owner == i].max() for i in range(len(recs))])


val = [r for r in ml.read_jsonl("data/train_pool.jsonl") if r["split"] == "val"]
y = np.array([r["label"] == "violating" for r in val], int)
src = np.array([r["source"] for r in val])
z_tr = score("monitor/laya-monitor", val)
z_zs = score(ml.base_dir(), val)
out = {}
for s in ["r-judge", "injecagent", "toolemu"]:
    m = src == s
    out[s] = {"n": int(m.sum()), "n_violating": int(y[m].sum()),
              "auroc_trained": float(roc_auc_score(y[m], z_tr[m])), "ci_trained": boot_ci(y[m], z_tr[m]),
              "auroc_zeroshot": float(roc_auc_score(y[m], z_zs[m])), "ci_zeroshot": boot_ci(y[m], z_zs[m])}
for tag, key in [("finetuned", "trained"), ("zeroshot", "zeroshot")]:
    rows = ml.read_jsonl(f"results/heldout_scores_{tag}.jsonl")
    yy = np.array([r["label"] == "violating" for r in rows], int)
    zz = np.array([r["z_max"] for r in rows])
    out.setdefault("shade-arena", {"n": len(rows), "n_violating": int(yy.sum())})
    out["shade-arena"][f"auroc_{key}"] = float(roc_auc_score(yy, zz))
    out["shade-arena"][f"ci_{key}"] = boot_ci(yy, zz, n=300)
json.dump(out, open("results/cross_source_auroc.json", "w"), indent=1)
print(json.dumps(out, indent=1))
