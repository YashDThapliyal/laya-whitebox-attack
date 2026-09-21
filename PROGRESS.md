# PROGRESS

Append-only log of phase status.

- 2026-09-21 00:19 — Phase 0 STARTED (env setup)
- 2026-09-21 00:23 — Phase 0 DONE. Python 3.11 venv (uv; system python is 3.14, too new for a safe torch pin), laya 0.3.4, torch 2.14, transformers 5.17. MPS available. Laya English checkpoint (ModernBERT-large + 2-layer decision head, 421.3M params) loads in ~200s first time (download), forward pass ~30ms warm on MPS. Toy noul question gives sensible direction (rm -rf: 0.30, weather: 0.11). Repos for R-Judge, ToolEmu, InjecAgent, laya, scaleapi/mrt cloned into raw/ (gitignored).
