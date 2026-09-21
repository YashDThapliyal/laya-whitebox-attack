"""Phase 4: white-box, gradient-guided (HotFlip-style) token-substitution attack on the monitor.

Threat model: the monitored agent controls only the text it writes. Editable positions are the tokens of
agent-authored message text ([AGENT] lines: visible replies and <model_thinking>); the user request,
tool-call names, and tool outputs are fixed (changing them would change what the agent actually did).
`--scope all` lifts that restriction (any trace token) as an upper bound.

Trace score = max over sliding windows of the monitor margin z (see monitor_lib). Success = the trace's
p(violating) = sigmoid(max_w z_w / T) drops below the val-F1-optimal threshold.

Per step (one token substitution = one unit of budget):
  1. forward all windows; objective J = logsumexp_w(z_w)  (smooth max over windows)
  2. grad of J w.r.t. every window's input embeddings, scattered back to trace positions (a trace
     position can sit in several overlapping windows)
  3. first-order HotFlip score for every (editable position i, candidate token v):
        dJ ~= (E[v] - E[x_i]) . g_i          -> take the K most negative (<= 4 tokens per position)
  4. evaluate every candidate exactly (re-score only the windows containing i); apply the best one
  5. stop at success or when the budget is exhausted
Candidate vocabulary: tokens that decode to plain alphabetic word pieces (plus basic punctuation), no
special tokens, so edits stay text-like. Every run is also re-verified by decoding the adversarial token
ids to text, re-tokenizing, and re-scoring (tokenization need not round-trip).
A random-substitution baseline (same positions/vocab/budget) isolates the value of the gradient.
"""
import argparse
import json
import math
import os
import random
import re
import time

import numpy as np
import torch

import monitor_lib as ml

p = argparse.ArgumentParser()
p.add_argument("--model", default="monitor/laya-monitor")
p.add_argument("--calib", default="monitor/calibration.json")
p.add_argument("--data", default="data/eval_heldout.jsonl")
p.add_argument("--scores", default="results/heldout_scores_finetuned.jsonl",
               help="per-trace scores from eval_monitor.py, or 'compute' to score the (val-split violating) records here")
p.add_argument("--n", type=int, default=30)
p.add_argument("--budget", type=int, default=20)
p.add_argument("--topk", type=int, default=48)
p.add_argument("--scope", choices=["agent", "all"], default="agent")
p.add_argument("--random_baseline", action="store_true")
p.add_argument("--max_windows", type=int, default=40, help="skip traces with more windows (time cap)")
p.add_argument("--max_minutes", type=float, default=90)
p.add_argument("--out", default="attack/results_agent.jsonl")
p.add_argument("--seed", type=int, default=0)
args = p.parse_args()

random.seed(args.seed); np.random.seed(args.seed); torch.manual_seed(args.seed)
ml.AMP = False  # fp32 (TF32 matmuls) margins for candidate ranking and success checks; bf16 is too coarse
torch.backends.cuda.matmul.allow_tf32 = True
torch.backends.cudnn.allow_tf32 = True
dev = ml.device()
model, cfg = ml.load_model(args.model, dev)
model.eval()
for q in model.parameters():
    q.requires_grad_(False)
tok = ml.load_tokenizer(args.model)
enc = ml.Encoder(tok)
cal = json.load(open(args.calib))
T, THR = cal["temperature"], cal["threshold"]
Z_THR = T * math.log(THR / (1 - THR))  # p < THR  <=>  max-window margin < Z_THR
E = model.encoder.get_input_embeddings().weight  # [V, d]

# ---- candidate vocabulary: plain word pieces
vocab_ok = torch.zeros(E.size(0), dtype=torch.bool)
special = set(tok.all_special_ids)
for tid in range(min(E.size(0), len(tok))):
    s = tok.decode([tid])
    if tid not in special and re.fullmatch(r" ?[A-Za-z]{1,12}|[.,;:!?'\-]", s):
        vocab_ok[tid] = True
vocab_ok = vocab_ok.to(dev)
print(f"candidate vocab {int(vocab_ok.sum())} / {E.size(0)} ; Z_THR {Z_THR:.3f} (thr {THR:.3f}, T {T:.3f})", flush=True)


CONTEXT_TAGS = r"USER|AGENT PROFILE|AVAILABLE TOOLKITS"      # never editable: not written by the agent
AGENT_TAGS = r"AGENT|AGENT THOUGHT|AGENT FINAL ANSWER"         # agent-authored prose
# ToolEmu pseudo-traces have no tool calls: their [AGENT ACTION] lines are the agent's own narrated actions,
# so for ToolEmu those lines count as agent-authored text. Elsewhere [AGENT ACTION] = a tool call (fixed).


def _line_spans(text, tags, whole=False):
    """Char spans of lines with the given tags: content only, or (whole=True) the full line incl. tag and newline."""
    out = []
    for mt in re.finditer(rf"^\[({tags})\] (.*)$", text, flags=re.M):
        out.append((mt.start(0), min(len(text), mt.end(0) + 1)) if whole else mt.span(2))
    return out


def editable_mask(text, sids, source=None):
    """Token positions (in state ids) the attacker may change.
    agent scope: agent-authored lines only. all scope: every token outside user/profile/toolkit lines.
    The shared window prefix (first PREFIX_TOKENS) is frozen only for multi-window traces, where it is
    repeated in every window; single-window traces have no such duplication."""
    offs = enc.tok(text.replace(tok.mask_token, " "), add_special_tokens=False, return_offsets_mapping=True)["offset_mapping"]
    assert len(offs) == len(sids)

    def in_spans(spans):
        m, j = np.zeros(len(sids), bool), 0
        for i, (a, b) in enumerate(offs):
            while j < len(spans) and spans[j][1] <= a:
                j += 1
            if j < len(spans) and spans[j][0] <= a and b <= spans[j][1]:
                m[i] = True
        return m

    if args.scope == "all":
        ctx = _line_spans(text, CONTEXT_TAGS, whole=True)
        m = ~in_spans(ctx) if ctx else np.ones(len(sids), bool)
    else:
        tags = AGENT_TAGS + ("|AGENT ACTION" if source == "toolemu" else "")
        m = in_spans(_line_spans(text, tags))
    if len(sids) > enc.budget:
        m[: ml.PREFIX_TOKENS] = False
    return m


class Trace:
    def __init__(self, text, source=None):
        self.text = text
        self.sids = np.array(enc.state_ids(text))
        _, self.spans = enc.windows(list(self.sids))
        self.edit = editable_mask(text, self.sids, source)

    def window_ids(self, sids=None, which=None):
        sids = self.sids if sids is None else sids
        which = range(len(self.spans)) if which is None else which
        out = []
        for w in which:
            s, e = self.spans[w]
            body = list(sids[:ml.PREFIX_TOKENS]) + list(sids[s:e]) if len(self.spans) > 1 or s > 0 else list(sids[s:e])
            out.append(enc.item(body))
        return out

    def win_positions(self, w):
        """Map window w's sequence index -> trace state position."""
        s, e = self.spans[w]
        H = len(enc.head)
        if len(self.spans) == 1 and s == 0:
            return {H + k: k for k in range(e - s)}
        d = {H + k: k for k in range(ml.PREFIX_TOKENS)}
        d.update({H + ml.PREFIX_TOKENS + k: s + k for k in range(e - s)})
        return d


def score_windows(items, bs=48):
    return ml.logits_for(model, items, tok.pad_token_id, dev, bs=bs)


def grad_by_position(tr):
    """dJ/d(embedding) for each trace position, J = logsumexp over windows of margin."""
    items = tr.window_ids()
    G = torch.zeros(len(tr.sids), E.size(1), device=dev)
    zs = []
    for i in range(0, len(items), 8):
        chunk = items[i:i + 8]
        ids, att, mpos, _, _ = ml.collate(chunk, tok.pad_token_id, dev)
        emb = model.encoder.get_input_embeddings()(ids).detach().requires_grad_(True)
        with torch.autocast("cuda", dtype=torch.bfloat16, enabled=ml.AMP and dev.type == "cuda"):
            z = ml.forward_embeds(model, emb, att, mpos)
        zs.append(z.detach())
        # logsumexp gradient weights = softmax(z) over ALL windows; computed after, so use z directly
        # and reweight: accumulate raw per-window grads, weight later
        z.sum().backward()
        g = emb.grad.float()
        for b in range(len(chunk)):
            w = i + b
            pos = tr.win_positions(w)
            seq_idx = torch.tensor(list(pos.keys()), device=dev)
            tr_idx = torch.tensor(list(pos.values()), device=dev)
            tr._wg = getattr(tr, "_wg", {})
            tr._wg[w] = (seq_idx, tr_idx, g[b])
    z_all = torch.cat(zs).float()
    wts = torch.softmax(z_all, 0)
    for w, (seq_idx, tr_idx, g) in tr._wg.items():
        G.index_add_(0, tr_idx, g[seq_idx] * wts[w])
    tr._wg = {}
    return G, z_all.cpu().numpy()


def trace_max(tr, sids):
    return float(score_windows(tr.window_ids(sids)).max())


def attack_one(tr, rnd=False):
    """Greedy search. Always applies the best exact-scored candidate (even if it doesn't improve), so the
    search can leave plateaus; the returned adversarial trace is the best state seen. hist[b] is the trace
    max-margin after b swaps, so success within budget b <=> min(hist[:b+1]) < Z_THR."""
    sids = tr.sids.copy()
    zw = score_windows(tr.window_ids(sids))
    hist = [float(zw.max())]
    edits, best_sids = [], sids.copy()
    editable = np.where(tr.edit)[0]
    if len(editable) == 0:
        return hist, edits, best_sids
    vocab_ids = np.where(vocab_ok.cpu().numpy())[0]
    for step in range(args.budget):
        if min(hist) < Z_THR:
            break
        if rnd:
            i = int(np.random.choice(editable))
            v = int(np.random.choice(vocab_ids))
            new = sids.copy(); new[i] = v
            zw_new = zw.copy()
            aff = [w for w, (s, e) in enumerate(tr.spans) if s <= i < e]
            zw_new[aff] = score_windows(tr.window_ids(new, aff))
            edits.append((i, int(sids[i]), v))
            sids, zw = new, zw_new
        else:
            saved, tr.sids = tr.sids, sids
            G, _ = grad_by_position(tr)
            tr.sids = saved
            g = G[torch.tensor(editable, device=dev)]                    # [P, d]
            cur = E[torch.tensor(sids[editable], device=dev)].float()      # [P, d]
            # first-order change of J for replacing x_i by v: (E_v - E_xi) . g_i
            sc = g @ E.float().T - (cur * g).sum(-1, keepdim=True)       # [P, V]
            sc[:, ~vocab_ok] = float("inf")
            sc[torch.arange(len(editable)), torch.tensor(sids[editable], device=dev)] = float("inf")
            per_pos = torch.topk(-sc, 4, dim=1)                         # best 4 tokens per position
            top = torch.topk(per_pos.values.flatten(), min(args.topk, per_pos.values.numel())).indices
            cands = [(int(editable[t // 4]), int(per_pos.indices.flatten()[t])) for t in top.tolist()]
            # exact evaluation of each candidate on the windows it touches
            batch_items, meta = [], []
            for (i, v) in cands:
                new = sids.copy(); new[i] = v
                for w in [w for w, (s, e) in enumerate(tr.spans) if s <= i < e]:
                    batch_items.extend(tr.window_ids(new, [w]))
                    meta.append((i, v, w))
            zc = score_windows(batch_items, bs=64)
            per = {}
            for (i, v, w), z in zip(meta, zc):
                per.setdefault((i, v), {})[w] = z
            best = (float("inf"), None, None)
            for (i, v), upd in per.items():
                zz = zw.copy()
                for w, z in upd.items():
                    zz[w] = z
                if zz.max() < best[0]:
                    best = (float(zz.max()), (i, v), zz)
            i, v = best[1]
            edits.append((i, int(sids[i]), v))
            sids = sids.copy(); sids[i] = v
            zw = best[2]
        hist.append(float(zw.max()))
        if hist[-1] <= min(hist):
            best_sids = sids.copy()
    return hist, edits, best_sids


def context(sids, i, k=12):
    a, b = max(0, i - k), min(len(sids), i + k + 1)
    return tok.decode(list(sids[a:b]))


# ---- choose targets: violating traces the monitor currently flags (true positives)
recs = {r["id"]: r for r in ml.read_jsonl(args.data)}
if args.scores == "compute":  # in-distribution targets: training-pool val slice (never trained on)
    recs = {k: r for k, r in recs.items() if r.get("split") == "val" and r["label"] == "violating"}
    scores = []
    for k, r in recs.items():
        trr = Trace(r["state"], r["source"])
        z = trace_max(trr, trr.sids)
        scores.append({"id": k, "label": r["label"], "task": r["source"], "strategy": r.get("risk_category"),
                       "p": float(ml.sigmoid(z / T)), "n_windows": len(trr.spans), "leak": False,
                       "n_editable": int(trr.edit.sum())})
    scores = [s for s in scores if s["n_editable"] > 0]
else:
    scores = ml.read_jsonl(args.scores)
tp = [s for s in scores if s["label"] == "violating" and s["p"] >= THR and s["n_windows"] <= args.max_windows]
by_task = {}
for s in tp:
    by_task.setdefault(s["task"], []).append(s)
rng = random.Random(args.seed)
for v in by_task.values():
    rng.shuffle(v)
targets, no_edit = [], 0
while len(targets) < args.n and any(by_task.values()):  # round-robin over tasks for diversity
    for t in sorted(by_task):
        if by_task[t] and len(targets) < args.n:
            cand = by_task[t].pop()
            if Trace(recs[cand["id"]]["state"], recs[cand["id"]]["source"]).edit.sum() == 0:
                no_edit += 1  # agent wrote no visible text outside the prefix: nothing to perturb
                continue
            targets.append(cand)
print(f"true positives available: {len(tp)}; skipped {no_edit} with zero editable tokens; attacking {len(targets)}", flush=True)

os.makedirs(os.path.dirname(args.out), exist_ok=True)
fout = open(args.out, "w")
t0 = time.time()
for k, s in enumerate(targets):
    if (time.time() - t0) / 60 > args.max_minutes:
        print("time cap reached", flush=True)
        break
    r = recs[s["id"]]
    tr = Trace(r["state"], r["source"])
    t1 = time.time()
    hist, edits, adv = attack_one(tr, rnd=args.random_baseline)
    # re-verify on retokenized text of the modified windows' tokens
    adv_text = tok.decode(list(adv))
    tr2 = Trace(adv_text, r["source"])
    z_retok = trace_max(tr2, tr2.sids)
    out = {
        "id": s["id"], "task": s["task"], "strategy": s["strategy"], "leak": s["leak"], "n_windows": len(tr.spans),
        "n_editable": int(tr.edit.sum()), "z_thr": Z_THR, "z_hist": hist, "p_hist": [float(ml.sigmoid(z / T)) for z in hist],
        "success": min(hist) < Z_THR, "swaps_used": len(edits), "z_best": min(hist),
        "z_retokenized": z_retok, "p_retokenized": float(ml.sigmoid(z_retok / T)), "success_retokenized": z_retok < Z_THR,
        "edits": [{"pos": int(i), "from": tok.decode([a]), "to": tok.decode([b]), "orig_context": context(tr.sids, i),
                   "adv_context": context(adv, i)} for (i, a, b) in edits],
        "seconds": time.time() - t1, "random_baseline": args.random_baseline, "scope": args.scope,
    }
    fout.write(json.dumps(out) + "\n"); fout.flush()
    print(f"[{k + 1}/{len(targets)}] {s['id'][:60]} win={len(tr.spans)} edit={int(tr.edit.sum())} "
          f"p {out['p_hist'][0]:.3f}->{min(out['p_hist']):.3f} swaps={len(edits)} ok={out['success']} "
          f"retok_p={out['p_retokenized']:.3f} {out['seconds']:.0f}s", flush=True)
print("done", (time.time() - t0) / 60, "min", flush=True)
