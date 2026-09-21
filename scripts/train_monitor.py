"""Phase 2: fine-tune Laya into a binary trace monitor (MPS).

Loss = soft cross-entropy over the two option-marker logits (the `loss_ce` term of Laya's own
fine-tuning notebook; the GRPO noise term is dropped, see DECISIONS.md). Encoder LR 2e-5, head LR
1e-4, AdamW, linear warmup + cosine. Stopping: fixed epoch count AND wall-clock cap. Model
selection on training-pool val AUROC. Temperature and F1-optimal threshold fitted on val.
"""
import argparse
import json
import math
import os
import random
import time

import numpy as np
import torch
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score

import monitor_lib as ml

p = argparse.ArgumentParser()
p.add_argument("--epochs", type=int, default=3)
p.add_argument("--bs", type=int, default=8)
p.add_argument("--accum", type=int, default=2)
p.add_argument("--lr_enc", type=float, default=2e-5)
p.add_argument("--lr_head", type=float, default=1e-4)
p.add_argument("--max_minutes", type=float, default=110)
p.add_argument("--max_steps", type=int, default=0, help="debug: stop after N micro-steps")
p.add_argument("--out", default="monitor/laya-monitor")
p.add_argument("--ckpt_every", type=int, default=100)
p.add_argument("--grad_ckpt", action="store_true")
args = p.parse_args()

SEED = 0
random.seed(SEED); np.random.seed(SEED); torch.manual_seed(SEED)
dev = ml.device()
src = ml.base_dir()
tok = ml.load_tokenizer(src)
enc = ml.Encoder(tok)
model, cfg = ml.load_model(src, dev)
if args.grad_ckpt:
    model.encoder.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})

pool = ml.read_jsonl("data/train_pool.jsonl")


def mk(rs):
    items = []
    for r in rs:
        it = enc.item(enc.head_tail(enc.state_ids(r["state"])))
        it["y"] = 1 if r["label"] == "violating" else 0
        it["source"] = r["source"]
        items.append(it)
    return items


train = mk([r for r in pool if r["split"] == "train"])
val = mk([r for r in pool if r["split"] == "val"])
print(f"train {len(train)}  val {len(val)}  device {dev}  head_len {len(enc.head)}  state_budget {enc.budget}", flush=True)

enc_params = [p for n, p in model.named_parameters() if n.startswith("encoder.")]
head_params = [p for n, p in model.named_parameters() if not n.startswith("encoder.")]
opt = torch.optim.AdamW([{"params": enc_params, "lr": args.lr_enc},
                         {"params": head_params, "lr": args.lr_head}], weight_decay=0.01)
steps_per_epoch = math.ceil(len(train) / (args.bs * args.accum))
total = steps_per_epoch * args.epochs
warm = max(1, int(0.06 * total))
sched = torch.optim.lr_scheduler.LambdaLR(
    opt, lambda s: (s + 1) / warm if s < warm else 0.5 * (1 + math.cos(math.pi * (s - warm) / max(1, total - warm))) * 0.95 + 0.05)


def evaluate(items):
    z = ml.logits_for(model, items, tok.pad_token_id, dev)
    y = np.array([it["y"] for it in items])
    pr = ml.sigmoid(z)
    res = {"auroc": float(roc_auc_score(y, z)), "acc@0.5": float(accuracy_score(y, pr > 0.5)),
           "nll": float(-np.mean(y * np.log(pr + 1e-9) + (1 - y) * np.log(1 - pr + 1e-9)))}
    for s in sorted({it["source"] for it in items}):
        m = np.array([it["source"] == s for it in items])
        if len(set(y[m])) == 2:
            res[f"auroc_{s}"] = float(roc_auc_score(y[m], z[m]))
    return res, z, y


os.makedirs("monitor/checkpoints", exist_ok=True)
log = open("monitor/train_log.jsonl", "a")
res0, _, _ = evaluate(val)
print("epoch 0 (zero-shot) val:", res0, flush=True)
log.write(json.dumps({"epoch": 0, "val": res0}) + "\n"); log.flush()

t0 = time.time()
best, best_ep, micro, stop = -1.0, 0, 0, False
for ep in range(1, args.epochs + 1):
    model.train()
    random.shuffle(train)
    run_loss, n = 0.0, 0
    opt.zero_grad(set_to_none=True)
    for i in range(0, len(train), args.bs):
        chunk = train[i:i + args.bs]
        with torch.autocast("cuda", dtype=torch.bfloat16, enabled=dev.type == "cuda"):
            lg, act = model(*ml.collate(chunk, tok.pad_token_id, dev))
        y = torch.tensor([it["y"] for it in chunk], device=dev)
        loss = torch.nn.functional.cross_entropy(lg.float(), y) + 0.0 * act.sum()
        (loss / args.accum).backward()
        micro += 1
        run_loss += loss.item(); n += 1
        if micro % args.accum == 0 or i + args.bs >= len(train):
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step(); sched.step(); opt.zero_grad(set_to_none=True)
        if micro % 20 == 0:
            el = (time.time() - t0) / 60
            print(f"ep {ep} micro {micro} loss {run_loss / n:.4f} lr {sched.get_last_lr()[0]:.2e} {el:.1f}min", flush=True)
            log.write(json.dumps({"epoch": ep, "micro": micro, "train_loss": run_loss / n, "min": el}) + "\n"); log.flush()
        if micro % args.ckpt_every == 0:
            torch.save({"model": model.state_dict(), "epoch": ep, "micro": micro}, "monitor/checkpoints/latest.pt")
        if (time.time() - t0) / 60 > args.max_minutes or (args.max_steps and micro >= args.max_steps):
            stop = True
            break
    res, _, _ = evaluate(val)
    res["train_loss"] = run_loss / max(1, n)
    print(f"epoch {ep} val: {res}", flush=True)
    log.write(json.dumps({"epoch": ep, "val": res, "min": (time.time() - t0) / 60}) + "\n"); log.flush()
    if res["auroc"] > best:
        best, best_ep = res["auroc"], ep
        torch.save(model.state_dict(), "monitor/checkpoints/best.pt")
    if stop:
        print("stopping: time/step cap reached", flush=True)
        break

# ---- restore best, fit temperature + threshold on val, save in laya format
model.load_state_dict(torch.load("monitor/checkpoints/best.pt", map_location=dev))
_, z, y = evaluate(val)
zt, yt = torch.tensor(z, dtype=torch.float64), torch.tensor(y, dtype=torch.float64)
logT = torch.zeros(1, dtype=torch.float64, requires_grad=True)
lb = torch.optim.LBFGS([logT], lr=0.1, max_iter=200)


def closure():
    lb.zero_grad()
    l = torch.nn.functional.binary_cross_entropy_with_logits(zt / logT.exp(), yt)
    l.backward()
    return l


lb.step(closure)
T = float(logT.exp().clamp(0.05, 20).item())
pr = ml.sigmoid(z / T)
cands = np.unique(np.round(pr, 4))
f1s = [(f1_score(y, pr >= c), c) for c in cands]
f1, thr = max(f1s)
calib = {"best_epoch": best_ep, "val_auroc": best, "temperature": T, "threshold": float(thr), "val_f1_at_thr": float(f1),
         "val_acc_at_thr": float(accuracy_score(y, pr >= thr)), "val_majority_baseline": float(max(y.mean(), 1 - y.mean())),
         "minutes": (time.time() - t0) / 60, "args": vars(args)}
cfg = dict(cfg)
cfg["temperature"] = [cfg["temperature"][0], cfg["temperature"][1], T]
cfg["temperature_by_options"] = dict(cfg.get("temperature_by_options", {}), **{"noul:2": T})
cfg["monitor"] = {"question": ml.QUESTION, **calib}
ml.save_model(model, cfg, src, args.out)
json.dump(calib, open("monitor/calibration.json", "w"), indent=1)
print("saved", args.out, calib, flush=True)
