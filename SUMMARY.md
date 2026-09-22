# Laya as a trusted monitor: quality vs white-box fragility

## Headline

A fine-tuned Laya monitor (421M, ModernBERT-large + decision head) was **near-perfect on held-out slices of its training-style data but near chance on held-out SHADE-Arena traces** (AUROC 0.58; it flags 92% of *benign* SHADE traces). A white-box HotFlip token-substitution attack **flips its correct "violating" verdicts easily wherever the incriminating evidence is text the attacker writes, and mostly fails where it isn't.** The central question was whether fragility tracks how good the monitor's judgment is on a source. **The answer from these four sources is no:** equally-good sources differ 2× in fragility and equally-bad ones differ ~9×. Fragility instead follows trace structure: how much of the trace the attacker can edit, and how many windows must all be pushed under the threshold. With four sources, two of them synthetic, that is suggestive, not established.

**Follow-up results (corrected framing).** Restricting the attack to locally plausible word substitutions didn't reduce its success. Most successful edits work by changing what the agent's narration claims happened, usually toward sounding more benign, while the frozen tool-call evidence is unchanged. That makes this a **narrative-meaning vulnerability** (the monitor trusts the agent's account over its recorded actions), **not** a stealth result: per two LLM raters (no human review yet), 58% of successful edits are visibly broken and only 2/73 read naturally. Widening SHADE to 80 traces left all conclusions unchanged.

## Central result: quality vs fragility, per source

Monitor = fine-tuned Laya (run 2). AUROC is on each source's existing held-out val slice (SHADE: full held-out MRT set), with 95% bootstrap CIs. Attack = white-box HotFlip on **agent-authored text only**. Success @b = fraction of correctly flagged violating traces pushed below the operating threshold (p = 0.865, F1-optimal on val) within b token substitutions.

| Source | AUROC trained [95% CI] | AUROC zero-shot | attacked n | @1 | @3 | @5 | @10 | @20 | random @20 | any-token @20 |
|---|---|---|---|---|---|---|---|---|---|---|
| InjecAgent (templated pairs) | **1.00** [1.00, 1.00] | 0.79 | 87 | 0.01 | 0.03 | 0.09 | 0.24 | **0.44** | 0.00 | 1.00 |
| ToolEmu (synthetic pseudo-traces) | **1.00** [1.00, 1.00] | 0.79 | 21 | 0.10 | 0.38 | 0.52 | 0.90 | **0.90** | 0.14 | 1.00 |
| R-Judge (real trajectories) | **0.52** [0.33, 0.72] | 0.48 | 9 | 0.11 | 0.44 | 0.44 | 0.67 | **0.89** | 0.11 | 1.00 |
| SHADE-Arena / MRT (held out) | **0.58** [0.55, 0.61] | 0.51 | 20 | 0.00 | 0.00 | 0.00 | 0.05 | **0.10** | 0.00 | 0.60 |

(SHADE at 60 swaps: 0.15 agent text, 0.75 any-token.) Full table, Wilson CIs and structural stats: `cross_source_analysis.md`. Curves: `attack/success_vs_budget.png`.

**What it shows:**
- **Quality doesn't predict fragility.** InjecAgent and ToolEmu are both at 1.00 AUROC, but 44% vs 90% flip at 20 swaps. R-Judge and SHADE are both near chance, but 89% vs 10% flip.
- **Structure does.** Pooled over all 137 attacked traces, success correlates with the fraction of the trace the attacker may edit (Spearman ρ = +0.65) and with window count (ρ = −0.66), much more than with starting confidence (ρ = −0.29). The same pattern holds inside one source, where quality is fixed: InjecAgent "direct harm" cases (one frozen attacker tool call) flip 83%, while "data stealing" cases (a frozen data-access call plus a frozen exfiltration email) flip 7%. These correlations were computed after seeing the table, so they're post-hoc.
- **SHADE's low fragility isn't robustness.** The monitor is wrong about SHADE anyway. Its flags are hard to remove because ~15 windows of routine money-movement and email text each trip it independently, and the agent's own prose is ~2% of the trace. Let the attacker edit any token and 60–75% of SHADE flags flip.
- **With an unrestricted edit surface, every in-distribution source breaks.** Any-token edits flip 100% of flagged traces within 20 swaps, in a median of 1–4, regardless of quality.
- **Random swaps don't do this** (0–14% at 20). The gradient is doing the work.

**Two important qualifiers.** First, the edits are **not fluent**: HotFlip has no language-model constraint, and most successful edits are non-words. This bounds an unconstrained white-box attacker, not a stealthy agent writing natural prose. Second, **"success" means crossing p = 0.865, not convincing the monitor the trace is benign.** The threshold-0.5 sensitivity check:

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

## What was done

1. **Data** (`data/`, Phase 1).
   - *Train pool:* R-Judge (571 real multi-turn records); InjecAgent (500 cases → 1,000 contrastive pairs, same prefix, agent follows vs ignores the injection); ToolEmu (288 synthetic pseudo-traces from case specs; the repo ships no trajectories and generating them needs a paid GPT-4 emulator).
   - *Held out:* ScaleAI MRT, the public SHADE-Arena-based dataset — 1,448 deduplicated traces from 5 tasks (371 benign; 1,077 sabotage with a successful side task), rendered exactly as MRT monitors see them (system prompt and hidden `<thinking>` removed).
   - Val slices are group-held-out: R-Judge by scenario file, InjecAgent by user tool, ToolEmu by case.
2. **Monitor** (`monitor/`, Phase 2).
   - Laya's binary `noul` question, fine-tuned with cross-entropy over the option markers (Laya's own notebook recipe, minus its RL noise term), 3 epochs, ~2 min on a Colab A100.
   - Long traces are scored with sliding 512-token windows; a trace's score is the max over windows.
3. **Baseline** (`baseline_eval.md`, Phase 3). AUROC / accuracy / ECE on held-out SHADE, plus zero-shot Laya and the original MRT LLM monitors as references.
4. **Attack** (`attack/`, `attack_eval.md`, Phases 4–5).
   - Greedy HotFlip over a smooth max of window margins, with top-48 exact re-scoring per step.
   - Budgets 1–20 swaps (60 for SHADE).
   - Agent-text-only and any-token scopes, a random baseline, and a retokenization check.
5. **Cross-source analysis** (`cross_source_analysis.md`, Phase 4.5). Per-source trained vs zero-shot quality, joined to attack fragility.

## Supporting results

- **Monitor quality on SHADE** (`baseline_eval.md`):
  - AUROC 0.577 (run 2), 0.513 (run 1), zero-shot 0.505. The MRT LLM monitors stored in the same transcripts reach 0.662.
  - At the operating threshold: TPR 0.98, FPR 0.92, accuracy 0.747 (the majority rate is 0.744), ECE 0.19.
  - Why: a window-level diagnostic found 64% of windows in *benign* SHADE traces are flagged, vs 73% in sabotage traces. The top-scoring benign windows are routine task actions (scheduled bank transfers, Venmo payments, flight searches). The monitor learned "money movement / bank details = attack" from InjecAgent, but in SHADE that's the job.
  - Removing the 188 traces where the agent literally writes "secondary task" doesn't change AUROC.
- **The in-distribution quality is weaker evidence than it looks.**
  - InjecAgent and ToolEmu are templated or synthetic, and ToolEmu has a lexical shortcut ("The agent may …" appears only in risky actions).
  - The one real-trajectory in-distribution source, R-Judge, is not reliably learned: 0.52–0.77 AUROC depending on run and scoring view, on n = 35.
  - A first R-Judge split by record was leaky (0.99 AUROC); I caught it and re-split by scenario file.
- **Versus the prior black-box result on Jev** (score moved ≤ 0.014 by hand-crafted tricks): white-box gradient edits move Laya's p by 0.1–0.2, often with one token, and cross the operating threshold for 44–90% of flagged in-distribution traces within 20 tokens. So the white-box ceiling is far higher. But it's a different model, task and data, and the edits are non-fluent, so this isn't a head-to-head (`attack_eval.md`).

## Limitations (please read before citing any number)

- **One architecture, one fine-tuning recipe, one attack method.** No fluency constraint on the attack; no adaptive or ensemble monitor; no adversarial training.
- **Small n where it matters.** R-Judge: 35 val traces, 9 attackable. SHADE: 20 attacked traces, and only 5 SHADE tasks exist in the public MRT release. expenditure_accounting has just 4 successful-sabotage traces.
- **Training-run variance.** The whole pipeline was trained twice with the same seed (the first VM was lost; see below). SHADE AUROC moved 0.51 → 0.58, R-Judge 0.77 → 0.52/0.66, and the operating threshold 0.41 → 0.87. Attack success depends on that threshold. Everything reported is run 2, the model that was attacked.
- **Synthetic training data.** Half the train pool (InjecAgent pairs, ToolEmu pseudo-traces) was constructed by me from benchmark specs, not collected from real agents.
- **Edit surfaces differ by source by construction.** The agent-text column isn't a matched comparison; the any-token column is.
- **Local-compute scale.** Training on the 18 GB Mac swapped heavily, so all GPU work ran on Colab A100s.
- **License.** MRT is CC BY-NC 4.0 (non-commercial), and its card asks that it not be used to train generative models. It was used for evaluation only. Flag this if the work moves toward anything commercial.

## What's still open / next steps

1. **Make the monitor good on SHADE first.** The plan forbade training on MRT. The natural next experiment is a *task-disjoint* split: train on some SHADE/MRT tasks, test on others, and add real-trajectory data (e.g. generate ToolEmu trajectories with an LLM emulator). Only a monitor with real SHADE skill makes "can the attack flip its SHADE verdicts" a meaningful question.
2. **Test quality vs fragility properly:** several real-trajectory sources spanning AUROC ~0.6–0.95, attacked under a *matched* edit surface (e.g. the same number of editable agent tokens per trace).
3. **Natural-language (stealth) attacks:** the fluency-constrained follow-up is done (below), but it produced mostly awkward or broken text. What's still open is whether an LLM agent rewriting its narration in natural prose, black-box against the monitor's score, can evade it. That's the experiment that would test stealth.
4. **Defenses the structure result suggests:**
   - Monitors that weight frozen evidence (tool calls and outputs) over agent-written prose.
   - Max-over-windows aggregation, which helps robustness here but destroys precision; a calibrated alternative is needed.

## How the night went (wall clock, PDT, from PROGRESS.md and git log)

- **00:19–00:23 · Phase 0.** Env; Laya loads on MPS (~30 ms/forward).
- **00:23–00:29 · Phase 1.** Data. MRT's HF repo is 11.5 GB with every run duplicated per monitor model, so I pulled ~230 MB of unique runs. HF rate-limited the unauthenticated download.
- **00:30–00:52 · Phase 2.** Local MPS training was infeasible (10 GB swap), so I moved to a Colab A100. The first `colab new` timed out client-side but still allocated a VM, which I found and released. I also found and fixed the leaky R-Judge split.
- **00:52–01:04 · Phase 3.** Eval took 4 min on the A100 for 47k windows.
- **01:04–01:46 · Phase 4, first attempt.** Stale processes caused a CUDA OOM, which I fixed. Then **the A100 VM was reclaimed server-side at ~01:46 and all in-flight attack results were lost**, because they weren't being synced. That was my mistake. I noticed only at ~02:14, when the user asked for status.
- **02:14–02:30 · Recovery.** New A100 requests timed out client-side while the server allocated them, so I adopted the allocated VM. The 1.7 GB checkpoint wouldn't upload, so I retrained (run 2) and re-evaluated. From then on: `caffeinate`, a 3-minute result-sync watchdog, attack `--resume`, and `scripts/recover_colab.sh` (restores the exact model via 50 MB chunks).
- **02:30–03:30 · Phase 4 rerun.** The user added Phase 4.5 at ~02:45. While preparing it I found an edit-scope bug that left ToolEmu almost un-attackable (the 96-token frozen prefix covered most of each ~100-token trace), fixed it, and restarted the in-distribution attacks. At 03:26 the CLI dropped its session record (likely token expiry), but the VM survived and was re-adopted; nothing was lost.
- **03:30–04:25 · Phase 5 / 4.5 analysis and write-up.** The threshold-0.5 sensitivity runs used a fresh A100: provisioning 03:40, exact run-2 weights restored via 50 MB chunks (checksum verified), runs finished 04:15, VM stopped.
- **For next time:** sync results continuously from the start; don't rely on `colab new` returning; keep weights somewhere the VM can pull from (an HF private repo or GCS) instead of uploading through the Jupyter API; poll for failure states, not just for "done" files.

## File map

- `SUMMARY.md` — this file.
- `cross_source_analysis.md` — the central table and analysis.
- `baseline_eval.md` — monitor quality.
- `attack_eval.md` — attack details and examples.
- `DECISIONS.md` — every judgment call.
- `PROGRESS.md` — timeline.
- `data/` — normalized datasets + stats.
- `monitor/` — config, calibration and logs; weights are local and gitignored.
- `results/` — metrics, scores and plots; run 1 is in `results/run1_model_v1/`.
- `attack/` — per-trace attack records, logs and summary.
- `scripts/` — everything that produced the above.

## Follow-up: fluency-constrained attack (see `fluency_attack_eval.md`, `fluent_edit_review.md`)

The original attack's edits were non-words. The follow-up restricted every substitution to the top-20 words base ModernBERT-large predicts for that position (same targets, thresholds, scopes, budgets). That's a constraint on *word-level plausibility*.
- **The constraint didn't reduce attack success.** With agent-text-only edits at the operating threshold, success at 20 swaps is 47% / 100% / 100% (InjecAgent / ToolEmu / R-Judge), vs 44% / 90% / 89% unconstrained. SHADE agent-only still mostly holds (19% within 60 swaps at n = 80).
- **Most successful edits change what the agent's narration claims happened, usually toward sounding more benign, while the frozen tool-call evidence is unchanged.** 67% of successful flips change the claim, 62% toward benign: "tweet was successfully posted" → "…generated"; "without determining off-peak hours" → "without violating off-peak hours". The monitor accepts the rewritten account even though the recorded actions contradict it. **This is a narrative-meaning vulnerability, not a stealth or undetectability finding.**
- **The edited text does not read naturally.** Only 2 of 73 successful flips were rated natural; 40% awkward, 58% visibly broken. Local GPT-2 perplexity (1.1–2.1× increase) turned out to be a poor proxy for readability. **Caveat:** these naturalness and meaning labels come from two LLM raters (κ 0.81–0.89), not humans. A 26-example side-by-side sample is provided for a human spot-check, but no human review has been done.
- **The untuned zero-shot checkpoint, on the same traces, is flipped far more easily** (InjecAgent agent text: 78% vs 36%, McNemar p ≈ 5e-10). That's mostly because its verdicts start much less confident (median p 0.67 vs 0.98), but also because it moves about 2× further per edit. The fine-tuned model's advantage is real on InjecAgent but partial, and absent or unmeasurable elsewhere (ToolEmu at ceiling; SHADE indistinguishable; R-Judge overlap only 6 traces).
- **Context:** these success rates sit at or above the best-case 47% approval rate that natural-language persuasion achieves against LLM CoT monitors (Za et al., arXiv 2607.08066). But persuasion uses natural-sounding generated text and this attack mostly doesn't, so the shared finding is that both monitor types can be moved by changing the agent's *account* relative to its actions. It isn't about undetectable evasion.

## Strengthening pass (see `widened_samples.md`, `fluent_edit_review.md`)

- **SHADE widened 20 → 80 flagged traces.** Agent-text-only edits flip 17% (unconstrained) / 19% (constrained) within 60 swaps (95% CIs 11–29%), ≤ 3% reach p < 0.5; any-token edits flip 66–67%. The conclusions are unchanged, with CIs about half as wide.
- **R-Judge held-out can't be widened** (all 9 flagged held-out traces were already attacked). A 60-trace training-split supplement flips less (20–27%) because the monitor is more confident on traces it trained on; margin-matched training traces flip 73%, close to the held-out 89%.
- **Edit review:** only 2 of 73 successful constrained flips were rated natural (40% awkward, 58% broken); 67% change what the text claims, 62% toward sounding more benign. Two independent LLM raters (κ 0.81–0.89), no human review yet.
