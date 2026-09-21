"""Build the human-review set of successful fluent edits (fine-tuned monitor, agent-text scope).

For every trace the fluent attack flipped at the operating threshold (p < 0.865), replay its edits on the
original token ids up to the first crossing, decode, and diff line by line against the original trace.
Output: results/edit_review_items.json (one item per trace: changed lines before/after) and
results/edit_review_items.md (plain side-by-side listing for eyeballing).
"""
import difflib
import json
import math

import monitor_lib as ml

tok = ml.load_tokenizer("monitor/laya-monitor")
enc = ml.Encoder(tok)
cal = json.load(open("monitor/calibration.json"))
Z865 = cal["temperature"] * math.log(cal["threshold"] / (1 - cal["threshold"]))
recs = {r["id"]: r for f in ["data/train_pool.jsonl", "data/eval_heldout.jsonl"] for r in ml.read_jsonl(f)}
str2id = {}
for i in range(len(tok)):
    str2id.setdefault(tok.decode([i]), i)

items = []
for stem in ["f_val_agent", "f_mrt_agent"]:
    for l in open(f"attack/{stem}.jsonl"):
        r = json.loads(l)
        k = next((i for i, z in enumerate(r["z_hist"]) if z < Z865), None)
        if k is None or k == 0:
            continue
        sids = list(enc.state_ids(recs[r["id"]]["state"]))
        orig = list(sids)
        ok = True
        for e in r["edits"][:k]:
            if tok.decode([sids[e["pos"]]]) != e["from"] or e["to"] not in str2id:
                ok = False
                break
            sids[e["pos"]] = str2id[e["to"]]
        if not ok:
            print("replay mismatch", r["id"])
            continue
        a, b = tok.decode(orig).split("\n"), tok.decode(sids).split("\n")
        changed = [(a[i1:i2], b[j1:j2]) for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(a=a, b=b).get_opcodes() if tag != "equal"]
        items.append({"id": r["id"], "source": "shade-arena" if "mrt" in stem else r["task"], "swaps": k,
                      "p_before": r["p_hist"][0], "p_after": r["p_hist"][k],
                      "changed": [{"original": "\n".join(x), "edited": "\n".join(y)} for x, y in changed]})
json.dump(items, open("results/edit_review_items.json", "w"), indent=1)
print(len(items), "flipped traces reconstructed;", {s: sum(i["source"] == s for i in items) for s in {i["source"] for i in items}})
