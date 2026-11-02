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
p.add_argument("--seed", type=int, default=0)
p.add_argument("--calib_out", default="monitor/calibration.json")
p.add_argument("--work_dir", default="monitor", help="checkpoints/ and train_log.jsonl go here")
p.add_argument("--resume_dir", default=None,
               help="save the full training state here (model, optimizer, scheduler, RNG, data position) and "
                    "resume from it if present; best.pt also lives here")
p.add_argument("--ckpt_minutes", type=float, default=5.0, help="with --resume_dir: save state at least this often")
p.add_argument("--ckpt_steps", type=int, default=0, help="with --resume_dir: also save every N optimizer steps")
p.add_argument("--crash_at_step", type=int, default=0, help="test only: hard-exit (like SIGKILL) after N optimizer steps")
p.add_argument("--deterministic", action="store_true",
               help="test only: deterministic algorithms (warn_only) and a per-step batch-order log")
p.add_argument("--attn_math", action="store_true",
               help="use the deterministic math SDPA kernel instead of the fused (nondeterministic backward) ones")
args = p.parse_args()

if args.deterministic:
    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    torch.use_deterministic_algorithms(True, warn_only=True)  # warns (into the log) on ops with no deterministic kernel
if args.attn_math and torch.cuda.is_available():  # fused SDPA backward kernels are nondeterministic; math is not
    torch.backends.cuda.enable_flash_sdp(False)
    torch.backends.cuda.enable_mem_efficient_sdp(False)
    torch.backends.cuda.enable_math_sdp(True)
SEED = args.seed
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
    for idx, r in enumerate(rs):
        it = enc.item(enc.head_tail(enc.state_ids(r["state"])))
        it["y"] = 1 if r["label"] == "violating" else 0
        it["source"] = r["source"]
        it["idx"] = idx  # lets a resume restore the shuffled order exactly
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


CKPT_DIR = os.path.join(args.work_dir, "checkpoints")
os.makedirs(CKPT_DIR, exist_ok=True)
BEST = os.path.join(args.resume_dir or CKPT_DIR, "best.pt")
STATE = os.path.join(args.resume_dir, "state.pt") if args.resume_dir else None
LOG_PATH = os.path.join(args.work_dir, "train_log.jsonl")


def rng_state() -> dict:
    return {"py": random.getstate(), "np": np.random.get_state(), "torch": torch.get_rng_state(),
            "cuda": torch.cuda.get_rng_state_all() if torch.cuda.is_available() else None}


def set_rng_state(s: dict) -> None:
    random.setstate(s["py"]); np.random.set_state(s["np"]); torch.set_rng_state(s["torch"])
    if s["cuda"] is not None:
        torch.cuda.set_rng_state_all(s["cuda"])


def save_state(pos: dict) -> None:
    """Atomically write everything needed to continue exactly from this optimizer-step boundary."""
    log.flush()
    state = {"model": model.state_dict(), "opt": opt.state_dict(), "sched": sched.state_dict(), "rng": rng_state(),
             "order": [it["idx"] for it in train], "log_bytes": os.path.getsize(LOG_PATH), **pos}
    tmp = STATE + ".tmp"
    torch.save(state, tmp)
    os.replace(tmp, STATE)
    print(f"saved state ep {pos['ep']} next_i {pos['next_i']} micro {pos['micro']}", flush=True)


# position = (epoch, next chunk start, whether this epoch's shuffle already happened) plus running counters
pos = {"ep": 1, "next_i": 0, "shuffled": False, "micro": 0, "run_loss": 0.0, "n": 0, "best": -1.0, "best_ep": 0,
       "elapsed_min": 0.0, "stop": False}
resumed = None
if STATE:
    os.makedirs(args.resume_dir, exist_ok=True)
    if os.path.exists(STATE):
        # load on CPU: RNG states must stay CPU ByteTensors; load_state_dict moves weights and optimizer state
        resumed = torch.load(STATE, map_location="cpu", weights_only=False)
if resumed:
    model.load_state_dict(resumed["model"]); opt.load_state_dict(resumed["opt"]); sched.load_state_dict(resumed["sched"])
    by_idx = {it["idx"]: it for it in train}
    train = [by_idx[i] for i in resumed["order"]]
    pos = {k: resumed[k] for k in pos}
    with open(LOG_PATH, "r+") as fh:  # drop log lines written after the checkpoint (those steps get replayed)
        fh.truncate(resumed["log_bytes"])
    set_rng_state(resumed["rng"])
    print(f"RESUMED from {STATE}: ep {pos['ep']} next_i {pos['next_i']} micro {pos['micro']}", flush=True)
    del resumed
log = open(LOG_PATH, "a")
order_log = open(os.path.join(args.work_dir, "order_log.jsonl"), "a", buffering=1) if args.deterministic else None
if pos["micro"] == 0 and pos["ep"] == 1:
    res0, _, _ = evaluate(val)
    print("epoch 0 (zero-shot) val:", res0, flush=True)
    log.write(json.dumps({"epoch": 0, "val": res0}) + "\n"); log.flush()

t0 = time.time() - 60 * pos["elapsed_min"]
loop_seconds, loop_steps = 0.0, 0  # training-loop time without evals (this process only), for the kernel timing
last_save = time.time()
best, best_ep, micro, stop = pos["best"], pos["best_ep"], pos["micro"], pos["stop"]
for ep in range(pos["ep"], args.epochs + 1):
    model.train()
    mid_epoch = ep == pos["ep"] and pos["shuffled"]
    if not mid_epoch:
        random.shuffle(train)
    run_loss, n = (pos["run_loss"], pos["n"]) if mid_epoch else (0.0, 0)
    ep_t, ep_micro0 = time.time(), micro
    start = (len(train) if pos["stop"] else pos["next_i"]) if mid_epoch else 0  # stopped: go straight to eval
    opt.zero_grad(set_to_none=True)
    for i in range(start, len(train), args.bs):
        chunk = train[i:i + args.bs]
        if args.deterministic:  # test only: which items each step saw (a resumed run must replay the same order)
            order_log.write(json.dumps({"micro": micro + 1, "ids": [it["idx"] for it in chunk]}) + "\n")
        with torch.autocast("cuda", dtype=torch.bfloat16, enabled=dev.type == "cuda"):
            lg, act = model(*ml.collate(chunk, tok.pad_token_id, dev))
        y = torch.tensor([it["y"] for it in chunk], device=dev)
        loss = torch.nn.functional.cross_entropy(lg.float(), y) + 0.0 * act.sum()
        (loss / args.accum).backward()
        micro += 1
        run_loss += loss.item(); n += 1
        boundary = micro % args.accum == 0 or i + args.bs >= len(train)
        if boundary:
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step(); sched.step(); opt.zero_grad(set_to_none=True)
        if micro % 20 == 0:
            el = (time.time() - t0) / 60
            print(f"ep {ep} micro {micro} loss {run_loss / n:.4f} lr {sched.get_last_lr()[0]:.2e} {el:.1f}min", flush=True)
            log.write(json.dumps({"epoch": ep, "micro": micro, "train_loss": run_loss / n, "min": el}) + "\n"); log.flush()
        if micro % args.ckpt_every == 0:
            torch.save({"model": model.state_dict(), "epoch": ep, "micro": micro}, os.path.join(CKPT_DIR, "latest.pt"))
        if (time.time() - t0) / 60 > args.max_minutes or (args.max_steps and micro >= args.max_steps):
            stop = True
        due = time.time() - last_save >= 60 * args.ckpt_minutes or (args.ckpt_steps and micro % args.ckpt_steps == 0)
        if STATE and boundary and due:
            save_state({"ep": ep, "next_i": i + args.bs, "shuffled": True, "micro": micro, "run_loss": run_loss,
                        "n": n, "best": best, "best_ep": best_ep, "elapsed_min": (time.time() - t0) / 60,
                        "stop": stop})
            last_save = time.time()
        if args.crash_at_step and micro == args.crash_at_step:
            print(f"crash_at_step {micro}: hard exit", flush=True)
            os._exit(137)
        if stop:
            break
    if dev.type == "cuda":
        torch.cuda.synchronize()
    loop_seconds += time.time() - ep_t
    loop_steps += micro - ep_micro0
    res, _, _ = evaluate(val)
    res["train_loss"] = run_loss / max(1, n)
    print(f"epoch {ep} val: {res}", flush=True)
    log.write(json.dumps({"epoch": ep, "val": res, "min": (time.time() - t0) / 60}) + "\n"); log.flush()
    if res["auroc"] > best:
        best, best_ep = res["auroc"], ep
        torch.save(model.state_dict(), BEST + ".tmp")
        os.replace(BEST + ".tmp", BEST)
    if stop:
        print("stopping: time/step cap reached", flush=True)
        break
    if STATE:
        save_state({"ep": ep + 1, "next_i": 0, "shuffled": False, "micro": micro, "run_loss": 0.0, "n": 0,
                    "best": best, "best_ep": best_ep, "elapsed_min": (time.time() - t0) / 60, "stop": False})
        last_save = time.time()

# ---- restore best, fit temperature + threshold on val, save in laya format
model.load_state_dict(torch.load(BEST, map_location=dev))
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
         "minutes": (time.time() - t0) / 60, "attn": "math" if args.attn_math else "fused",
         "train_loop_seconds": loop_seconds, "train_loop_steps": loop_steps, "args": vars(args)}
cfg = dict(cfg)
cfg["temperature"] = [cfg["temperature"][0], cfg["temperature"][1], T]
cfg["temperature_by_options"] = dict(cfg.get("temperature_by_options", {}), **{"noul:2": T})
cfg["monitor"] = {"question": ml.QUESTION, **calib}
ml.save_model(model, cfg, src, args.out)
json.dump(calib, open(args.calib_out, "w"), indent=1)
print("saved", args.out, calib, flush=True)
