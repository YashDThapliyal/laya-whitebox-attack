# PROGRESS

Append-only log of phase status.

- 2026-09-21 00:19 — Phase 0 STARTED (env setup)
- 2026-09-21 00:23 — Phase 0 DONE. Python 3.11 venv (uv; system python is 3.14, too new for a safe torch pin), laya 0.3.4, torch 2.14, transformers 5.17. MPS available. Laya English checkpoint (ModernBERT-large + 2-layer decision head, 421.3M params) loads in ~200s first time (download), forward pass ~30ms warm on MPS. Toy noul question gives sensible direction (rm -rf: 0.30, weather: 0.11). Repos for R-Judge, ToolEmu, InjecAgent, laya, scaleapi/mrt cloned into raw/ (gitignored).
- 2026-09-21 00:23 — Phase 1 STARTED (data acquisition & normalization)
- 2026-09-21 00:29 — Phase 1 DONE. train pool 1,853 records (R-Judge 571, InjecAgent 1,000 contrastive pairs, ToolEmu 288 synthetic), 15% group-wise val. Held-out MRT/SHADE: 1,448 traces (371 compliant / 1,077 violating; 410 side-task-failed excluded). MRT download hit HF 429 rate limits (unauthenticated) but completed via retries in ~10 min. ToolEmu has no trajectories (synthetic pseudo-traces used, see DECISIONS).
