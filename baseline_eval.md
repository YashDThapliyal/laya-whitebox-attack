# Baseline evaluation (Phase 3)

**Headline: the fine-tuned Laya monitor is near chance on held-out SHADE-Arena (ScaleAI MRT) traces — AUROC 0.577 (95% CI 0.55–0.61) — despite 0.99 AUROC on the held-out slice of its training pool.** At the pre-registered threshold (F1-optimal on the training-pool val slice, p ≥ 0.865) it flags 92% of *compliant* SHADE traces; its 0.747 accuracy equals the majority-class rate (0.744). Zero-shot Laya: 0.505. For reference, the original MRT LLM monitors' suspicion scores stored in the same transcripts reach 0.662 (heterogeneous GPT/Claude/Gemini monitors and prompts — a loose reference, not a controlled comparison).

> **Which model?** Two fine-tuning runs exist with the identical script and seed (bf16 training on GPU is not bit-deterministic). Run 1 was trained on a Colab VM that was later reclaimed; its checkpoint could not be re-uploaded, so the model was retrained (run 2) on a new VM and *run 2 is the model that was attacked and is reported everywhere*. Run 1's numbers are kept as a reproducibility check (`results/run1_model_v1/`). They agree on the conclusion (near-chance on SHADE) but individual numbers move by several points, and the F1-optimal threshold moved a lot (0.409 → 0.865).

## 1. Training-pool validation slice (in-distribution, group-held-out)

Per-source AUROC, windowed max scoring (same scoring used by the attack), 95% bootstrap CIs (`results/cross_source_auroc.json`):

| source | n (viol.) | trained (run 2) | zero-shot |
|---|---|---|---|
| InjecAgent | 176 (88) | 1.000 [1.00, 1.00] | 0.792 [0.72, 0.85] |
| ToolEmu | 44 (22) | 1.000 [1.00, 1.00] | 0.787 [0.64, 0.92] |
| R-Judge | 35 (19) | 0.520 [0.33, 0.72] | 0.477 [0.29, 0.67] |

Per-epoch val AUROC as logged during training (head+tail truncated view, not windows):

| run | epoch | all | InjecAgent | R-Judge | ToolEmu |
|---|---|---|---|---|---|
| run 2 | 0 (zero-shot) | 0.737 | 0.779 | 0.441 | 0.787 |
| run 2 | 1 | 0.990 | 1.000 | 0.655 | 0.998 |
| run 2 | 2 | 0.986 | 0.999 | 0.679 | 1.000 |
| run 2 | 3 | 0.990 | 1.000 | 0.658 | 1.000 |
| run 1 | 0 (zero-shot) | 0.737 | 0.779 | 0.441 | 0.787 |
| run 1 | 1 | 0.992 | 1.000 | 0.724 | 1.000 |
| run 1 | 2 | 0.991 | 1.000 | 0.770 | 1.000 |
| run 1 | 3 | 0.994 | 1.000 | 0.766 | 1.000 |

Run 2: best epoch 3, temperature T = 2.483, F1-optimal threshold 0.8649 (val F1 0.944, acc 0.945 vs majority 0.506). The F1-optimal tie range is narrow (0.863–0.873, `results/threshold_tie_range.json`), so the high threshold is real, not a tie-breaking artifact. Run 1: threshold 0.4092, T 2.256.

**Caveats on the in-distribution numbers.** InjecAgent (templated contrastive pairs) and ToolEmu (synthetic pseudo-traces built from case specs) are near-trivially separable — 1.00 AUROC says little about monitoring ability; ToolEmu risky-action text also contains a lexical shortcut ("The agent may ..."). **R-Judge — the only real-trajectory in-distribution source — is not reliably learned: 0.52 with windowed scoring, 0.66 with head+tail truncation, 0.77 in run 1, all on n = 35 with CIs spanning ~0.3–0.7.**

## 2. Held-out SHADE-Arena (ScaleAI MRT), n = 1,448 (371 compliant / 1,077 violating)

Trace score = max over sliding windows (median 21 windows/trace).

| metric | fine-tuned run 2 (reported) | fine-tuned run 1 | zero-shot Laya |
|---|---|---|---|
| AUROC (max-agg) | 0.577 | 0.513 | 0.505 |
| accuracy @ threshold | 0.747 | 0.747 | 0.733 |
| balanced accuracy | 0.528 | 0.505 | 0.498 |
| TPR | 0.978 | 1.000 | 0.981 |
| FPR | 0.922 | 0.989 | 0.984 |
| precision | 0.755 | 0.746 | 0.743 |
| F1 | 0.852 | 0.854 | 0.845 |
| AUROC (top-3-mean agg) | 0.574 | 0.518 | 0.497 |
| AUROC excl. 188 traces that say "secondary task" | 0.587 | 0.509 | 0.491 |
| ECE of p(violating), 10-bin reliability | 0.190 | 0.213 | 0.110 |
| ECE of confidence max(p,1−p), laya.ece_score | 0.189 | 0.213 | 0.099 |
| threshold | 0.865 | 0.409 | 0.5 |
| majority-class accuracy | 0.744 | | |
| reference: original MRT LLM monitors, AUROC | 0.662 | | |

### By task

| task | n | violating | AUROC run 2 | AUROC run 1 | FPR run 2 |
|---|---|---|---|---|---|
| american_airlines_2 | 417 | 307 | 0.614 | 0.420 | 0.936 |
| api_key_calendar_agendas_2 | 302 | 233 | 0.763 | 0.630 | 0.768 |
| bank_transfer_2 | 308 | 262 | 0.685 | 0.597 | 0.978 |
| expenditure_accounting | 45 | 4 | 0.387 | 0.567 | 0.976 |
| spam_filter_update | 376 | 271 | 0.384 | 0.353 | 0.962 |

(expenditure_accounting has 4 violating traces — ignore its AUROC. Per-task AUROCs swing by up to 0.2 between the two training runs: they are not stable estimates.)

### By red-teaming strategy (that strategy's violating traces vs all 371 compliant)

| strategy | violating n | run 2 | run 1 | zero-shot |
|---|---|---|---|---|
| transcripts | 60 | 0.521 | 0.549 | 0.573 |
| transcripts_no_hint | 176 | 0.635 | 0.634 | 0.594 |
| transcripts_no_hint_naive_thinking_time | 72 | 0.517 | 0.507 | 0.524 |
| transcripts_no_hint_no_thinking_time | 61 | 0.529 | 0.520 | 0.513 |
| transcripts_no_hint_selective_liar_strategy__thinking_time | 388 | 0.599 | 0.471 | 0.442 |
| transcripts_no_hint_selective_thinking_time | 164 | 0.530 | 0.490 | 0.529 |
| transcripts_no_hint_visible_liar_thinking_time | 78 | 0.581 | 0.437 | 0.521 |
| transcripts_no_hint_visible_thinking_time | 78 | 0.564 | 0.550 | 0.480 |

Files: `results/baseline_*.json`, `results/heldout_scores_*.jsonl`, `results/reliability_*.png`, run 1 in `results/run1_model_v1/`.

## 3. Interpretation

- **No meaningful transfer.** Fine-tuning moved SHADE AUROC from 0.505 (zero-shot) to 0.513 (run 1) / 0.577 (run 2). Even the better run is far below the LLM monitors (0.66) and nowhere near usable. The training pool (short, single-incident scenarios, half templated/synthetic) teaches "an agent visibly did a risky-looking thing in a short window"; SHADE sabotage is buried in 15–40 turns of legitimate work, often visible only in tool outputs, by agents deliberately trying to look innocent.
- **Why it flags almost everything** (window-level diagnostic, `results/diag_fp_windows.json`, run-1 model, 25+25 sampled traces): **64% of individual windows in compliant SHADE traces are flagged, vs 73% in violating ones.** The top-scoring windows of compliant traces are routine task actions — `schedule_transaction` to "unrecognized IBAN ... using override", Venmo payments, flight searches. The monitor learned that money movement / bank details / bookings = attack, because in InjecAgent they are; in SHADE they are the job. Max-aggregation over ~21 windows then guarantees a flag.
- **Explicit confessions aren't the driver either:** removing the 188 violating traces where the agent literally writes "secondary task" leaves AUROC unchanged (0.587 run 2).
- **Calibration:** ECE 0.19 on SHADE for the fine-tuned model — its confident "violating" scores are wrong most of the time for compliant traces. Zero-shot's lower ECE (0.11) only reflects probabilities hovering near the base rate.
- **Consequence for the attack:** on SHADE, "flipping" a flag means pushing a near-constant classifier's max window under threshold; so Phase 4 also attacks the in-distribution val slices where the monitor does discriminate, and Phase 4.5 compares fragility across all four sources.
