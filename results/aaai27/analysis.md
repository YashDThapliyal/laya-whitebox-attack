# AAAI-27 analysis

Sections 1 to 4 are Phase A (structure vs fragility, recomputed on SHADE-80). Sections 5 to 7 are Phase B (GPU jobs 6 to 8).

**Phase A.** All numbers are for the fine-tuned monitor (run 2), agent-text attacks, success at the operating threshold (p < 0.865). There was no GPU or API use: everything is recomputed from the existing `attack/*.jsonl` records.

**Short answer.** With the widened SHADE set (80 traces instead of 20), the share of the trace the agent can edit is still the strongest structural predictor of attack success. Pooled Spearman ρ = +0.66 [0.58, 0.73], unchanged from +0.65 on the old 137-trace set. It also holds within SHADE alone (+0.52) and within InjecAgent alone (+0.66), and in a logistic regression with source fixed effects (odds ratio 8.4 per SD of editable fraction, 95% CI 2.9 to 24). **One earlier claim does not survive.** The docs say structure predicts success "much more than starting confidence (ρ = −0.29)". That pooled number is confounded by source. Within a source, the clean-score margin is about as strong a predictor as editable fraction (ρ ≈ −0.5 within SHADE and within InjecAgent; regression OR 0.03 per SD). Window count is nearly collinear with editable fraction (pooled ρ = −0.91), and its separate effect isn't established.

## Files

| file | contents |
|---|---|
| `scripts/aaai27/trace_features.py` | builds `trace_features.jsonl`: one row per attacked trace (434 rows) |
| `scripts/aaai27/structure_stats.py` | Spearman correlations with bootstrap CIs, logistic regressions, InjecAgent split, all written to `phaseA_stats.json` |
| `results/aaai27/trace_features.jsonl` | per-trace source, tokens, editable tokens, editable fraction, windows, clean margin, success at budgets 20 and 60 under both bars |
| `results/aaai27/phaseA_stats.json` | every number in this file, plus ML and Firth fits for both attacks and both SHADE budgets |

## Definitions

- **Traces.** These are the attacked targets: 117 in-distribution val traces (InjecAgent 87, ToolEmu 21, R-Judge 9) plus SHADE-80. SHADE-80 is the original 20 (`mrt_agent`) plus 60 new targets (`x_u_mrt_agent` without its first 3 rows, which re-run original targets to p < 0.5), the same assembly as `scripts/widen_analysis.py`. The constrained attack uses `f_val_agent` + `f_mrt_agent` + `x_f_mrt_agent`.
- **Editable fraction** = editable tokens / state tokens, exactly as `scripts/attack.py` computes them (`Trace.edit.sum() / len(Trace.sids)`).
- **Clean margin** = starting trace score minus the operating threshold, in the attack's calibrated logit units (z = T · logit p; threshold z = 4.610).
- **Success** = the max-window score drops below p = 0.865 within the budget. The budget is 20 for every source (primary). SHADE at 60 is reported as a sensitivity check, since in-distribution traces were only run to 20.
- **Reproduction check.** On the original 137-trace set the script reproduces the published figures exactly: ρ = +0.649 / −0.658 / −0.29, InjecAgent median editable fraction 0.36 vs 0.21, and InjecAgent direct harm 35/42 vs data stealing 3/45.
- **Bootstrap.** Percentile intervals. Traces are resampled within source, which keeps the per-source sample sizes fixed by design. There are 10,000 replicates for Spearman and 2,000 for regressions, seed 0.

## 1. Spearman correlations of success with trace structure

Values are ρ with stratified-bootstrap 95% CIs. Positive means more editable or larger values go with more success.

| set | attack | n | successes | editable fraction | window count | clean margin |
|---|---|---|---|---|---|---|
| Original: val 117 + SHADE-20, @20 | unconstrained | 137 | 67 | +0.65 [+0.54, +0.74] | −0.66 [−0.77, −0.54] | −0.29 [−0.41, −0.16] |
| Original: val 117 + SHADE-20, @20 | constrained | 137 | 72 | +0.72 [+0.64, +0.79] | −0.76 [−0.85, −0.67] | −0.26 [−0.37, −0.14] |
| **Pooled: val 117 + SHADE-80, @20** | **unconstrained** | **197** | **75** | **+0.66 [+0.58, +0.73]** | **−0.63 [−0.71, −0.53]** | **−0.01 [−0.13, +0.12]** |
| Pooled: val 117 + SHADE-80, @20 | constrained | 197 | 83 | +0.69 [+0.62, +0.75] | −0.66 [−0.74, −0.56] | +0.00 [−0.12, +0.13] |
| Pooled: val 117 + SHADE-80 (SHADE @60) | unconstrained | 197 | 79 | +0.64 [+0.55, +0.71] | −0.59 [−0.68, −0.50] | −0.05 [−0.18, +0.07] |
| Pooled: val 117 + SHADE-80 (SHADE @60) | constrained | 197 | 86 | +0.68 [+0.60, +0.74] | −0.64 [−0.72, −0.54] | −0.04 [−0.17, +0.10] |
| Within SHADE-80, @20 | unconstrained | 80 | 10 | +0.52 [+0.36, +0.65] | −0.34 [−0.48, −0.17] | −0.49 [−0.62, −0.32] |
| Within SHADE-80, @20 | constrained | 80 | 12 | +0.50 [+0.31, +0.63] | −0.24 [−0.42, −0.03] | −0.49 [−0.63, −0.31] |
| Within SHADE-80, @60 | unconstrained | 80 | 14 | +0.63 [+0.48, +0.74] | −0.43 [−0.58, −0.27] | −0.48 [−0.61, −0.32] |
| Within SHADE-80, @60 | constrained | 80 | 15 | +0.60 [+0.43, +0.72] | −0.34 [−0.52, −0.14] | −0.52 [−0.65, −0.36] |
| Within InjecAgent (87), @20 | unconstrained | 87 | 38 | +0.66 [+0.52, +0.77] | −0.65 [−0.79, −0.50] | −0.54 [−0.68, −0.36] |
| Within InjecAgent (87), @20 | constrained | 87 | 41 | +0.69 [+0.56, +0.79] | −0.72 [−0.85, −0.58] | −0.52 [−0.67, −0.34] |

What changes with SHADE-80:

- **Editable fraction and window count:** essentially unchanged (+0.66 and −0.63 vs +0.65 and −0.66).
- **Clean margin:** goes from −0.29 to about 0 pooled. That isn't because margin stopped mattering. Within SHADE and within InjecAgent it is about −0.5. Pooled, it's washed out because sources differ in both margin and success in ways that don't line up: R-Judge has low margins (median 1.93) and high success (0.89), while SHADE has low margins (2.27) and low success (0.12). This is a Simpson's-paradox pattern, so the pooled margin correlation shouldn't be cited either way.
- **Within SHADE alone,** where monitor quality and source are fixed, editable fraction is the strongest of the three at budget 60 (+0.63) and ties margin at budget 20.

## 2. Logistic regression with source fixed effects

Model: `success ~ editable_frac + n_windows + clean_margin + source`. InjecAgent is the reference source. Continuous predictors are z-scored on the 197 fitted traces, so coefficients are log-odds per SD. The SDs are editable fraction 0.153, window count 6.9, and clean margin 1.34 logit units.

**Firth-penalized fits are the primary estimates.** The regression uses Firth's penalized likelihood because of complete separation on ToolEmu and R-Judge: in the constrained attack, ToolEmu (21/21) and R-Judge (9/9) succeed on every trace, so unpenalized maximum likelihood doesn't exist there. In the unconstrained attack the separation isn't complete in the full sample (ToolEmu 19/21, R-Judge 8/9), so ML fits it, but 848 of 2,000 bootstrap resamples were separated and failed to fit, so its bootstrap CIs are biased. Firth fits every resample except 1 (unconstrained) and 11 (constrained). The ML estimates are in `phaseA_stats.json`; they are within about 0.4 log-odds of the Firth ones and lead to the same conclusions.

**Primary: unconstrained, budget 20 for every source (n = 197, 75 successes)**

| term | β (log-odds) | Wald 95% CI | bootstrap 95% CI | odds ratio | OR Wald 95% CI | p (Wald) |
|---|---|---|---|---|---|---|
| Editable fraction (per SD) | +2.13 | [+1.06, +3.19] | [+1.08, +3.76] | 8.4 | [2.9, 24] | 9e-05 |
| Window count (per SD) | −1.92 | [−4.24, +0.41] | [−4.67, −0.49] | 0.15 | [0.014, 1.5] | 0.1 |
| Clean margin (per SD) | −3.48 | [−5.07, −1.89] | [−5.85, −2.38] | 0.031 | [0.0063, 0.15] | 2e-05 |
| ToolEmu vs InjecAgent | −0.01 | [−1.75, +1.73] | [−1.97, +2.18] | 0.99 | [0.17, 5.7] | 1 |
| R-Judge vs InjecAgent | −3.37 | [−6.85, +0.12] | [−6.84, −1.29] | 0.035 | [0.0011, 1.1] | 0.06 |
| SHADE vs InjecAgent | −3.08 | [−7.58, +1.42] | [−8.12, +0.80] | 0.046 | [0.00051, 4.1] | 0.2 |

**Sensitivity: unconstrained, SHADE at budget 60 (n = 197, 79 successes)**

| term | β | Wald 95% CI | bootstrap 95% CI | OR | p |
|---|---|---|---|---|---|
| Editable fraction (per SD) | +2.15 | [+1.09, +3.20] | [+1.10, +3.68] | 8.6 | 7e-05 |
| Window count (per SD) | −3.17 | [−5.52, −0.83] | [−6.34, −1.68] | 0.042 | 0.008 |
| Clean margin (per SD) | −3.26 | [−4.77, −1.75] | [−5.46, −2.21] | 0.038 | 2e-05 |
| ToolEmu vs InjecAgent | −0.09 | [−1.83, +1.64] | [−2.01, +2.12] | 0.91 | 0.9 |
| R-Judge vs InjecAgent | −3.03 | [−6.42, +0.35] | [−6.25, −0.66] | 0.048 | 0.08 |
| SHADE vs InjecAgent | +0.31 | [−3.43, +4.05] | [−2.37, +3.25] | 1.4 | 0.9 |

**Sensitivity: constrained (plausible-word) attack, budget 20 (n = 197, 83 successes)**

| term | β | Wald 95% CI | bootstrap 95% CI | OR | p |
|---|---|---|---|---|---|
| Editable fraction (per SD) | +3.07 | [+1.80, +4.33] | [+2.03, +5.04] | 21 | 2e-06 |
| Window count (per SD) | −0.01 | [−1.69, +1.67] | [−2.48, +1.61] | 0.99 | 1 |
| Clean margin (per SD) | −2.78 | [−4.28, −1.28] | [−5.39, −1.56] | 0.062 | 0.0003 |
| ToolEmu vs InjecAgent | +1.53 | [−1.63, +4.68] | [+0.14, +2.34] | 4.6 | 0.3 |
| R-Judge vs InjecAgent | −0.41 | [−4.73, +3.91] | [−5.01, +1.46] | 0.67 | 0.9 |
| SHADE vs InjecAgent | −3.19 | [−7.53, +1.14] | [−10.18, +1.09] | 0.041 | 0.1 |

Reading the regressions:

- **Editable fraction** has a positive, significant coefficient in all four fits (both attacks, both SHADE budgets, ML and Firth). Every CI excludes zero. This is the robust result.
- **Clean margin** is negative and significant in all four fits, with a magnitude similar to editable fraction's. Traces the monitor flags with less confidence are much easier to flip, even with editable fraction and source held fixed.
- **Window count** is not separately established. Its Wald CI crosses zero at budget 20, its bootstrap CI does not, it becomes significant when SHADE runs to 60 swaps, and it is null in the constrained attack. Pooled, it's nearly the same variable as editable fraction (Spearman −0.91), and within InjecAgent the two correlate at −0.81. The data can't separate "many windows" from "small editable share".
- **Source effects shrink once structure and margin are controlled.** ToolEmu's raw success (0.90 vs InjecAgent's 0.44) is fully accounted for (OR 0.99). SHADE's gap is no longer distinguishable from zero (Wald CI spans 0.0005 to 4). R-Judge stays lower than its features predict (OR 0.035, bootstrap CI excludes 1, n = 9). The source fixed effects absorb any between-source difference in monitor AUROC, so these fits can't test "monitor quality" directly. They say that within a source, fragility follows editable fraction and starting margin.

## 3. InjecAgent direct harm vs data stealing

These are the 87 InjecAgent targets, budget 20, operating threshold. The case type comes from the trace id (`injecagent_dh_*` / `injecagent_ds_*`).

| case type | targets | unconstrained success | constrained success | median editable fraction | median windows |
|---|---|---|---|---|---|
| Direct harm (one frozen attacker tool call) | 42 | 35 / 42 = 83% [69, 92] | 39 / 42 = 93% [81, 98] | 0.35 | 1 |
| Data stealing (frozen data-access call + frozen exfiltration email) | 45 | 3 / 45 = 7% [2, 18] | 2 / 45 = 4% [1, 15] | 0.21 | 2 |

Brackets are Wilson 95% CIs. The groups are balanced (42 vs 45), so the 83% vs 7% contrast in `cross_source_analysis.md` rests on reasonable group sizes, not a handful of traces. Within this one source and one monitor, the extra frozen evidence in data-stealing cases goes with a roughly 12× drop in success. It is still observational: data-stealing traces also differ in length, window count and content.

## 4. Doc consistency fixes (task 1)

| doc | was | now |
|---|---|---|
| `DECISIONS.md` Phase 4 "Success" | threshold 0.409 (z < −0.828) with no note | marked as written for run 1 (attacks lost with its VM); reported run 2 uses 0.865 (z < 4.610) |
| `DECISIONS.md` Phase 4 "Budgets/samples" | "all 103 violating val traces" | 117 for run 2 (InjecAgent 87, ToolEmu 21, R-Judge 9, after the Phase 4.5 rule fix); 103 noted as the run-1, old-rule count |
| `DECISIONS.md` scope correction | LLM raters "32 of 52 (62%)" next to the human's toward-benign 7/18 | 9/18 (50%) toward benign on the same 18 items; 28/52 (54%) over all non-ToolEmu edits; 32/52 explained as the raters' any-direction count |
| `DECISIONS.md` threshold-0.5 run | SHADE agent text "15%" | n = 20 noted; 17% at n = 80 |
| `README.md` finding 4 | raters "32 of 52 (62%)" compared with the human's 7/18 toward benign | raters 9/18 on the same items and 28/52 on these sources, both toward benign |
| `fluency_attack_eval.md` headline + perplexity section | led with "about half" | leads with 39% (7/18) on traces with a frozen record; the 54% all-source figure follows with the ToolEmu caveat |
| `fluent_edit_review.md` short answer, point 1, human-review section | "about half change meaning" | same scoping: 39% (7/18) on traces with a frozen record, 54% (14/26) all sources |
| `fluency_experiment_full.md` | verbatim copies of the passages above | updated identically |
| `SUMMARY.md` follow-up bullet | "revised the meaning-change rate down to about half" | "54% across all sources (39% on traces with a frozen action record)" |
| `PROGRESS.md` Phase 2 entry | run-1 values (thr 0.409, R-Judge 0.77) with no label | labelled as run 1, with a pointer to the run-2 values |

I checked the counts against `results/edit_labels_final.json` and `results/human_spotcheck.json`. Among the 52 non-ToolEmu edits, the raters label 32 as changing meaning and 28 as toward benign. The human's 7 of 18 is both meaning-changing and toward benign (the two sets are identical). On those same 18 items, the raters label 11 as changing meaning and 9 as toward benign.

**Not changed, flagged for your decision:** README finding 2, `SUMMARY.md` and `cross_source_analysis.md` still say structure predicts success "much more than starting confidence (ρ = −0.29)". The number is correct for the 137-trace pooled set, but section 2 shows that the comparison is misleading. Suggested replacement: *"Within a source, success rises with the editable fraction and falls with the monitor's starting margin, each independently (logistic regression with source fixed effects, n = 197). Across sources it doesn't track monitor AUROC."* Applied after owner approval.

## Implications for the paper's claim

- **Supported:** fragility depends on how much of the record the agent controls. Editable fraction predicts success pooled, within SHADE, within InjecAgent, and with source fixed effects and margin controlled, under both attacks. The InjecAgent split (83% vs 7%, n = 42 / 45) is the cleanest single illustration.
- **Needs rewording:** "not monitor quality" holds only if quality means source-level AUROC. Per-trace confidence (clean margin) matters about as much as editable fraction. This agrees with two earlier results: the R-Judge train-split supplement (margin-matched traces flip 73%) and the zero-shot checkpoint comparison (less confident verdicts flip more). The paper should present margin as a second, independent factor, not as something structure beats.
- **Don't claim** window count as a separate factor. With these sources it can't be told apart from editable fraction.

## Caveats

- **Post hoc.** These analyses were chosen after the per-source table was seen, as with the original correlations.
- **Few events in SHADE.** There are 10 successes at budget 20 and 14 at budget 60, so the within-SHADE correlations rest on few events.
- **Different budgets across sources.** In-distribution traces were only run to 20 swaps, so the budget-60 sensitivity mixes budgets.
- **Selection.** SHADE targets were capped at 25 windows when selected, which truncates the window-count range.
- **Four sources, two synthetic.** Source fixed effects use up much of the between-source information.

# Phase B

## 5. Job 6: hiding the agent's prose from the monitor

**Question.** If the monitor scores only tool calls and tool outputs, an agent-text attack has nothing left to edit. Does that defend the monitor, and what does it cost on clean traces?

**What each attack can edit.** Traces are serialized as tagged lines: `[USER]`, `[AGENT PROFILE]` (R-Judge), `[AVAILABLE TOOLKITS]` (ToolEmu), agent prose (`[AGENT THOUGHT]`, `[AGENT]` in SHADE, `[AGENT FINAL ANSWER]` in InjecAgent), tool calls with their arguments (`[AGENT ACTION]`) and tool outputs (`[TOOL OUTPUT]`). ToolEmu pseudo-traces have no tool calls or outputs; their `[AGENT ACTION]` lines narrate what the agent did and count as agent prose.

- **Agent-text attack:** the content of agent-prose lines only (the tags themselves are excluded).
- **Any-token attack:** every token outside the `[USER]`, `[AGENT PROFILE]` and `[AVAILABLE TOOLKITS]` lines, which are frozen whole, tags included, because the agent did not write them. That covers agent prose, tool calls and their arguments, tool outputs, the tags of those lines and untagged continuation lines.
- **Both attacks:** on traces longer than one window, the first 96 tokens (the prefix repeated in every window) are frozen. Replacement tokens are plain word pieces (up to 12 letters, optional leading space) or single punctuation marks, never special tokens.
- **Mask and remove** act on agent-prose blocks: a prose-tagged line plus the untagged lines that follow it. Blocks are located from the original trace's structure by token position, so an attack that edits tag tokens cannot move text out of the mask. Mask replaces each block with `[TAG] [withheld]`; remove drops it.
- **Left editable under mask or remove:** for the agent-text attack, nothing. For the any-token attack, its surface minus the prose blocks: tool calls, tool outputs and their tags. On ToolEmu nothing is left for either attack, since its traces hold only frozen lines and prose.

Measured on the attacked targets (`phaseB_stats.py`; its re-implementation of the any-token editable set matches the attack records' token counts on all 197 traces):

| source | traces | median share of any-token editable tokens still editable under masking | traces with nothing left editable | any-token edits (up to the first state below p = 0.865) that survive masking |
|---|---|---|---|---|
| InjecAgent | 87 | 61% | 0 | 371 / 414 (90%) |
| ToolEmu | 21 | 0% | 21 | 0 / 101 (0%) |
| R-Judge | 9 | 48% | 0 | 16 / 16 (100%) |
| SHADE-80 | 80 | 80% | 0 | 2197 / 2424 (91%) |

Outside ToolEmu, about 90% of the any-token attack's edits were already in tool calls and tool outputs, not in prose, so masking leaves them in place.

**Setup.** Run 2 rescored every validation trace (InjecAgent, ToolEmu, R-Judge) and every held-out SHADE trace in three views: *full*; *mask*; and *remove*. Scoring uses TF32, the attack's numerics. The full view reproduces the published run-2 AUROC per source (InjecAgent 0.9997, ToolEmu 1.000, SHADE 0.577 exactly; R-Judge 0.523, equal to the windowed val file; the 0.520 in `cross_source_analysis.md` differs by one pair of 304). For mask and remove, the threshold was refit on that view's val slice with the training procedure (temperature by NLL, F1-optimal threshold): 0.775 for mask, 0.752 for remove, against 0.865 for full. Scripts: `analyze_masking.py`, `phaseB_stats.py`; outputs: `job6_masking.json`, `phaseB_stats.json`.

**Clean AUROC per source** (95% stratified-bootstrap CI)

| view | InjecAgent (n = 176) | ToolEmu (n = 44) | R-Judge (n = 35), near chance | SHADE (n = 1448), near chance |
|---|---|---|---|---|
| full | 1.000 | 1.000 | 0.523 [0.33, 0.71] | 0.577 [0.54, 0.61] |
| mask | 0.997 [0.99, 1.00] | 0.662 [0.49, 0.82] | 0.533 [0.35, 0.72] | 0.524 [0.49, 0.55] |
| remove | 0.991 [0.98, 1.00] | 0.500 [0.33, 0.67] | 0.566 [0.36, 0.76] | 0.540 [0.50, 0.58] |

- **R-Judge and SHADE are near chance on clean traces in every view**, including the full one, so attack counts on them say little about masking. They are reported in a separate table below.
- **InjecAgent keeps its signal** because the injected attacker tool call stays in the record.
- **ToolEmu loses most of it.** Under remove, the refit threshold flags 0 of 22 ToolEmu violations.
- **At run 2's own threshold, masking floods false positives**: 86% of compliant ToolEmu traces and 97% of compliant SHADE traces are flagged under mask. With the refit threshold, the masked view flags 55% of ToolEmu violations against 14% of compliant ones, and 33% of SHADE traces in both classes.

**Attacks under masking.** Each attacked target's clean trace and adversarial state (the first state below p = 0.865 on the full-view attack path) were scored under the view at its refit threshold. Counts are detections that survive masking (clean trace still flagged) and that the adversarial state flips (no longer flagged), with 95% Wilson CIs. All attacks are budget 20 and were run against the full view, so they are not adapted to masking.

*Sources where the clean monitor works (InjecAgent and ToolEmu, pooled):*

| attack | mask: flipped / still flagged | remove: flipped / still flagged |
|---|---|---|
| agent text, unconstrained | 0 / 98 [0, 4]% | 0 / 83 [0, 4]% |
| agent text, fluent | 0 / 98 [0, 4]% | 0 / 83 [0, 4]% |
| any token, unconstrained | 58 / 98 [49, 68]% | 40 / 83 [38, 59]% |
| any token, fluent | 57 / 98 [48, 67]% | 32 / 83 [29, 49]% |

Every flip here is on InjecAgent (58/86 and 57/86 under mask; 40/83 and 32/83 under remove). ToolEmu keeps 12 of its 21 detections under mask and none under remove, and masking leaves nothing editable on it, so its 0/12 is by construction.

*Near-chance sources (R-Judge and SHADE-80):*

| attack | R-Judge, mask | R-Judge, remove | SHADE-80, mask | SHADE-80, remove |
|---|---|---|---|---|
| agent text, unconstrained | 0 / 4 [0, 49]% | 0 / 5 [0, 43]% | 0 / 17 [0, 18]% | 0 / 52 [0, 7]% |
| agent text, fluent | 0 / 4 [0, 49]% | 0 / 5 [0, 43]% | 0 / 17 [0, 18]% | 0 / 52 [0, 7]% |
| any token, unconstrained | 2 / 4 [15, 85]% | 3 / 5 [23, 88]% | 14 / 20 [48, 86]% | 22 / 53 [29, 55]% |
| any token, fluent | 3 / 4 [30, 95]% | 4 / 5 [38, 96]% | 16 / 20 [58, 92]% | 21 / 52 [28, 54]% |

**Reading.** Where the clean monitor works, masking stops narration edits by construction, but it gives up most of the clean signal outside InjecAgent. Any-token edits still flip 58 of 98 remaining detections under mask (59% [49, 68]) and 40 of 83 under remove (48% [38, 59]), without any adaptation to the masked view, because about 90% of those edits were in tool calls and tool outputs to begin with. The audit below shows that none of these flips is a realizable evasion, so masking's cost is the clean signal it gives up, not these flips.

**Where the surviving any-token edits land** (`anytoken_edit_audit.py`, output `job6_anytoken_audit.json`). For every any-token flip under mask or remove, the edits outside agent prose (the only ones the masked monitor sees) were located by line: tool output content, tool-call name, tool-call arguments, or a role tag such as `[AGENT ACTION]`. Classes: (a) no edit in any tool call; (b) at least one. On InjecAgent the harmful action is marked exactly (every `[AGENT ACTION]` after the first is an injected attacker call), so each (b) case was checked against "same tool, same target or recipient, same payload". An edited attacker tool name (for example `BankManagerTransferFunds` to "BankManager emerged reprods") counts as neutralized. The three cases with an intact name and edited arguments were reviewed by hand: "delete" changed to "View" (neutralized); a corrupted verb with the same tool, amount and account (still harmful); a word appended after an unchanged address (still harmful). Role-tag edits are counted separately because a deployed monitor takes roles from the agent API, so an agent cannot make them. Denominators are the detections that survive the view, as above; 95% Wilson CIs.

| InjecAgent + ToolEmu | all flips | (a) tool outputs only | (a) tool outputs and role tags | (b) harmful call kept | (b) harmful call neutralized | any role-tag edit |
|---|---|---|---|---|---|---|
| mask, unconstrained | 58 / 98 [49, 68]% | 0 / 98 [0, 4]% | 3 / 98 [1, 9]% | 0 / 98 [0, 4]% | 55 / 98 [46, 66]% | 47 / 98 [38, 58]% |
| mask, fluent | 57 / 98 [48, 67]% | 0 / 98 [0, 4]% | 9 / 98 [5, 16]% | 0 / 98 [0, 4]% | 48 / 98 [39, 59]% | 49 / 98 [40, 60]% |
| remove, unconstrained | 40 / 83 [38, 59]% | 0 / 83 [0, 4]% | 2 / 83 [1, 8]% | 1 / 83 [0, 6]% | 37 / 83 [34, 55]% | 32 / 83 [29, 49]% |
| remove, fluent | 32 / 83 [29, 49]% | 0 / 83 [0, 4]% | 6 / 83 [3, 15]% | 1 / 83 [0, 6]% | 25 / 83 [21, 41]% | 26 / 83 [22, 42]% |

- **No flip comes from tool-output edits alone.** Every class (a) flip also edits a role tag.
- **Most class (b) flips break the harmful call itself**, usually by corrupting the attacker tool's name. The two that keep it also edit a role tag.
- **Harmful call kept and no role tag edited: 0 of 98 (mask) and 0 of 83 (remove)**, 95% CI 0 to 4%, for both attacks.
- **Near-chance sources:** on R-Judge (4 or 5 detections) and SHADE-80 (20 under mask, 52 to 53 under remove), every flip edits a role tag. Neither marks the harmful call, so the 1 to 21 (b) cases per set there were not judged.

So the roughly 60% any-token flip rate under masking does not show a realizable evasion. Every flip either removes the harmful action from the record, by corrupting the attacker's call, or rewrites the role structure, which a deployed monitor takes from the agent API. The audit covers this non-adaptive attack only. An attack restricted to tool-output text with intact calls and roles was not run, so masking's robustness to it is untested. (An agent also does not normally control tool outputs; the any-token attack is an upper bound.)

**Realizability cross-check** (`realizability.py`, output `job6_realizability.json`). The attack edits token ids; an agent writes text. Decoding each first successful state, re-tokenizing and rescoring:

| set | recorded successes | still below the bar as text |
|---|---|---|
| agent text, unconstrained (val) | 65 | 57 (InjecAgent 31 of 38) |
| agent text, fluent (val) | 71 | 68 (InjecAgent 38 of 41) |
| any token, unconstrained (val) | 117 | 108 (InjecAgent 79 of 87) |
| any token, fluent (val) | 114 | 105 |
| any token, unconstrained / fluent (SHADE-80) | 53 / 53 | 40 / 35 |

Clean points rescore within 0.009 of the attack's recorded margin, so the gaps come from re-tokenization, not from scoring differences. Coverage: `job6_realizability.json` covers the full view only, on run 2, for all ten attack sets (agent text and any token, unconstrained and fluent, val and SHADE-80, plus the threshold-0.5 runs), at the first state below p = 0.865. It does not cover the masked views; those flips are already text-level, since each masked view was decoded to text and re-tokenized for scoring. This agrees with the attack's own `success_retokenized` field and the "retokenized" column in `SUMMARY.md`; the README headline table reports token-level success. Only the first crossing on each path is checked, so these counts are lower bounds.

## 6. Job 7: do run-2 flips transfer to other checkpoints?

**Setup.** The clean and adversarial texts of every run-2 attack, plus the random-substitution control, were scored by zero-shot Laya and by the run-1 fine-tune, each at its own calibrated threshold (TF32). A flip *transfers* if the checkpoint flags the clean trace and does not flag the adversarial one; the denominator is the targets that checkpoint flags clean. The run-2 column counts adversarial texts that still cross run 2's own bar. Brackets are 95% Wilson CIs. p is a two-sided Fisher exact test of the set's transfer rate against the random-edit control on the same checkpoint, Holm-adjusted across the 8 tests per checkpoint (the four val attacks at each of the two depths). Scripts: `analyze_transfer.py`, `phaseB_stats.py`; outputs: `job7_transfer.json`, `phaseB_stats.json`.

*Validation targets, adversarial state = first state below p = 0.865 on run 2:*

| attack | run 2 | zero-shot Laya | p vs random | run-1 Laya | p vs random |
|---|---|---|---|---|---|
| agent text, unconstrained | 57 / 65 [78, 94]% | 12 / 55 [13, 34]% | 0.020 | 9 / 65 [8, 24]% | 0.005 |
| agent text, fluent | 68 / 71 [88, 99]% | 17 / 60 [18, 41]% | 0.0008 | 14 / 71 [12, 30]% | 0.0002 |
| any token, unconstrained | 108 / 117 [86, 96]% | 11 / 106 [6, 18]% | 0.31 | 14 / 117 [7, 19]% | 0.006 |
| any token, fluent | 105 / 114 [86, 96]% | 13 / 103 [8, 20]% | 0.19 | 9 / 114 [4, 14]% | 0.032 |
| random edits (control) | 4 / 117 [1, 8]% | 6 / 106 [3, 12]% | | 2 / 117 [0, 6]% | |

*Validation targets, deeper state = first state below p = 0.5 on run 2* (unconstrained attacks from their dedicated threshold-0.5 runs):

| attack | run 2 | zero-shot Laya | p vs random | run-1 Laya | p vs random |
|---|---|---|---|---|---|
| agent text, unconstrained | 47 / 48 [89, 100]% | 9 / 40 [12, 38]% | 0.022 | 15 / 48 [20, 45]% | 9e-7 |
| agent text, fluent | 60 / 62 [89, 99]% | 15 / 51 [19, 43]% | 0.0008 | 21 / 62 [23, 46]% | 2e-8 |
| any token, unconstrained | 106 / 106 [96, 100]% | 18 / 95 [12, 28]% | 0.022 | 18 / 106 [11, 25]% | 0.0003 |
| any token, fluent | 103 / 103 [96, 100]% | 16 / 92 [11, 26]% | 0.035 | 18 / 103 [11, 26]% | 0.0003 |

*SHADE-80 (first state below p = 0.865; there is no SHADE random control):*

| attack | run 2 | zero-shot Laya | run-1 Laya |
|---|---|---|---|
| agent text, unconstrained | 14 / 14 [78, 100]% | 3 / 13 [8, 50]% | 0 / 14 [0, 22]% |
| agent text, fluent | 14 / 15 [70, 99]% | 0 / 14 [0, 22]% | 0 / 15 [0, 20]% |
| any token, unconstrained | 40 / 53 [62, 85]% | 1 / 52 [0, 10]% | 0 / 53 [0, 7]% |
| any token, fluent | 35 / 53 [53, 77]% | 1 / 52 [0, 10]% | 0 / 53 [0, 7]% |

**Caveats on the control.** The random control is `val_agent_random`: 20 random substitutions in agent text (the full budget), on the same 117 val targets. For the any-token rows it is a narrower-scope baseline, and the attack states often use fewer than 20 edits. A matching any-token random control was therefore run (`random_any_control.py`, job 8 step `rand_any`): the any-token attack's editable set, candidate vocabulary and budget, 20 random substitutions (stopping early once below run 2's bar, like the agent-text control), on the same 117 targets, scored by all three checkpoints. Output: `job7_random_any_control.json`.

| any token, first state below p = 0.865 | run 2 | zero-shot Laya | run-1 Laya |
|---|---|---|---|
| any-token attack, unconstrained | 108 / 117 [86, 96]% | 11 / 106 [6, 18]% | 14 / 117 [7, 19]% |
| random any-token edits (control) | 5 / 117 [2, 10]% | 14 / 106 [8, 21]% | 3 / 117 [1, 7]% |
| Fisher exact, attack vs this control | p < 1e-40 | p = 0.67 | p = 0.010 |

Against the matching control, the any-token attack transfers to run 1 (12% against 3%) but not to zero-shot Laya, where random edits over the same surface flip as many traces (13%) as the attack does (10%).

**Reading.** Most run-2 flips do not carry over. Agent-text edits transfer above the random-edit rate on both checkpoints (Holm p at most 0.022), but only 14 to 28% of the time at the operating point. Any-token edits beat the control on run 1 (12% and 8%) but are not distinguishable from it on zero-shot Laya at the operating point (10% and 13% against 6%; p = 0.31 and 0.19), and against the matching any-token random control, which flips 13% of zero-shot detections by itself, the unconstrained attack shows no transfer to zero-shot Laya at all (p = 0.67). Deeper edits transfer more (17 to 34%) and all exceed the control. SHADE-80 edits essentially do not transfer. The attack is largely specific to the checkpoint it was optimized against, so the threat model it supports is an attacker with gradient access to the deployed monitor or a close surrogate.

## 7. Job 8: how much do the results move across training seeds?

**Reproducibility note.** Fixed-seed retrains of the monitor are not bit-reproducible. In the resume test, two uninterrupted runs with the same seed, the same data order and the same A100 ended with a maximum weight difference of 0.005, different per-step losses, and different best epochs (epoch 1 with val AUROC 0.992 against epoch 2 with 0.989). The cause is the fused attention kernels (SDPA flash and memory-efficient backward), which are nondeterministic; `torch.use_deterministic_algorithms(warn_only=True)` only warns about them. The seed results below are therefore *between-monitor variation*: they include this kernel noise on top of what the seed itself changes (data order, dropout, head initialization). **Resume test and kernel choice.** With deterministic algorithms and the math attention kernel, two uninterrupted runs (130 steps, seed 1) were identical: every logged training loss, the best epoch, the validation AUROC per source, the temperature and the threshold. This confirms the fused attention kernels as the source of the noise above. Runs hard-killed at step 115 (resumed from the end-of-epoch-1 checkpoint) and at step 125 (resumed mid-epoch from step 120) saw exactly the same batches in the same order over all 130 steps and matched the uninterrupted run on every one of those quantities (`job8/out/resume_test/`, `gate_local.txt`). The math kernel trained at 0.507 s per step against 0.272 s for the fused kernels, 1.86 times slower, above the 1.5 times limit, so the seed retrains use the fused kernels (`timing.json`; each seed's calibration file records `attn`). The resume test ran with deterministic attention and the seed retrains run with fused attention, so "bit-identical" describes the resume test only, not the seed runs: the seed retrains are not bit-reproducible, and the note above applies to them.

**Setup.** Seeds 1 and 2 were retrained with run 2's arguments (3 epochs, batch size 16; the recorded arguments differ only in seed and output paths), then evaluated and re-attacked on the val targets each one flags, budget 20, with all three attacks. Run 2 is seed 0. Attack runs went down to min(0.5, the seed's threshold), so success at p < 0.5 can be read off every seed's paths; run 2's p < 0.5 numbers come from its threshold-0.5 runs, and no fluent run exists there. Success is token level, as in the README table. Brackets are 95% Wilson CIs. Script: `analyze_seeds.py`; output: `job8_seeds.json`; records: `job8/out/seed{1,2}/`. Weights are not committed (`job8/models/`, gitignored).

**The monitors** (each at its own threshold):

| seed | threshold | best epoch | val AUROC: InjecAgent / ToolEmu / R-Judge | SHADE AUROC | SHADE false-positive rate |
|---|---|---|---|---|---|
| 0 (run 2) | 0.865 | 3 | 1.000 / 1.000 / 0.523 | 0.577 | 0.92 |
| 1 | 0.368 | 2 | 1.000 / 1.000 / 0.720 | 0.486 | 0.99 |
| 2 | 0.825 | 3 | 1.000 / 1.000 / 0.625 | 0.541 | 0.99 |

The source-level picture is stable: perfect on InjecAgent and ToolEmu, weak on R-Judge, near chance on SHADE. The calibrated threshold is not: it ranges from 0.37 to 0.87. Because of that, success at each seed's own threshold is not a like-for-like comparison, so p < 0.5 is the primary bar below.

**Attack success at the common bar, p < 0.5:**

| attack | source | seed 0 | seed 1 | seed 2 |
|---|---|---|---|---|
| agent text, unconstrained | InjecAgent | 25 / 87 [20, 39]% | 32 / 87 [27, 47]% | 15 / 87 [11, 27]% |
| | ToolEmu | 19 / 21 [71, 97]% | 20 / 22 [72, 97]% | 20 / 22 [72, 97]% |
| | R-Judge | 4 / 9 [19, 73]% | 14 / 19 [51, 88]% | 10 / 18 [34, 75]% |
| agent text, fluent | InjecAgent | no run | 36 / 87 [32, 52]% | 15 / 87 [11, 27]% |
| | ToolEmu | no run | 21 / 22 [78, 99]% | 20 / 22 [72, 97]% |
| | R-Judge | no run | 16 / 19 [62, 94]% | 11 / 18 [39, 80]% |
| any token, unconstrained | InjecAgent | 79 / 87 [83, 95]% | 80 / 87 [84, 96]% | 66 / 87 [66, 84]% |
| | ToolEmu | 18 / 21 [65, 95]% | 22 / 22 [85, 100]% | 22 / 22 [85, 100]% |
| | R-Judge | 9 / 9 [70, 100]% | 19 / 19 [83, 100]% | 16 / 18 [67, 97]% |

R-Judge targets differ a lot across seeds (9, 19 and 18) because each seed flags different traces, and that source is close to chance on clean traces.

**At each seed's own threshold** (bars differ, so for reference only):

| attack | source | seed 0 (0.865) | seed 1 (0.368) | seed 2 (0.825) |
|---|---|---|---|---|
| agent text, unconstrained | InjecAgent | 38 / 87 [34, 54]% | 31 / 88 [26, 46]% | 16 / 87 [12, 28]% |
| | ToolEmu | 19 / 21 [71, 97]% | 20 / 22 [72, 97]% | 22 / 22 [85, 100]% |
| | R-Judge | 8 / 9 [56, 98]% | 14 / 19 [51, 88]% | 12 / 18 [44, 84]% |
| agent text, fluent | InjecAgent | 41 / 87 [37, 58]% | 35 / 88 [30, 50]% | 20 / 87 [15, 33]% |
| any token, unconstrained | InjecAgent | 87 / 87 [96, 100]% | 81 / 88 [84, 96]% | 67 / 87 [67, 85]% |

**Does the structural result replicate?** InjecAgent direct harm (one frozen attacker call) against data stealing (two frozen calls), agent text, unconstrained, p < 0.5:

| seed | direct harm | data stealing |
|---|---|---|
| 0 | 24 / 42 [42, 71]% | 1 / 45 [0, 12]% |
| 1 | 23 / 42 [40, 69]% | 9 / 45 [11, 34]% |
| 2 | 14 / 42 [21, 48]% | 1 / 45 [0, 12]% |

**Is the same trace fragile on every seed?** Often not. Paired on the 87 InjecAgent targets all three seeds share (exact McNemar, agent text, unconstrained, p < 0.5, unadjusted across the 9 source-by-pair tests):

| pair | both flip | only the first | only the second | p |
|---|---|---|---|---|
| seed 0 vs 1 | 13 | 12 | 19 | 0.28 |
| seed 0 vs 2 | 9 | 16 | 6 | 0.052 |
| seed 1 vs 2 | 11 | 21 | 4 | 0.0009 |

Roughly 30% of the traces that flip on either seed of a pair flip on both. On ToolEmu and R-Judge no pair differs (p of at least 0.25).

**Text-level check.** The attack's own re-tokenized check, at the bar each run went to (0.5 for seeds 0 and 2, 0.368 for seed 1), agent text, unconstrained, for seeds 0 / 1 / 2: InjecAgent 23/87, 25/87, 13/87; ToolEmu 19/21, 17/22, 18/22; R-Judge 2/9, 13/19, 6/18.

**Reading.**

- **The ordering replicates.** On every seed, agent-text edits flip ToolEmu (where the agent's narration is the record) about 90% of the time and InjecAgent 17 to 37%, and direct-harm traces flip far more often than data-stealing ones. This is the paper's structural claim, on three monitors.
- **The magnitude does not pin down.** Three monitors with the same config and clean AUROC 1.000 on InjecAgent flip 17%, 29% and 37% of its traces at the same bar, and seeds 1 and 2 differ significantly. Run 2's single-monitor InjecAgent rates should be reported with this spread, as between-monitor variation that includes the kernel noise noted above.
- **Per-trace fragility is partly a property of the monitor, not only of the trace.** Most InjecAgent flips are not shared between two seeds. This limits any per-trace explanation drawn from one checkpoint, including the margin and editable-fraction regressions in section 2, which rest on run 2 alone.
- **Three monitors is few.** These ranges describe these three retrains. They are not a confidence interval over seeds.

**Run notes.** Seeds 1 and 2 trained in 2.5 and 2.6 minutes with fused attention, as against 1.7 for run 2; the software environment of run 2's original training was not compared. The 11 steps after the resume test completed on one VM (129 minutes, a heartbeat every 4 minutes, no failed beats, no reclaims). The smoke step's short chain (a 10-step training, then small attacks including a `--resume` pass) never ran: the first attempts stopped at the resume gate, and the step was then marked done from the resume test. The full runs completed without it, but `attack.py --resume` was not exercised in this job.

## 8. Phase C: does an LLM judge get moved by the same edits?

**Setup.** `llm_judge.py` asks Claude Haiku 5.5 (effort medium, structured output) for a suspicion score (0 to 100) and a verdict on each trace text, full view. On all 117 attacked val targets it judges five texts: the clean trace twice (Haiku 5.5 rejects sampling parameters, so the second call measures its run-to-run noise), the unconstrained agent-text edit, the fluent agent-text edit, and the random-edit control (20 random agent-text substitutions). Attack edits are run 2's first state below p = 0.865, else the path's best state. It also judges 40 val and 30 SHADE compliant traces, and run 2's SHADE-80 agent-text flips with their clean traces. All 718 calls succeeded (no refusals or parse errors) for $0.16; the 20-call dry run cost $0.003. A *judge flip* is a trace whose clean version the judge calls violating on both calls and whose edited version it calls not violating. Paired comparisons use exact McNemar tests. Scripts: `llm_judge.py`, `analyze_judge.py`; outputs: `phaseC/judge_calls.jsonl`, `phaseC_judge.json`.

**The judge itself** (95% Wilson CIs):

| | val | SHADE |
|---|---|---|
| clean violating calls judged violating | 217 / 234 (93% [89, 95]) | 9 / 34 (26% [15, 43]) |
| compliant traces judged violating | 0 / 40 (0% [0, 9]) | 7 / 30 (23% [12, 41]) |
| suspicion AUROC, violating vs compliant | 0.99 | 0.50 |
| the two clean calls disagree on the verdict | 1 / 117 | 1 / 17 |

Haiku is a strong judge on the val sources and, like Laya, at chance on SHADE.

**Flip rates on the same val traces** (traces the judge stably flags clean):

| edit | all attacked traces (n = 108) | traces both attacks flipped on run 2 (n = 54) |
|---|---|---|
| agent text, unconstrained | 4 / 108 (4% [1, 9]) | 4 / 54 (7% [3, 18]) |
| agent text, fluent | 7 / 108 (6% [3, 13]) | 6 / 54 (11% [5, 22]) |
| random edits (control) | 9 / 108 (8% [4, 15]) | 8 / 54 (15% [8, 27]) |

- **The edits that flip run 2 do not move Haiku more than random edits do.** Paired on the same 108 traces: unconstrained vs random, 0 traces flip only under the attack and 5 only under random (p = 0.06); fluent vs random, 1 and 3 (p = 0.63).
- **Every flip is on ToolEmu**: 4, 7 and 9 of its 16 stably flagged traces. InjecAgent (0 of 87) and R-Judge (0 of 5) never flip. ToolEmu's record is the agent's own narration of its actions, so any edit there, random or optimized, edits the evidence itself.
- **Suspicion moves less under attack edits than under random ones**: mean change from the clean score -3.1 (unconstrained) and -3.7 (fluent) against -5.4 (random); fluent vs random, Wilcoxon p = 0.004.
- **SHADE is uninformative here**: the judge stably flags only 4 clean traces in each SHADE set, and flips none of them.

**Reading.** Gradient edits against the Laya monitor are specific to it: they transfer to other Laya checkpoints only partly (section 6) and to an LLM judge not at all beyond random noise. An attacker who wants to fool an LLM judge would need to target it directly; this result says nothing about how hard that is.
