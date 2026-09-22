# Laya as a trusted monitor for agent traces: quality and white-box fragility

This project fine-tunes **Laya** (`convaiinnovations/laya`: ModernBERT-large, 421M, plus a typed-decision head) into a binary "is this agent trace policy-violating?" monitor. It then attacks the monitor with a **white-box, gradient-guided token-substitution attack** (HotFlip), on its training-style data and on held-out **SHADE-Arena** traces (ScaleAI MRT).

## Headline findings

1. **The monitor doesn't transfer to realistic sabotage.** It's near-perfect on held-out slices of its training-style data (AUROC 1.00 on InjecAgent/ToolEmu) but near chance on held-out SHADE-Arena traces (AUROC 0.58, 95% CI 0.55–0.61). At its operating threshold it flags 92% of *benign* SHADE traces. The original MRT LLM monitors reach 0.66 on the same traces.
2. **The white-box attack flips correct "violating" verdicts cheaply wherever the incriminating evidence is text the attacker writes.** Editing only the agent's own text, 20 substitutions flip 44–90% of correctly flagged in-distribution traces; random substitutions flip 0–14%. On SHADE, agent-text edits mostly fail (17% within 60 swaps, n = 80), because the monitor's flag comes from many windows of tool output the agent can't edit. With any token editable, 100% of in-distribution and about two-thirds of SHADE flags flip.
3. **Fragility doesn't track monitor quality; it tracks trace structure.** Equally good sources differ 2× in fragility and equally bad ones ~9×. Success correlates with the fraction of the trace the attacker can edit (Spearman ρ = +0.65) and with window count (ρ = −0.66), not with how good the monitor is on that source. That's four sources, two of them synthetic: suggestive, not established.
4. **A narrative-meaning vulnerability, not a stealth result.** Restricting every substitution to locally plausible words (top-20 masked-LM predictions) **did not reduce attack success** (47% / 100% / 100% on InjecAgent / ToolEmu / R-Judge vs 44% / 90% / 89% unconstrained). **Most successful edits work by changing what the agent's narration claims happened**, usually toward sounding more benign, while the frozen tool-call evidence of what actually happened is unchanged. Examples: "the tweet was successfully *posted*" → "*generated*"; "without *determining* off-peak hours" → "without *violating* off-peak hours". 67% of successful edits change the claim and 62% shift it toward benign. The monitor trusts the agent's account over its recorded actions. The edits are **not** natural or unnoticeable: 58% are visibly broken, 40% awkward, and only 2 of 73 read naturally, so a careful human would likely catch most of them. **Caveat:** these naturalness and meaning labels come from two independent **LLM raters** (κ 0.81–0.89), not humans. A 26-example side-by-side sample is provided for human spot-checking; no human review has been done yet.
5. **A better-calibrated checkpoint resists more, on one source only.** On the same 85 InjecAgent traces, the untuned zero-shot Laya checkpoint is flipped 78% of the time vs 36% for the fine-tuned one (McNemar p ≈ 5e-10). That's mostly because its verdicts start far less confident, partly because each edit moves it ~2× further. Elsewhere there's no measurable difference.

**Context:** the constrained attack's success rates sit at or above the best-case 47% approval rate that natural-language persuasion achieves against LLM chain-of-thought monitors ([Za et al., arXiv 2607.08066](https://arxiv.org/abs/2607.08066)). That paper uses natural-sounding generated arguments and a different monitor type, so this is context, not a direct comparison. The shared lesson is that both monitor types can be moved by changing the agent's *account* relative to its actions. **An actual stealth test is still open:** an LLM agent rewriting its narration in natural prose, black-box.

## Where to read

| Read this | For |
|---|---|
| [`SUMMARY.md`](SUMMARY.md) | The whole project: headline, central table, method, limitations, what's open, how the night went |
| [`cross_source_analysis.md`](cross_source_analysis.md) | The central result: per-source monitor quality vs attack fragility |
| [`baseline_eval.md`](baseline_eval.md) | Monitor quality on held-out SHADE (AUROC, ECE, per task and strategy) |
| [`attack_eval.md`](attack_eval.md) | The original (unconstrained) attack: setup, curves, examples, Jev comparison |
| [`fluency_experiment_full.md`](fluency_experiment_full.md) | **Self-contained** write-up of the follow-up work: constrained attack, zero-shot comparison, edit review, widened samples |
| [`fluency_attack_eval.md`](fluency_attack_eval.md) · [`fluent_edit_review.md`](fluent_edit_review.md) · [`widened_samples.md`](widened_samples.md) | The three parts of that follow-up, as separate files |
| [`DECISIONS.md`](DECISIONS.md) · [`PROGRESS.md`](PROGRESS.md) | Every judgment call, and the timeline including infrastructure incidents |
| [`laya-monitor-attack-plan.md`](laya-monitor-attack-plan.md) | The original plan/spec |

## Key numbers

Fine-tuned monitor. Success = a correctly flagged violating trace pushed below the operating threshold (p = 0.865) within the budget, editing only agent-authored text.

| Source | Monitor AUROC [95% CI] | Unconstrained @20 | Constrained @20 | Any-token (unconstrained) @20 |
|---|---|---|---|---|
| InjecAgent (templated pairs, n = 87) | 1.00 [1.00, 1.00] | 0.44 | 0.47 | 1.00 |
| ToolEmu (synthetic, n = 21) | 1.00 [1.00, 1.00] | 0.90 | 1.00 | 1.00 |
| R-Judge (real trajectories, n = 9) | 0.52 [0.33, 0.72] | 0.89 | 1.00 | 1.00 |
| SHADE / MRT (held out, n = 80) | 0.58 [0.55, 0.61] | 0.12 (0.17 @60) | 0.15 (0.19 @60) | 0.47 (0.66 @60) |

The stricter p < 0.5 bar, Wilson CIs, per-budget curves and retokenization checks are in the linked files.

## Repository layout

```
data/        normalized datasets: train_pool.jsonl (R-Judge, InjecAgent pairs, ToolEmu pseudo-traces; train/val split),
             eval_heldout.jsonl (1,448 MRT/SHADE traces), stats.json
monitor/     calibration + training logs; laya-monitor/ (reported model, run 2) and laya-monitor-v2/ backup;
             zeroshot_calibration.json. Weights (*.safetensors, 1.7 GB) are gitignored and exist locally only.
results/     metrics, per-trace scores, plots, cross-source / fluency / widening / edit-review outputs
attack/      per-trace attack records (*.jsonl) and logs for every run, target lists, summaries, plots
scripts/     everything that produced the above (see below)
raw/         downloaded source repos and MRT transcripts (gitignored)
```

## Reproducing

**Environment** (the local runs used macOS on an M3 Pro; training and attacks ran on Colab A100s):
```bash
uv venv --python 3.11 .venv && source .venv/bin/activate
uv pip install laya torch transformers datasets scikit-learn matplotlib huggingface_hub pandas scipy
export PYTHONPATH=scripts
```

**Pipeline**

| Step | Command | Notes |
|---|---|---|
| Data | clone R-Judge, ToolEmu, InjecAgent into `raw/` (URLs in the plan, §1.5); `python scripts/download_mrt.py`; `python scripts/normalize.py` | MRT index/selection logic is described in DECISIONS.md, Phase 1 |
| Train | `python scripts/train_monitor.py --epochs 3 --bs 16 --accum 1` | ~2 min on an A100; local MPS training swaps on 18 GB |
| Baseline eval | `python scripts/eval_monitor.py --tag finetuned` · `--model base --tag zeroshot` | windowed max-over-windows scoring |
| Per-source quality | `python scripts/cross_source_eval.py` | trained vs zero-shot AUROC on existing val slices |
| Attack | `python scripts/attack.py [--scope agent\|all] [--random_baseline] [--fluent_k 20] [--threshold 0.5] [--target_ids F] [--model base --calib monitor/zeroshot_calibration.json]` | `--resume` continues from a partial output file |
| Analyses | `analyze_attack.py`, `cross_source_table.py`, `fluent_analysis.py`, `perplexity.py`, `zeroshot_targets.py`, `widen_analysis.py`, `edit_review.py` | each script's docstring says what it reads and writes |
| Colab recovery | `scripts/recover_colab.sh <name>` | re-provisions an A100 and restores the exact weights in 50 MB chunks |

A trace's score is the max over sliding 512-token windows. Success at budget *b* reads the greedy path's margin history, which also lets a single run be read at both thresholds (validated in DECISIONS.md).

## Limitations

- One monitor architecture, one fine-tuning recipe, one attack family; white-box gradient access throughout.
- Small n where it matters: R-Judge has 9 held-out attackable traces (it can't grow; a 60-trace training-split supplement is reported separately), and the public MRT release has only 5 SHADE tasks.
- Half the training pool (InjecAgent pairs, ToolEmu pseudo-traces) was constructed from benchmark specs, not collected from real agents.
- Run-to-run variance is material: two identical-seed training runs gave SHADE AUROC 0.51 vs 0.58, and operating thresholds 0.41 vs 0.87. Everything reported uses run 2, the model that was attacked.
- The naturalness and meaning labels for the constrained edits come from LLM raters; human review of the provided sample hasn't been done.
- **Data license:** ScaleAI MRT is CC BY-NC 4.0 (non-commercial) and was used for evaluation only.
