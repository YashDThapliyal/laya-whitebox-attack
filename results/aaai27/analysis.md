# AAAI-27 Phase A: structure vs fragility, recomputed on SHADE-80

All numbers are for the fine-tuned monitor (run 2), agent-text attacks, success at the operating threshold (p < 0.865). There was no GPU or API use: everything is recomputed from the existing `attack/*.jsonl` records.

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
