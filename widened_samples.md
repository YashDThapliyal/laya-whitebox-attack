# Widened samples: SHADE 20 → 80 targets, and an R-Judge training-split supplement

**Short answer: the conclusions hold, now with confidence intervals about half as wide.** On held-out SHADE-Arena traces, edits limited to the agent's own text still mostly fail against the fine-tuned monitor. At its operating threshold they flip **17% (unconstrained) and 19% (constrained)** of 80 flagged traces within 60 swaps (95% CIs 11–27% and 12–29%); the 20-trace estimates were 15% and 10%. Almost none reach p < 0.5 (1–3%). Any-token edits, the upper bound, flip **66–67%** within 60 swaps (CIs 55–76%), vs 75% at n = 20. The constrained attack again matches the unconstrained one on SHADE. R-Judge's held-out set can't be widened (see below). A 60-trace training-split supplement shows the monitor is harder to flip on traces it was trained on, and that this is explained by higher starting confidence: margin-matched training traces flip 73% of the time, close to the held-out 89%.

## SHADE (held-out MRT): 80 flagged violating traces per attack × scope

Same fine-tuned monitor, selection rule, budgets and thresholds as before. The selection with n = 80 reproduces the original 20 as its first 20, in order (verified), so only the 60 new traces were attacked. Unconstrained agent-text at p < 0.5 combines the 3 originals that crossed 0.865 (re-run to p < 0.5) with the 17 that never crossed 0.865 in 60 swaps, which are failures at p < 0.5 by construction. Constrained any-token hit its time cap at 59 of 60 new traces, so **n = 79** there.

#### SHADE, p < 0.865: 80 targets (original 20 in parentheses at @20 / @60)

| attack | scope | n | @1 | @3 | @5 | @10 | @20 | @60 | 95% CI @60 | retokenized @60 | original-20 @20 / @60 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| unconstrained | agent text | 80 | 0.03 | 0.05 | 0.05 | 0.07 | 0.12 | 0.17 | [0.11, 0.27] | 0.16 | 0.10 / 0.15 (n=20) |
| constrained | agent text | 80 | 0.04 | 0.06 | 0.06 | 0.11 | 0.15 | 0.19 | [0.12, 0.29] | 0.19 | 0.05 / 0.10 (n=20) |
| unconstrained | any token | 80 | 0.03 | 0.14 | 0.23 | 0.39 | 0.47 | 0.66 | [0.55, 0.76] | 0.59 | 0.60 / 0.75 (n=20) |
| constrained | any token | 79 | 0.03 | 0.09 | 0.20 | 0.33 | 0.46 | 0.67 | [0.56, 0.76] | 0.57 | 0.55 / 0.75 (n=20) |

#### SHADE, p < 0.5: 80 targets (original 20 in parentheses at @20 / @60)

| attack | scope | n | @1 | @3 | @5 | @10 | @20 | @60 | 95% CI @60 | retokenized @60 | original-20 @20 / @60 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| unconstrained | agent text | 80 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.01 | [0.00, 0.07] | 0.01 | 0.00 / 0.00 (n=20) |
| constrained | agent text | 80 | 0.00 | 0.00 | 0.00 | 0.00 | 0.01 | 0.03 | [0.01, 0.09] | 0.03 | 0.00 / 0.00 (n=20) |
| unconstrained | any token | 80 | 0.00 | 0.00 | 0.01 | 0.07 | 0.20 | 0.44 | [0.33, 0.55] | 0.28 | 0.20 / 0.55 (n=20) |
| constrained | any token | 79 | 0.00 | 0.00 | 0.01 | 0.05 | 0.14 | 0.34 | [0.25, 0.45] | 0.13 | 0.15 / 0.40 (n=20) |

**Reading it**
- **Agent-text-only edits still mostly fail on SHADE**, at both bars and for both attacks. The widened estimate is a little higher than the 20-trace one at the operating threshold (17–19% vs 10–15%), still low, and with far tighter bounds (upper CI ≤ 29%, vs up to 36% before). Reaching p < 0.5 remains essentially impossible from agent text alone (≤ 3%, upper CI ≤ 9%).
- **Any-token edits flip about two-thirds** within 60 swaps (vs 75% at n = 20; the old estimate sat at the top of the new interval). About 34–44% reach p < 0.5. As before, this is an upper bound: it includes editing tool outputs and log structure, which a real agent can't do.
- **Constrained ≈ unconstrained on SHADE at n = 80** (agent text 0.19 vs 0.17; any token 0.67 vs 0.66 within 60 swaps). The fluency constraint doesn't weaken the attack here either.
- **Why SHADE resists agent-only edits is unchanged:** the monitor's flag comes from many windows of tool output the agent doesn't write, and agent prose is ~2% of these traces (see `cross_source_analysis.md`).

## R-Judge: why the held-out sample can't grow, and what the supplement shows

The held-out R-Judge slice has 19 violating traces, and the fine-tuned monitor flags 9. All 9 were already attacked, so there's nothing more to attack without new data. The only other flagged R-Judge traces are in the **training split**, which the monitor saw with labels. As a clearly separated supplement, 60 of the 266 flagged violating training-split traces (seeded order) were attacked with the same settings (agent text, budget 20).

#### R-JudgeTRAIN-split supplement (seen in training; not comparable to held-out numbers)

| attack | bar | n | @1 | @3 | @5 | @10 | @20 | 95% CI @20 | retokenized @20 |
|---|---|---|---|---|---|---|---|---|---|
| unconstrained | p < 0.865 | 60 | 0.02 | 0.08 | 0.08 | 0.20 | 0.27 | [0.17, 0.39] | 0.27 |
| constrained | p < 0.865 | 60 | 0.02 | 0.08 | 0.10 | 0.13 | 0.20 | [0.12, 0.32] | 0.20 |
| unconstrained | p < 0.5 | 60 | 0.00 | 0.02 | 0.02 | 0.07 | 0.13 | [0.07, 0.24] | 0.13 |
| constrained | p < 0.5 | 60 | 0.00 | 0.02 | 0.03 | 0.07 | 0.10 | [0.05, 0.20] | 0.08 |

**Starting confidence explains the gap.** The monitor is far more confident on training traces (median p 0.970, 1.62 logits above the operating threshold) than on the held-out ones (median p 0.933, 0.78 logits above). Restricting the supplement to the 11 training traces whose starting margin falls in the held-out range:

| attack | bar | all 60 training traces | margin-matched (n = 11) | held-out (n = 9) |
|---|---|---|---|---|
| unconstrained | p < 0.865 | 0.27 | **0.73** | 0.89 |
| constrained | p < 0.865 | 0.20 | **0.73** | 1.00 |
| unconstrained | p < 0.5 | 0.13 | 0.27 | 0.44 |
| constrained | p < 0.5 | 0.10 | 0.36 | 0.89 |

So the high held-out R-Judge fragility isn't obviously a small-n fluke at the operating threshold: comparably confident training traces flip at a similar rate. It's driven by the held-out verdicts being low-confidence. At the stricter p < 0.5 bar the margin-matched training traces flip less often than the held-out ones (0.27–0.36 vs 0.44–0.89), but with n = 11 and n = 9 that difference isn't reliable. **This supplement doesn't replace a larger held-out R-Judge set.** It tells you the direction and mechanism, not a held-out rate.

## Files

`attack/x_*` (per-trace records and logs), `attack/targets_ft_mrt80_*.json`, `attack/targets_rjudge_train60.json`, `results/widen_analysis.json`, `results/widen_tables.md`, `scripts/widen_analysis.py`.

## Infrastructure note

The widening runs lost two VMs mid-run: the Mac's network dropped around 15:00–15:16, the keep-alive pings stopped, and Colab reclaimed both. Every trace synced before the drop was kept, and the rest resumed on two new VMs with checksum-verified weights (`--resume`; no duplicate records). The watchdog was fixed to stop treating local network errors as "VM gone".
