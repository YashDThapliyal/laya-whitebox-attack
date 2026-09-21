# DECISIONS

Running log of non-trivial judgment calls made during the unsupervised run.

## Phase 0
- **Python 3.11 via uv, not system 3.14.** 3.14 is very new; 3.11 is the safest target for torch/transformers wheels.
- **Laya max_len = 512 tokens (192 reserved for question+options head).** This is a hard architectural constraint from the checkpoint config (ModernBERT supports 8k natively, but Laya was trained at 512). Agent traces — especially MRT/SHADE trajectories — are far longer than ~320 state tokens. Handled in Phase 1/2 via trace compression (see below). Did NOT raise max_len: the decision head was trained with 512 and position behaviour beyond it is untested; doing so would confound the monitor quality.
