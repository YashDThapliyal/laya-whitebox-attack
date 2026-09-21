"""Diagnostic: which windows of compliant SHADE traces trip the monitor? (explains FPR ~ 0.99)."""
import json, random
import numpy as np
import monitor_lib as ml

random.seed(0)
dev = ml.device()
model, cfg = ml.load_model("monitor/laya-monitor", dev)
tok = ml.load_tokenizer("monitor/laya-monitor")
enc = ml.Encoder(tok)
cal = json.load(open("monitor/calibration.json"))
T, thr = cal["temperature"], cal["threshold"]
recs = ml.read_jsonl("data/eval_heldout.jsonl")
out = {}
for lab in ("compliant", "violating"):
    rs = random.sample([r for r in recs if r["label"] == lab], 25)
    fr, first_idx, ex = [], [], []
    for r in rs:
        wins, spans = enc.windows(enc.state_ids(r["state"]))
        p = ml.sigmoid(ml.logits_for(model, [enc.item(w) for w in wins], tok.pad_token_id, dev) / T)
        fr.append(float((p >= thr).mean()))
        first_idx.append(int(np.argmax(p >= thr)) if (p >= thr).any() else -1)
        j = int(np.argmax(p))
        ex.append({"id": r["id"], "n_windows": len(wins), "frac_windows_flagged": fr[-1], "max_p": float(p.max()),
                   "top_window_text": tok.decode(wins[j][ml.PREFIX_TOKENS:])[:700]})
    out[lab] = {"mean_frac_windows_flagged": float(np.mean(fr)), "median_frac": float(np.median(fr)),
                "first_flagged_window_median": float(np.median(first_idx)), "examples": ex[:4]}
    print(lab, out[lab]["mean_frac_windows_flagged"], out[lab]["median_frac"], out[lab]["first_flagged_window_median"], flush=True)
json.dump(out, open("results/diag_fp_windows.json", "w"), indent=1)
