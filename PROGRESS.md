# PROGRESS

Append-only log of phase status.

- 2026-09-21 00:19 — Phase 0 STARTED (env setup)
- 2026-09-21 00:23 — Phase 0 DONE. Python 3.11 venv (uv; system python is 3.14, too new for a safe torch pin), laya 0.3.4, torch 2.14, transformers 5.17. MPS available. Laya English checkpoint (ModernBERT-large + 2-layer decision head, 421.3M params) loads in ~200s first time (download), forward pass ~30ms warm on MPS. Toy noul question gives sensible direction (rm -rf: 0.30, weather: 0.11). Repos for R-Judge, ToolEmu, InjecAgent, laya, scaleapi/mrt cloned into raw/ (gitignored).
- 2026-09-21 00:23 — Phase 1 STARTED (data acquisition & normalization)
- 2026-09-21 00:29 — Phase 1 DONE. train pool 1,853 records (R-Judge 571, InjecAgent 1,000 contrastive pairs, ToolEmu 288 synthetic), 15% group-wise val. Held-out MRT/SHADE: 1,448 traces (371 compliant / 1,077 violating; 410 side-task-failed excluded). MRT download hit HF 429 rate limits (unauthenticated) but completed via retries in ~10 min. ToolEmu has no trajectories (synthetic pseudo-traces used, see DECISIONS).
- 2026-09-21 00:30 — Phase 2 STARTED (fine-tune monitor)
- 2026-09-21 00:52 — Phase 2 DONE. Local MPS training infeasible (10 GB swap, <20 steps in 10 min) → moved to Colab A100. Discarded first run (R-Judge val split by record was leaky: 0.994 R-Judge val AUROC). Final run (R-Judge split by scenario file): 3 epochs, 1.7 min, best epoch 3, val AUROC 0.994 (zero-shot 0.737), val acc 0.961 @ F1-opt thr 0.409 vs majority 0.506. Per-source val AUROC: InjecAgent 1.00, ToolEmu 1.00, R-Judge 0.77. Go/no-go (beat majority on val) passed.
