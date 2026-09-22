# Laya as a Trusted Monitor: How Well Does It Generalize, and How Easily Can It Be Fooled?

AI control setups rely on a cheap "trusted monitor" that reads an agent's tool-use trace and flags harmful actions. Small typed-decision models like Jev and Laya are pitched for exactly this role, but prior robustness work only ran black-box attacks on the closed Jev model. Laya (`convaiinnovations/laya`, ModernBERT-large, 421M params, plus a decision head) is open-weight, so we can ask two things directly: does a fine-tuned Laya monitor generalize to realistic sabotage, and how cheaply can an attacker with full gradient access flip its verdicts?

## Results

Fine-tuned monitor, operating threshold p = 0.865. Attack success is the share of correctly flagged violating traces pushed below the threshold within 20 token substitutions (SHADE @60 in parentheses).

| Source | Monitor AUROC [95% CI] | Agent-text edits, unconstrained | Agent-text edits, plausible-word constrained | Any-token edits | Random substitutions (agent text) |
|---|---|---|---|---|---|
| InjecAgent (templated pairs, n = 87) | 1.00 [1.00, 1.00] | 0.44 | 0.47 | 1.00 | 0.00–0.14 across sources |
| ToolEmu (synthetic, n = 21) | 1.00 [1.00, 1.00] | 0.90 | 1.00 | 1.00 | |
| R-Judge (real trajectories, n = 9) | 0.52 [0.33, 0.72] | 0.89 | 1.00 | 1.00 | |
| SHADE-Arena / MRT (held out, n = 80) | 0.58 [0.55, 0.61] | 0.12 (0.17) | 0.15 (0.19) | 0.47 (0.66) | |

The fine-tuned monitor is near-perfect on its training-style sources, but on held-out SHADE-Arena sabotage it's near chance (AUROC 0.58) and flags 92% of benign traces. Where the incriminating evidence is text the agent writes, 20 gradient-chosen word swaps flip 44–100% of its correct verdicts. That holds even when every swap must be a word a language model finds plausible in context. On traces that keep a frozen record of the action, about 4 in 10 successful edits change what the agent's narration *claims* happened, and the monitor believes the new claim over the record.

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

- On held-out slices of its training-style data it reaches AUROC 1.00 on InjecAgent and ToolEmu but only 0.52 on R-Judge. Pooled over all 255 validation traces it's 0.99; that blended figure is dominated by InjecAgent and ToolEmu (220 of the 255).
- On 1,448 held-out SHADE-Arena traces it reaches 0.577 [0.55, 0.61]. The original MRT LLM monitors score 0.66 on the same traces.
- At its operating threshold it flags 92% of benign SHADE traces, so as a deployed monitor it would mostly raise false alarms.
- The untuned zero-shot Laya checkpoint does worse on SHADE (AUROC 0.51).

Details: [`baseline_eval.md`](baseline_eval.md).

### 2. Structure predicts fragility, not monitor quality

- Sources with equally good monitors differ 2× in attack success (InjecAgent 0.44 vs ToolEmu 0.90), and equally poor ones differ about 9×.
- Across per-source attack settings, success correlates with how much of the trace the attacker can edit (Spearman ρ = +0.65) and with how many windows the trace spans (ρ = −0.66). It doesn't correlate with monitor AUROC.
- On SHADE, agent-text edits mostly fail (17% within 60 swaps, n = 80). The flag comes from many windows of tool output the agent can't touch. Allowed any token, the attack flips about two-thirds.
- On the two near-chance sources (R-Judge 0.52, SHADE 0.58), "correct" verdicts are partly lucky guesses, so flipping them says less about robustness than on InjecAgent and ToolEmu. The within-source InjecAgent split in `cross_source_analysis.md` (83% vs 7% by how much of the evidence is frozen) is the cleaner test.
- Only four sources back this, two of them synthetic, so it's suggestive rather than established.

Details: [`cross_source_analysis.md`](cross_source_analysis.md), [`attack_eval.md`](attack_eval.md), [`widened_samples.md`](widened_samples.md).

### 3. Restricting swaps to plausible words doesn't stop the attack

- Requiring every swap to be a top-20 masked-LM prediction left success unchanged or slightly higher: 47% / 100% / 100% on InjecAgent / ToolEmu / R-Judge, vs 44% / 90% / 89% unconstrained.
- On SHADE (n = 80) the constrained attack reaches 19% vs 17% at 60 swaps.
- "Plausible" is local. Each swapped word fits its slot according to the language model, but several swaps in one sentence compound into broken text (finding 5).
- **A better-calibrated checkpoint resists more, on one source.** On the same 85 InjecAgent traces, the untuned zero-shot checkpoint is flipped 78% of the time vs 36% for the fine-tuned one (McNemar p ≈ 5e-10). The main reason is that its verdicts start far less confident (median p 0.67 vs 0.98); each edit also moves it about 2× further. On other sources there's no measurable difference.
- **On traces the monitor trained on**, a 60-trace R-Judge train-split supplement is harder: 20–27% overall. When matched to the held-out traces' starting confidence it's 73%.

Details: [`fluency_attack_eval.md`](fluency_attack_eval.md).

### 4. What the edits actually do: where there's a record, they contradict it

- On traces that keep a frozen record of the action (InjecAgent, R-Judge, SHADE), some successful edits change the claim the agent's narration makes, toward sounding more benign, while the record still shows the harmful action. Examples:
  - R-Judge: "the tweet was successfully *posted*" → "*generated*", with the frozen `TwitterManagerPostTweet` call still in the trace.
  - InjecAgent: the agent's final answer quoting "*Please redirect* my shipment" → "*Cannot update* my shipment", with the frozen `FedExShipManagerManageShipment` call still in the trace.
- In the human-reviewed sample this is **7 of 18 edits (39%, 95% CI 20–61%)**. The LLM raters say 32 of 52 (62%) on the same sources, but they agree only weakly with the human on meaning.
- Where it applies, the monitor trusts the agent's account over its recorded actions. That's a **narrative-meaning vulnerability**: an agent that controls its own narration can steer the monitor.
- **ToolEmu is different.** Its pseudo-traces have no separate record: the editable `[AGENT ACTION]` line is the only evidence of what the agent did. An edit like "without *determining* off-peak hours" → "without *violating*" rewrites the evidence itself, so it doesn't support the narrative-vs-record reading. 7 of the 14 meaning-changing items in the human sample are ToolEmu.
- Za et al. ([arXiv 2607.08066](https://arxiv.org/abs/2607.08066)) report a best-case 47% approval rate for natural-language persuasion against LLM chain-of-thought monitors. Their arguments are fluent and generated, and their monitor type differs, so this is context rather than a head-to-head.

Details: [`fluent_edit_review.md`](fluent_edit_review.md).

### 5. Correction after human review: the edits are not natural, and the meaning rate is lower

- Two LLM raters labelled all 73 successful constrained edits (InjecAgent, ToolEmu, R-Judge and SHADE). A human then reviewed a stratified sample of 26.
- **Naturalness:** the human confirmed the LLM labels (88% agreement, κ 0.78). 58% of edits are visibly broken, 40% awkward, and only 2 of 73 read naturally. This is not a stealth result: a careful human reader would likely catch most of these edits.
- **Meaning change:** the human agreed only weakly with the raters (κ 0.28). Across all sources, the rate of edits that change the text's claim dropped from the raters' 67% to **54%** (95% CI about 35–72%). On traces with a frozen action record it's **39%** (finding 4).
- A later check of the traces behind the examples found that the ToolEmu edits have no record to contradict. Finding 4 is scoped accordingly.

Details: [`fluent_edit_review.md`](fluent_edit_review.md) (the "Human spot-check" section), `results/human_spotcheck.json`.

## What this doesn't show

- **Black-box or realistic attackers weren't tested.** Every attack here uses white-box gradient access. The open question is whether an LLM agent rewriting its own narration in natural prose, without gradients, fools the monitor.
- **Stealth isn't shown.** Most successful edits are awkward or broken text.
- **The narrative-vs-record rate is small-sample.** It rests on 18 human-reviewed edits from traces with a frozen action record.
- **Much of the training data is synthetic.** Half the training pool (InjecAgent pairs, ToolEmu pseudo-traces) was built from benchmark specs, not collected from real agents.
- **Samples of real data are small.**
  - R-Judge has 9 held-out attackable traces, a number that can't grow. The 60-trace train-split supplement is reported separately.
  - The public MRT release covers only 5 SHADE tasks.
  - The meaning-change rate rests on 26 human-reviewed edits.
- **Scope is narrow:** one architecture, one fine-tuning recipe, one attack family. Other monitors may behave differently.
- **Run-to-run variance is material.** Two identical-seed training runs gave SHADE AUROC 0.51 vs 0.58, with operating thresholds 0.41 vs 0.87. Everything reported uses run 2, the model that was attacked.
- **The MRT license is non-commercial.** ScaleAI MRT is CC BY-NC 4.0 and was used for evaluation only.

## Reproduce it

**Setup.** Local analysis ran on macOS (M3 Pro). Training and attacks ran on Colab A100s; MPS training swaps on 18 GB.

```bash
uv venv --python 3.11 .venv && source .venv/bin/activate
uv pip install laya torch transformers datasets scikit-learn matplotlib huggingface_hub pandas scipy
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
