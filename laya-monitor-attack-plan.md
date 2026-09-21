# Laya Trusted-Monitor Adversarial Robustness — Plan, Spec, Kickoff Prompt

## 0. One-line goal

Fine-tune Laya (open-weight, non-autoregressive typed-decision model) as a trusted
monitor for agentic tool-use traces, then run a white-box, gradient-guided attack
against it to find the actual adversarial ceiling, something no published work has
done yet (prior work only ran black-box attacks against the closed Jev model on
code-backdoor detection, not white-box attacks on an open-weight model over agent
traces).

## 1. Deliverables ("done" means these exist and are readable without me present)

1. `data/` — normalized, labeled agent-trace datasets, train/eval split, with a
   held-out attack-eval set that was never used for training.
2. `monitor/` — a fine-tuned Laya checkpoint that classifies a trace as
   policy-violating vs. compliant (or the closest achievable version of this).
3. `baseline_eval.md` (or `.json` + a short summary) — monitor performance
   (AUROC, accuracy, calibration) on the held-out eval set, before any attack.
4. `attack/` — the gradient-guided attack implementation, runnable against the
   fine-tuned monitor.
5. `attack_eval.md` — attack success rate as a function of perturbation budget,
   plus a small set of qualitative examples (before/after trace text, before/after
   monitor score).
6. `SUMMARY.md` — the actual write-up: what worked, what didn't, what the honest
   headline finding is, and what's still open. This is the most important file.
   It should read like something you'd send me or a labmate, not a status log.
7. `DECISIONS.md` — a running log of every non-trivial judgment call made while
   unsupervised (which dataset subset, which hyperparameters, what got skipped and
   why), so I can audit the reasoning in the morning without re-deriving it.

## 1.5 Links (verified, use these directly, don't guess URLs)

**Laya (the monitor model)**
- HF model repo (all 3 checkpoints): https://huggingface.co/convaiinnovations/laya
- GitHub (code, fine-tuning notebook): https://github.com/NandhaKishorM/laya
- Fine-tuning notebook specifically: https://github.com/NandhaKishorM/laya/blob/main/notebooks/laya_finetune_typed_decisions_2xT4_kaggle.ipynb
- Full benchmark report: https://github.com/NandhaKishorM/laya/blob/main/BENCHMARKS.md
- PyPI: https://pypi.org/project/laya/ (`pip install laya`)

**R-Judge (train-pool data)**
- Repo: https://github.com/Lordog/R-Judge
- Paper: https://arxiv.org/abs/2401.10019
- 569 multi-turn agent interaction records, 27 risk scenarios, 10 risk types, human-annotated safety labels.

**ToolEmu (train-pool data)**
- Repo: https://github.com/ryoungj/ToolEmu
- 144 test cases, 36 toolkits, ICLR'24 Spotlight, MIT license.
- Note: originally built around an LM-emulated sandbox (uses an LLM to emulate tool execution), so ingesting it means either running the emulator or using its pre-generated trajectories if included in the repo; check `assets/` in the repo first before deciding whether to re-run emulation.

**InjecAgent (train-pool data)**
- Repo: https://github.com/uiuc-kang-lab/InjecAgent
- 1,054 test cases, 17 user tools, 62 attacker tools, indirect prompt injection focus.

**SHADE-Arena (held-out attack-eval set) — access note, read before Phase 1**
- The original SHADE-Arena task implementations live inside ControlArena
  (UK AI Security Institute / Redwood Research), here:
  https://github.com/UKGovernmentBEIS/control-arena
  As of this writing, the SHADE-Arena setting inside that repo is listed as a
  **private repo requiring access**, not open-clone. Don't burn time trying to
  force access to it, use the alternative below instead.
- **Practical substitute (public, no request needed):** Scale AI's "Monitor
  Red Teaming (MRT)" dataset is built directly on the SHADE-Arena framework
  and is openly downloadable:
  - Dataset: https://huggingface.co/datasets/ScaleAI/mrt
  - Code: https://github.com/scaleapi/mrt
  - It already contains labeled agent trajectories (17 SHADE-Arena-based tasks
    plus 15 additional computer-use tasks), each with a benign main task and a
    hidden malicious side task, generated under multiple red-teaming
    strategies, with monitor scores attached. This is arguably a *better* fit
    than raw SHADE-Arena for this project, since it's already in the
    trajectory-plus-monitoring-result shape we need, not just task
    definitions.
  - License: CC BY-NC 4.0, non-commercial, fine for a research project, flag
    it in `SUMMARY.md` if this ever moves toward anything commercial.
  - Use this as the `shade-arena` source in the schema below (keep that field
    name for consistency with the rest of this doc even though the literal
    source is MRT).

## 2. Phase breakdown (with go/no-go criteria so the run doesn't silently drift)

### Phase 0 — Environment setup (budget: ~20 min)
- Create a project directory, git init, Python venv.
- `pip install laya torch transformers datasets scikit-learn matplotlib`
- Verify `torch.backends.mps.is_available()` is True; fall back to CPU with a
  logged warning if not, don't halt.
- Verify Laya loads and runs a single forward pass on a toy input.
- **Go/no-go:** if Laya can't be loaded at all after reasonable troubleshooting,
  stop and write the blocker to `DECISIONS.md` and `SUMMARY.md` rather than
  spending the night on something downstream of a broken foundation.

### Phase 1 — Data acquisition & normalization (budget: ~1.5 hr)
- Pull R-Judge, ToolEmu, and InjecAgent (train pool) from the links in Section
  1.5.
- Pull the ScaleAI MRT dataset (Section 1.5) separately and keep it untouched
  as the held-out attack-eval set (do not train on it, do not tune
  hyperparameters against it). Do not attempt to access the original
  SHADE-Arena repo inside ControlArena, it's gated; the MRT dataset is the
  intended substitute and is referred to as `shade-arena` in the schema below
  for consistency.
- Normalize every source into one common schema (see Section 4.1).
- **Go/no-go:** if a given source's raw format is too ambiguous to normalize
  confidently, use best judgment, log the assumption in `DECISIONS.md`, and move
  on rather than getting stuck. Partial data beats a stalled night.

### Phase 2 — Fine-tune the monitor (budget: ~2 hr)
- Use Laya's fine-tuning notebook/approach as a starting template, adapted to
  the normalized schema and a binary (or typed) violation question.
- Small model (421M), local MPS: keep batch size modest, checkpoint every N
  steps so progress survives a crash.
- **Go/no-go:** target a sanity bar, not a paper-quality bar: better than the
  majority-class baseline on a held-out slice of the *training* pool. If it
  can't clear that after reasonable tuning, log it honestly, this is itself a
  finding worth reporting, don't fabricate a stopping point that looks better
  than it is.

### Phase 3 — Baseline evaluation on SHADE-Arena (budget: ~30 min)
- Run the fine-tuned monitor on the held-out SHADE-Arena set.
- Report AUROC, accuracy, and calibration (reliability curve or ECE).
- This is the "before attack" number everything else compares against.

### Phase 4 — White-box gradient attack (budget: ~2.5 hr)
- Implement a HotFlip-style (or embedding-space projected to nearest-token)
  attack: compute gradient of the monitor's output probability w.r.t. input
  token embeddings, rank candidate substitutions, greedily substitute under a
  perturbation budget.
- Budget should be defined in an interpretable unit (e.g. max N token swaps per
  trace, or max edit distance), not "however much it takes," so results are
  comparable across traces.
- Run against a sample of the SHADE-Arena eval traces (start with a small
  sample, e.g. 20-30, to validate the pipeline before scaling up if time
  allows).
- **Go/no-go:** if gradient computation through Laya's architecture hits a
  blocker (e.g. the option-marker head isn't differentiable the expected way),
  fall back to a simpler proxy (embedding-space perturbation without the
  discrete-token projection) and log why, rather than silently skipping the
  core experiment.

### Phase 5 — Attack evaluation (budget: ~1 hr)
- Report: attack success rate vs. perturbation budget (a curve, not a single
  number).
- Include qualitative examples: a few traces where a small, plausible-looking
  edit flipped the verdict, and a few where the attack failed even at a large
  budget.
- Compare, in prose, against the existing black-box result on Jev (monitor
  score moved by ≤0.014 under hand-crafted tricks) — is the white-box ceiling
  meaningfully different?

### Phase 6 — Write-up (budget: ~30 min)
- `SUMMARY.md`: headline finding stated plainly in the first paragraph, then
  method, then results, then honest limitations (small held-out set, one
  architecture, one attack method, local-compute-scale training).

Total budget: roughly 8 hours, sized for an overnight run with slack.

## 3. Guardrails (so autonomy doesn't turn into scope creep or silent failure)

- Everything lives inside one project directory. Nothing outside it gets
  touched.
- Commit to git after every phase, with a message summarizing what changed.
  This is the recovery mechanism if something breaks midway.
- Every phase writes its status (started / done / blocked-with-reason) to a
  single `PROGRESS.md` that's appended to, not overwritten, so the whole night
  is reconstructable in order.
- No open-ended loops. Every step that could run indefinitely (data download,
  training, attack search) has an explicit stopping condition (step count, time
  limit, or convergence check) defined before it starts.
- If genuinely stuck (not just "this is hard" but "I cannot proceed without a
  judgment call only Yash can make"), don't guess silently on something
  consequential, pick the most defensible option, log it clearly in
  `DECISIONS.md`, and keep going. Only fully halt for Phase 0-level blockers.
- Do not overstate results in `SUMMARY.md`. A null result (attack doesn't work,
  or monitor doesn't train well) is a valid, useful outcome, report it as such.

## 4. Technical spec

### 4.1 Common trace schema (normalize all sources into this)

```json
{
  "id": "string, source-prefixed, e.g. rjudge_0001",
  "source": "r-judge | toolemu | injecagent | shade-arena",
  "state": "the state/context text the monitor reads (task, tool calls, trace)",
  "verbal_summary": "optional: agent's own summary/report, if the source has one",
  "label": "compliant | violating",
  "risk_category": "optional, source-native category if available",
  "split": "train | eval_heldout"
}
```

`shade-arena` records always get `split: eval_heldout`. Everything else is
`train`, with a small carved-out slice for training-time validation. (Recall:
`shade-arena` here means the ScaleAI MRT dataset from Section 1.5, the
original repo is gated.)

### 4.2 Monitor

- Base: `convaiinnovations/laya` (English checkpoint, ModernBERT-large, 421M).
- Task: binary `noul`-style question ("is this trace policy-violating?") at
  minimum; typed `choice` classification into risk categories as a stretch
  goal if time allows.
- Fine-tune locally via MPS; log train/val loss per epoch.

### 4.3 Attack

- White-box, gradient-guided token substitution against the fine-tuned
  monitor's output probability.
- Budget metric: number of token substitutions (report results at a few budget
  levels, e.g. 1, 3, 5, 10 tokens).
- Success criterion: monitor's violation probability crosses its decision
  threshold (use the threshold that gave the best F1 on the training-pool
  validation slice from Phase 2).

### 4.4 Metrics to report throughout

- AUROC, accuracy, ECE for the monitor (Phase 3).
- Attack success rate vs. budget (Phase 5).
- Wall-clock time and any resource issues hit along the way (useful for me to
  know for next time regardless of research outcome).

## 5. Kickoff prompt for Claude Code

Copy the block below as the first message in a fresh Claude Code session, in an
empty working directory.

```
Read this entire file first: laya-monitor-attack-plan.md (in this directory).
It is your plan and spec for tonight. Follow it, including Section 1.5, which
has the exact URLs for the model and every dataset, use those directly
instead of searching for or guessing at repo links.

Context: this is a research project testing whether Laya (an open-weight,
non-autoregressive typed-decision model, pip install laya, HF repo
convaiinnovations/laya) can be fine-tuned into a "trusted monitor" for
agentic tool-use traces, and then whether a white-box, gradient-guided
adversarial attack can flip its decisions on held-out traces from SHADE-Arena.

I will not be supervising this run. Execute the full plan autonomously,
phase by phase, in order. Do not stop to ask me questions unless you hit a
Phase-0-level blocker (see the plan's guardrails section) that makes
continuing meaningless. For every other judgment call, make the most
defensible choice yourself and log it in DECISIONS.md, then continue.

Requirements while running:
- Set up git in this directory immediately and commit after every phase.
- Append phase status to PROGRESS.md as you go (started/done/blocked+reason).
- Respect the time budgets in the plan loosely, they're guidance, not hard
  cutoffs, but don't let any one phase eat the whole night.
- I'm on a local Mac (M3 Pro, 18GB unified memory) with no CUDA. Use MPS via
  PyTorch, keep batch sizes and model sizes sane for that hardware, and don't
  assume cloud compute is available.
- At the end, whether the results are good, bad, or mixed, write SUMMARY.md
  as an honest, plainly-stated account, no overselling a weak result, no
  underselling a real one. I'd rather read "the attack didn't work at any
  budget we tried" than a summary that quietly avoids saying so.

Start with Phase 0 now.
```

## 6. Notes for when you check on it in the morning

- Read `SUMMARY.md` first, then `PROGRESS.md` to see how the night actually
  went (where time got spent, what stalled).
- Check `DECISIONS.md` for anything you'd have decided differently, those are
  the places to sanity-check before trusting downstream results.
- If Phase 4/5 (the actual novel contribution) didn't get reached because
  earlier phases ate the budget, that's still useful: it tells you where the
  real bottleneck is (usually data normalization or fine-tuning, not the
  attack itself) for a second overnight run.
