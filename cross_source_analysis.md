# Cross-source analysis: monitor quality vs attack fragility (Phase 4.5)

**Bottom line: with these four sources, attack fragility does *not* track monitor quality.** The two sources the monitor judges perfectly (InjecAgent, ToolEmu, AUROC 1.00) sit at opposite ends of the fragility range (44% vs 90% flipped at 20 swaps). The two it judges near chance (R-Judge 0.52, SHADE 0.58) are also at opposite ends (89% vs 10%). What does predict fragility, trace by trace, is **structure**: how much of the incriminating evidence sits in text the attacker can edit, and how many windows must all be pushed under the threshold. Four sources, two of them near-trivially separable and one with only 9 attackable traces, can't establish or rule out a quality–fragility relationship. Read this as "no evidence of one here, and a clear structural confound", not "fragility is constant".

## The table

The monitor is fine-tuned Laya (run 2, the attacked model). "Trained" and "zero-shot" AUROC use each source's existing Phase-2 held-out val slice; no new splits were made. For SHADE they use the full held-out MRT set. Scoring for both is the same windowed max-margin. Brackets are 95% bootstrap CIs.

Attack = white-box HotFlip token substitution on **agent-authored text only**. "Success @b" = fraction of attacked traces (true positives: violating and flagged) pushed below the decision threshold (p = 0.865, F1-optimal on val) within b substitutions. "Random @20" is the random-substitution baseline on the same positions and budget. "Any-token @20" lifts the agent-text restriction (upper bound).

| Source | n eval | AUROC trained [95% CI] | AUROC zero-shot [95% CI] | attacked n | success @1 | @3 | @5 | @10 | @20 | random @20 | any-token @20 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| InjecAgent | 176 | **1.000** [1.00, 1.00] | 0.792 [0.72, 0.85] | 87 | 0.01 | 0.03 | 0.09 | 0.24 | **0.44** [0.34, 0.54] | 0.00 | 1.00 |
| ToolEmu | 44 | **1.000** [1.00, 1.00] | 0.787 [0.64, 0.92] | 21 | 0.10 | 0.38 | 0.52 | 0.90 | **0.90** [0.71, 0.97] | 0.14 | 1.00 |
| R-Judge | 35 | **0.520** [0.33, 0.72] | 0.477 [0.29, 0.67] | 9 | 0.11 | 0.44 | 0.44 | 0.67 | **0.89** [0.56, 0.98] | 0.11 | 1.00 |
| SHADE-Arena (MRT) | 1,448 | **0.577** [0.55, 0.61] | 0.505 [0.47, 0.55] | 20 | 0.00 | 0.00 | 0.00 | 0.05 | **0.10** [0.03, 0.30] | 0.00 | 0.60 |

Brackets on the @20 column are Wilson 95% intervals. SHADE runs went to 60 substitutions: at 60, agent text reaches 0.15 and any-token 0.75. Per-source curves: `attack/success_vs_budget.png`. Raw numbers: `results/cross_source_table.json`, `results/cross_source_table.md`.

Structural properties of the attacked traces (medians):

| Source | windows per trace | fraction of trace tokens the attacker may edit (agent text) | start margin above threshold (logit units) | where the incriminating evidence lives |
|---|---|---|---|---|
| InjecAgent | 2 | 0.27 | 4.56 | attacker tool call(s) + exfiltration email: **frozen** (tool calls); agent only edits its thoughts/final answer |
| ToolEmu | 1 | 0.41 | 3.83 | the narrated risky action itself, which **is** the editable agent text |
| R-Judge | 1 | 0.26 | 1.93 | mixed: agent actions/responses are largely editable prose |
| SHADE (MRT) | 15 | 0.02 | 2.27 | tool outputs across many windows: **frozen**; agent prose is ~2% of the trace |

## What the data does and doesn't show

1. **No monotone quality → fragility relationship.** Rank the sources by trained AUROC (InjecAgent ≈ ToolEmu > SHADE > R-Judge) and by fragility at 20 swaps (ToolEmu ≈ R-Judge > InjecAgent > SHADE): the orders don't line up in either direction. Equal-quality sources (InjecAgent vs ToolEmu, both 1.00) differ 2× in fragility; the two near-chance sources differ ~9×.
2. **Structure predicts fragility much better.** Pooled over all 137 attacked traces (agent-text scope), success at 20 swaps correlates with the *fraction of the trace the attacker can edit* (Spearman ρ = +0.65, p ≈ 1e-17) and with the *number of windows* (ρ = −0.66), far more than with how confidently the trace was flagged (starting margin, ρ = −0.29). This also holds **within a single source**, where quality is fixed. In InjecAgent, successful traces have a larger editable fraction (0.36 vs 0.21, Mann-Whitney p ≈ 1e-9). The InjecAgent split is stark: "direct harm" cases (one frozen attacker tool call) flip **83%** of the time at 20 swaps, while "data stealing" cases (a frozen data-access call *plus* a frozen exfiltration email to an outside address) flip **7%**. The caveat is that editable fraction and window count are partly confounded with source (SHADE is extreme on both).
3. **Monitor quality and robustness are both low where it matters.** SHADE's apparent robustness (10% at 20 swaps; 12% in the later 80-trace widened set, `widened_samples.md`) is *not* a sign of good judgment. The monitor flags 92% of compliant SHADE traces too; it is hard to un-flag because ~15 windows of routine money-movement and email text each trip it independently, and the attacker controls ~2% of the tokens. When the attacker may edit any token (including tool outputs), 60–75% of SHADE traces flip.
4. **Once the edit surface isn't the bottleneck, every source breaks.** With any-token edits, 100% of attacked in-distribution traces flip within 20 substitutions, regardless of quality (1.00, 1.00, 0.52 AUROC), in a median of 1–4 swaps. On these short traces, the monitor's decisions are fragile everywhere.
5. **The gradient matters.** Random substitutions on the same positions flip 0% (InjecAgent, SHADE) to 11–14% (R-Judge, ToolEmu) at 20 swaps, vs 44–90% for HotFlip.

**Honest verdict:** "fragility tracks quality" isn't supported. "Fragility is constant regardless of quality" isn't quite right either: it varies a lot, but the variation lines up with how much of the evidence the attacker can touch, not with how good the monitor's judgment is. With 4 sources (2 synthetic/templated at ceiling AUROC, R-Judge n = 9 attacked, SHADE n = 20 attacked), this is suggestive, not established. A proper test needs several real-trajectory sources whose monitor quality spans 0.6–0.95, attacked under a matched edit surface.

## Caveats specific to this comparison

- **"Success" means crossing p = 0.865, not convincing the monitor the trace is benign.** The attack stops at the first crossing, so post-attack p is typically ~0.80–0.86. See the threshold-0.5 sensitivity run below.
- **Edits are not fluent.** HotFlip has no language-model constraint; most successful edits are non-words or odd word swaps (examples in `attack_eval.md`). These results bound what an unconstrained white-box attacker can do, not what a stealthy, fluent attacker can.
- **Unequal edit surfaces by construction.** "Agent-authored text" means different things per source (ToolEmu's action descriptions vs InjecAgent's thoughts). That's the point of finding 2, but it also means the agent-scope column isn't a controlled comparison. The any-token column is the most controlled one: identical rule for every source.
- **Quality numbers are unstable.** R-Judge's trained AUROC was 0.77 (run 1), 0.66 (run 2, truncated view) and 0.52 (run 2, windowed), all on n = 35. SHADE's was 0.51 (run 1) and 0.58 (run 2).
- Every success was re-verified after decoding to text and re-tokenizing. The token-level and re-tokenized success rates agree for 82–100% of successes per source in the agent-text runs and 73% for SHADE any-token (`attack/summary.json`).

## Threshold sensitivity (p = 0.5)

At a stricter bar, **p < 0.5**, the monitor has to actually lean "benign". The attack was rerun on the **same targets** (`attack/t05_*.jsonl`, `results/threshold05_sensitivity.json`). Success rates, with the 0.865-threshold rate in parentheses:

| Source (n) | agent text @5 | agent text @10 | agent text @20 [95% CI] | any-token @5 | any-token @20 | retokenized, agent text / any |
|---|---|---|---|---|---|---|
| InjecAgent (87) | 0.01 | 0.14 | **0.29** [0.20, 0.39] (0.44) | 0.49 | **0.91** (1.00) | 0.26 / 0.82 |
| ToolEmu (21) | 0.43 | 0.76 | **0.90** [0.71, 0.97] (0.90) | 0.43 | **0.86** (1.00) | 0.90 / 0.86 |
| R-Judge (9) | 0.22 | 0.33 | **0.44** [0.19, 0.73] (0.89) | 0.67 | **1.00** (1.00) | 0.22 / 0.89 |
| SHADE (20) | – | – | not run (0.10 at 0.865 already) | 0.00 | **0.20** (0.60); 0.55 at 60 swaps (0.75) | – / 0.30 |

Reading:
- **The flips are not all shallow.** Most in-distribution flips still reach p < 0.5, typically within 5–11 swaps, and 86–100% of flagged in-distribution traces can be pushed all the way to "benign" when any token may change.
- **The cross-source ordering is unchanged.** At agent-text scope: ToolEmu > R-Judge > InjecAgent > SHADE, still unrelated to monitor quality.
- **R-Judge drops the most** (0.89 → 0.44), and half of those deeper flips don't survive re-tokenization (0.22). On n = 9, that's the least reliable row.
- **SHADE needs many more swaps** (median 36 with any-token edits) to reach p < 0.5, consistent with the many-windows explanation.
