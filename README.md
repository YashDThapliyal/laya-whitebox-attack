# Laya as a Trusted Monitor: How Well Does It Generalize, and How Easily Can It Be Fooled?

AI control setups rely on a cheap "trusted monitor" that reads an agent's tool-use trace and flags harmful actions. Small typed-decision models like Jev and Laya are pitched for exactly this role, but prior robustness work only ran black-box attacks on the closed Jev model. Laya (`convaiinnovations/laya`, ModernBERT-large, 421M params, plus a decision head) is open-weight, so we can ask two things directly: does a fine-tuned Laya monitor generalize to realistic sabotage, and how cheaply can an attacker with full gradient access flip its verdicts?

## Results

The claims this evidence supports are at the top of [`results/aaai27/analysis.md`](results/aaai27/analysis.md), and they govern where any older write-up in this repo reads stronger. The workshop paper is [`paper/main.tex`](paper/main.tex).

**Editing only the agent's narration flips verdicts on all three retrained monitors, most often where narration is most of the evidence.** Unconstrained agent-text attack, budget 20, common bar p < 0.5:

| | seed 0 | seed 1 | seed 2 |
|---|---|---|---|
| ToolEmu | 19 / 21 [71, 97]% | 20 / 22 [72, 97]% | 20 / 22 [72, 97]% |
| InjecAgent | 25 / 87 [20, 39]% | 32 / 87 [27, 47]% | 15 / 87 [11, 27]% |
| InjecAgent, direct harm | 24 / 42 [42, 71]% | 23 / 42 [40, 69]% | 14 / 42 [21, 48]% |
| InjecAgent, data stealing | 1 / 45 [0, 12]% | 9 / 45 [11, 34]% | 1 / 45 [0, 12]% |

- **The ordering replicates, the magnitude does not pin down.** The InjecAgent rate spreads from 17% to 37% across monitors with clean AUROC 1.000. The comparison is post hoc, so it is suggestive.
- **Hiding narration stops these edits, at a cost where narration was the only evidence.** On seed 0, ToolEmu falls from AUROC 1.000 to 0.500 when narration is removed, while InjecAgent stays at 0.991. The non-adaptive any-token attack produced no realizable flip under masking, but no attack was adapted to it (finding 6).
- **Flips are largely specific to the attacked monitor.** Agent-text edits transfer to other Laya checkpoints above random edits, 16 to 31% of the time, and do not move a Claude Haiku 5.5 judge beyond random noise (finding 7).
- **R-Judge and SHADE are near chance on clean traces,** so their attack numbers are reported separately and not used for claims.

*Seed 0 (run 2) at its own operating threshold p = 0.865, by source.* Attack success is the share of correctly flagged violating traces pushed below the threshold within 20 token substitutions (SHADE @60 in parentheses).

| Source | Monitor AUROC [95% CI] | Agent-text edits, unconstrained | Agent-text edits, plausible-word constrained | Any-token edits | Random substitutions (agent text) |
|---|---|---|---|---|---|
| InjecAgent (templated pairs, n = 87) | 1.00 [1.00, 1.00] | 0.44 | 0.47 | 1.00 | 0.00–0.14 across sources |
| ToolEmu (synthetic, n = 21) | 1.00 [1.00, 1.00] | 0.90 | 1.00 | 1.00 | |
| R-Judge (real trajectories, n = 9) | 0.52 [0.33, 0.72] | 0.89 | 1.00 | 1.00 | |
| SHADE-Arena / MRT (held out, n = 80) | 0.58 [0.55, 0.61] | 0.12 (0.17) | 0.15 (0.19) | 0.47 (0.66) | |

The fine-tuned monitor is near-perfect on its training-style sources, but on held-out SHADE-Arena sabotage it's near chance (AUROC 0.58) and flags 92% of benign traces. On traces that keep a frozen record of the action, 7 of 18 human-reviewed edits change what the agent's narration *claims* happened, which hints that the monitor sometimes trusts the agent's account over the record. The sample is small.

## What this actually tests

- **Attacker access:** white-box. The attacker has the monitor's weights and gradients and uses HotFlip-style greedy token substitution: first-order candidate scoring, then exact re-scoring of the top 48 candidates. The objective is the trace score, which is the max over sliding 512-token windows.
- **What the attacker may edit:**
  - *Agent text* (default): the agent's own narration and messages. Tool calls, tool outputs, the user request and the environment are frozen.
  - *Any token*: everything except structural lines. This is an upper bound, not a realistic threat.
- **Plausible-word constraint** (`--fluent_k 20`): each swap must be among base ModernBERT-large's top-20 masked-LM predictions at that position.
- **Four sources:**
  - R-Judge: real agent trajectories.
  - InjecAgent: prompt-injection cases turned into follow/ignore pairs.
  - ToolEmu: pseudo-traces built from case specs.
  - SHADE-Arena: realistic sabotage transcripts from ScaleAI MRT. The monitor never trained on it.
- **Why attack a monitor that doesn't generalize:** the attack tests the recipe, not just this checkpoint. Where the monitor *does* work (InjecAgent, ToolEmu, AUROC 1.00), the question is whether a Laya monitor that's accurate can also be robust.
- **Success, precisely:** an attack targets a trace that is truly violating *and* correctly flagged by the monitor. It succeeds if the trace's score drops below the threshold within the swap budget. The main bar is the operating threshold p = 0.865; the stricter bar is p < 0.5. Success also has to survive decoding and re-tokenizing the edited text, and the linked files report that rate.

## Findings

### 1. The monitor doesn't generalize to realistic sabotage

- On held-out slices of its training-style data it reaches AUROC 1.00 on InjecAgent and ToolEmu but only 0.52 on R-Judge. Pooled over all 255 validation traces it's 0.99 (0.987 with the same windowed scoring as the per-source numbers; `results/val_pooled_windowed_auroc.json`); that blended figure is dominated by InjecAgent and ToolEmu (220 of the 255).
- On 1,448 held-out SHADE-Arena traces it reaches 0.577 [0.55, 0.61]. The original MRT LLM monitors score 0.66 on the same traces.
- At its operating threshold it flags 92% of benign SHADE traces, so as a deployed monitor it would mostly raise false alarms.
- The untuned zero-shot Laya checkpoint does worse on SHADE (AUROC 0.51).

Details: [`baseline_eval.md`](baseline_eval.md).

### 2. Editing only narration flips verdicts most often where narration is most of the evidence

- **The source ordering replicates on three monitors, for agent-text edits.** ToolEmu, where narration is the only evidence, flips about 90%. InjecAgent, whose attacker calls cannot be edited, flips 17 to 37%. Direct harm (one frozen attacker call) flips far more than data stealing (two).
- **The magnitude does not pin down.** Seeds 1 and 2 differ significantly on InjecAgent (paired exact McNemar p = 0.0009, unadjusted), though both have clean AUROC 1.000. The three monitors are not a confidence interval over seeds.
- **It is an agent-text result.** Any-token edits flip both sources about equally: ToolEmu 18 / 21, 22 / 22 and 22 / 22, InjecAgent 79 / 87, 80 / 87 and 66 / 87.
- **Clean margin predicts success as a pooled effect.** On InjecAgent + ToolEmu it is significant on seed 0 and pooled, but not on seeds 1 and 2 alone.
- **Editable fraction is not claimed as the mechanism.** It predicts success on its own but cannot be separated from window count, and within InjecAgent it has no detectable effect once case type is controlled. An earlier, larger run-2 estimate came mostly from SHADE.
- **On SHADE, agent-text edits mostly fail** (17% within 60 swaps, n = 80). The flag comes from many windows of tool output the agent can't touch. Allowed any token, the attack flips about two-thirds. SHADE is near chance on clean traces, so this is not a robustness result.
- **The evidence is thin.** Two usable sources, one templated and one synthetic, and a post hoc comparison, so it is suggestive rather than established.

Details: [`results/aaai27/analysis.md`](results/aaai27/analysis.md), and for run 2 by source, [`cross_source_analysis.md`](cross_source_analysis.md), [`attack_eval.md`](attack_eval.md), [`widened_samples.md`](widened_samples.md).

### 3. Restricting swaps to plausible words doesn't stop the attack

- Requiring every swap to be a top-20 masked-LM prediction left success unchanged or slightly higher: 47% / 100% / 100% on InjecAgent / ToolEmu / R-Judge, vs 44% / 90% / 89% unconstrained.
- On SHADE (n = 80) the constrained attack reaches 19% vs 17% at 60 swaps.
- "Plausible" is local. Each swapped word fits its slot according to the language model, but several swaps in one sentence compound into broken text (finding 5).
- **A better-calibrated checkpoint resists more, on one source.** On the same 85 InjecAgent traces, the plausible-word attack pushes the untuned zero-shot checkpoint below p = 0.5 on 78% of them vs 36% for the fine-tuned one (McNemar p ≈ 5e-10). At each model's own alarm threshold it's 78% vs 46%. The main reason is that its verdicts start far less confident (median p 0.67 vs 0.98); each edit also moves it about 2× further. On other sources there's no measurable difference.
- **On traces the monitor trained on**, a 60-trace R-Judge train-split supplement is harder: 20–27% overall. When matched to the held-out traces' starting confidence it's 73%.

Details: [`fluency_attack_eval.md`](fluency_attack_eval.md).

### 4. What the edits actually do: where there's a record, they contradict it

- On traces that keep a frozen record of the action (InjecAgent, R-Judge, SHADE), some successful edits change the claim the agent's narration makes, toward sounding more benign, while the record still shows the harmful action. Examples:
  - R-Judge: "the tweet was successfully *posted*" → "*generated*", with the frozen `TwitterManagerPostTweet` call still in the trace.
  - InjecAgent: the agent's final answer quoting "*Please redirect* my shipment" → "*Cannot update* my shipment", with the frozen `FedExShipManagerManageShipment` call still in the trace.
- In the human-reviewed sample this is **7 of 18 edits (39%, 95% CI 20–61%)**. On the same 18 items the LLM raters say 9 of 18 (50%) toward benign, and over all 52 edits from these sources 28 of 52 (54%); they agree only weakly with the human on meaning (κ 0.28).
- This hints that the monitor sometimes trusts the agent's account over its recorded actions, so an agent that controls its own narration may be able to steer it. The sample is small.
- **ToolEmu is different.** Its pseudo-traces have no separate record: the editable `[AGENT ACTION]` line is the only evidence of what the agent did. An edit like "without *determining* off-peak hours" → "without *violating*" rewrites the evidence itself, so it doesn't support the narrative-vs-record reading. 7 of the 14 meaning-changing items in the human sample are ToolEmu.
- Za et al. ([arXiv 2607.08066](https://arxiv.org/abs/2607.08066)) are the closest related work. In their adversarial setting, giving an LLM monitor the agent's chain of thought raises its approval of harmful actions by 9.5% on average, because the scratchpad is a persuasion channel. A fact-checker from a different model family cuts approval of policy-violating actions by up to 45%, against 6% when one model fills both roles, which parallels the Haiku result in finding 7. Their arguments are fluent and generated and their monitors are LLMs, so this is context rather than a head-to-head.

Details: [`fluent_edit_review.md`](fluent_edit_review.md).

### 5. Correction after human review: the edits are not natural, and the meaning rate is lower

- Two LLM raters labelled all 73 successful constrained edits (InjecAgent, ToolEmu, R-Judge and SHADE). A human then reviewed a stratified sample of 26.
- **Naturalness:** the human confirmed the LLM labels (88% agreement, κ 0.78). 58% of edits are visibly broken, 40% awkward, and only 2 of 73 read naturally. This is not a stealth result: a careful human reader would likely catch most of these edits.
- **Meaning change:** the human agreed only weakly with the raters (κ 0.28). Across all sources, the human put the rate of edits that change the text's claim at **54%** (95% CI about 35–72%), against the raters' 65% on the same 26 items (67% over all 73). On traces with a frozen action record it's **39%** (finding 4).
- A later check of the traces behind the examples found that the ToolEmu edits have no record to contradict. Finding 4 is scoped accordingly.

Details: [`fluent_edit_review.md`](fluent_edit_review.md) (the "Human spot-check" section), `results/human_spotcheck.json`.

### 6. Hiding narration stops these edits, at a cost where narration was the only evidence

- **Detection.** On seed 0, clean AUROC under full / mask / remove is 1.000 / 0.662 / 0.500 on ToolEmu and 1.000 / 0.997 / 0.991 on InjecAgent. Masking was not run on seeds 1 and 2.
- **Agent-text attacks** flip 0 / 98 under mask and 0 / 83 under remove, by construction, since nothing they can edit is left. On ToolEmu the attack goes away with the detection: 12 of 21 detections survive mask and none survive remove.
- **Any-token attacks** give 187 flips across the view and attack cells, all on InjecAgent. Of these, 165 neutralize the harmful action by editing the tool call, and the other 22 rewrite a role tag, which an agent cannot do when roles come from the agent API. No flip edits tool outputs alone.

Details: [`results/aaai27/analysis.md`](results/aaai27/analysis.md), section 5.

### 7. The flips are largely specific to the attacked monitor

- **Other Laya checkpoints.** Without R-Judge targets, agent-text edits transfer 16 to 31% of the time, above random edits (Holm p of at most 0.014). Any-token edits do not clear a matched random control: 10 / 108 against 3 / 108 on an earlier fine-tune (p = 0.083) and 11 / 100 against 14 / 100 on untuned Laya (p = 0.67).
- **An LLM judge.** On the 103 traces Claude Haiku 5.5 stably flags, attack edits flip 4 and 7 against 9 for random edits, all on ToolEmu. This says nothing about how hard Haiku is to attack directly.
- **Retrained copies.** On InjecAgent, about 30% of the traces that flip on either of two seeds flip on both (13 / 44, 9 / 31, 11 / 36), above the 19, 12 and 13% independence would give.

Details: [`results/aaai27/analysis.md`](results/aaai27/analysis.md), sections 6 to 8.

## What this doesn't show

- **Masking met only non-adaptive attacks.** Edits were optimized against the full view and rescored in each view. No attack restricted to tool outputs under masking was run.
- **Black-box or realistic attackers weren't tested.** Every attack here uses white-box gradient access. The open question is whether an LLM agent rewriting its own narration in natural prose, without gradients, fools the monitor.
- **Stealth isn't shown.** Most successful edits are awkward or broken text.
- **The narrative-vs-record rate is small-sample.** It rests on 18 human-reviewed edits from traces with a frozen action record.
- **Much of the training data is synthetic.** Half the training pool (InjecAgent pairs, ToolEmu pseudo-traces) was built from benchmark specs, not collected from real agents.
- **Samples of real data are small.**
  - R-Judge has 9 held-out attackable traces, a number that can't grow. The 60-trace train-split supplement is reported separately.
  - The public MRT release covers only 5 SHADE tasks.
  - The meaning-change rate rests on 26 human-reviewed edits.
- **Scope is narrow:** one architecture, one fine-tuning recipe, one attack family. Other monitors may behave differently.
- **Run-to-run variance is material.** Two identical-seed training runs gave SHADE AUROC 0.51 vs 0.58, with operating thresholds 0.41 vs 0.87. The run-2 tables use that model; the three-seed results are in [`results/aaai27/analysis.md`](results/aaai27/analysis.md).
- **The MRT license is non-commercial.** ScaleAI MRT is CC BY-NC 4.0 and was used for evaluation only.

## Reproduce it

**Setup.** Local analysis ran on macOS (M3 Pro). Training and attacks ran on Colab A100s; MPS training swaps on 18 GB.

```bash
uv venv --python 3.11 .venv && source .venv/bin/activate
uv pip install laya torch transformers datasets scikit-learn matplotlib huggingface_hub pandas scipy statsmodels anthropic
export PYTHONPATH=scripts
```

**Data.** Clone R-Judge, ToolEmu and InjecAgent into `raw/` (URLs in [`laya-monitor-attack-plan.md`](laya-monitor-attack-plan.md) §1.5). Then:

```bash
python scripts/download_mrt.py      # ScaleAI MRT transcripts -> raw/
python scripts/normalize.py         # -> data/train_pool.jsonl (scenario-level train/val split), data/eval_heldout.jsonl
```

**Train and evaluate the monitor**

```bash
python scripts/train_monitor.py --epochs 3 --bs 16 --accum 1                 # -> monitor/laya-monitor, monitor/calibration.json (~2 min on A100)
python scripts/eval_monitor.py --tag finetuned                               # -> results/baseline_finetuned.json, heldout_scores_finetuned.jsonl
python scripts/eval_monitor.py --model base --tag zeroshot                   # untuned checkpoint
python scripts/zeroshot_targets.py                                           # zero-shot calibration + attack targets
python scripts/cross_source_eval.py                                          # per-source AUROC -> results/cross_source_auroc.json
```

**Attacks.** One run per line. Outputs go to `attack/<name>.jsonl`.

```bash
# in-distribution val targets (InjecAgent / ToolEmu / R-Judge), 20 swaps
python scripts/attack.py --data data/train_pool.jsonl --scores compute --n 200 --budget 20 --scope agent --out attack/val_agent.jsonl
python scripts/attack.py --data data/train_pool.jsonl --scores compute --n 200 --budget 20 --scope agent --random_baseline --out attack/val_agent_random.jsonl
python scripts/attack.py --data data/train_pool.jsonl --scores compute --n 200 --budget 20 --scope all --out attack/val_all.jsonl

# held-out SHADE targets, 60 swaps
python scripts/attack.py --n 20 --budget 60 --max_windows 25 --scope agent --out attack/mrt_agent.jsonl
python scripts/attack.py --n 20 --budget 60 --max_windows 25 --scope all --out attack/mrt_all.jsonl

# plausible-word constrained variant (run to p < 0.5; the 0.865 bar is read off the same path)
python scripts/attack.py --data data/train_pool.jsonl --scores compute --n 200 --budget 20 --threshold 0.5 --fluent_k 20 --scope agent --out attack/f_val_agent.jsonl
python scripts/attack.py --n 20 --budget 60 --max_windows 25 --threshold 0.5 --fluent_k 20 --scope agent --out attack/f_mrt_agent.jsonl

# widened SHADE (60 more targets) and zero-shot checkpoint
python scripts/attack.py --n 20 --budget 60 --max_windows 25 --fluent_k 20 --scope agent --target_ids attack/targets_ft_mrt_new60_agent.json --out attack/x_f_mrt_agent.jsonl
python scripts/attack.py --model base --calib monitor/zeroshot_calibration.json --scores results/heldout_scores_zeroshot.jsonl \
    --n 20 --budget 60 --max_windows 25 --fluent_k 20 --scope agent --target_ids attack/targets_zs_mrt_agent.json --out attack/z_mrt_agent.jsonl
```

Add `--resume` to continue a partial run. `scripts/recover_colab.sh <name>` re-provisions an A100 and restores the exact weights in 50 MB chunks with a checksum.

**Analyses.** Each reads `attack/*.jsonl` and writes to `results/`.

```bash
python scripts/analyze_attack.py       # success vs budget, examples -> attack/summary.json, success_vs_budget.png
python scripts/cross_source_table.py   # quality vs fragility -> results/cross_source_table.{json,md}
python scripts/fluent_analysis.py      # constrained vs unconstrained, fine-tuned vs zero-shot -> results/fluent_analysis.json
python scripts/widen_analysis.py       # SHADE-80 and R-Judge train supplement -> results/widen_analysis.json
python scripts/perplexity.py           # GPT-2 local perplexity of edits -> results/perplexity.json
python scripts/edit_review.py          # reconstruct successful edits for review -> results/edit_review_items.{json,md}
```

**Layout**

```
data/      normalized datasets and stats.json
monitor/   calibration + training logs; weights (*.safetensors, 1.7 GB) are gitignored and exist locally only
results/   metrics, per-trace scores, edit labels (LLM raters + human spot-check), analysis outputs
attack/    per-trace attack records and logs for every run, target lists
scripts/   everything that produced the above
```

The full write-up is [`SUMMARY.md`](SUMMARY.md), with the follow-up work collected in [`fluency_experiment_full.md`](fluency_experiment_full.md). Every judgment call is logged in [`DECISIONS.md`](DECISIONS.md), and the timeline, including infrastructure incidents, is in [`PROGRESS.md`](PROGRESS.md).
