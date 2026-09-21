# monitor/

Fine-tuned Laya trace monitor (base: `convaiinnovations/laya`, English, ModernBERT-large + 2-layer decision head, 421M).

- `rl_agent_config.json` — config of the saved checkpoint (includes the monitor question, fitted temperature, val threshold).
- `calibration.json` — best epoch, val AUROC, temperature T, F1-optimal threshold on the training-pool val slice.
- `train_log.jsonl` — per-20-step train loss and per-epoch val metrics (epoch 0 = zero-shot).
- `train_v0_rjudge_by_record.out` — log of the discarded first run (leaky R-Judge val split; see DECISIONS.md).
- `laya-monitor/` — the checkpoint in `laya.load()`-compatible layout (`model.safetensors` is 1.7 GB and gitignored).

Trained on Colab A100 (bf16) in ~1.7 min: `PYTHONPATH=scripts python scripts/train_monitor.py --epochs 3 --bs 16 --accum 1`.
Load: `laya.load("monitor/laya-monitor")` then ask the `noul` question in `scripts/monitor_lib.py::QUESTION`,
or use `monitor_lib.load_model` + `Encoder.windows` for long traces (max over windows).
