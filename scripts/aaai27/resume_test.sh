#!/bin/bash
# Resume test for train_monitor.py, plus the attention-kernel timing that picks the setting for the seed retrains.
#   A, A2  uninterrupted runs (A vs A2 = run-to-run noise)
#   B      hard-killed at step CRASH_B, then resumed from its last checkpoint
#   C      hard-killed at step CRASH_C, then resumed
#   TF, TM short timing runs, fused vs math attention, no checkpointing (TIME_STEPS steps each)
# A, A2, B, C use --deterministic (deterministic algorithms, warn_only, plus a per-step batch-order log) and
# --attn_math. With 101 steps per epoch, STEPS=130 EVERY=20 CRASH_B=115 CRASH_C=125 makes B resume from the
# end-of-epoch-1 checkpoint (shuffle + RNG restore at an epoch boundary) and C from the mid-epoch one at step 120.
# Gate (compare_train_runs.py --gate): B and C see exactly A's batches in A's order, and their best-epoch per-source
# val AUROC and val loss are within the A vs A2 spread. Writes attn_choice.txt: "math" if math attention trains at most
# 1.5x slower per step than fused, else "fused".
# Usage: bash scripts/aaai27/resume_test.sh OUT_DIR STEPS EVERY CRASH_B CRASH_C [TIME_STEPS]
# Exits 0 only if the gate passes.
set -u
OUT=$1; STEPS=$2; EVERY=$3; CRASH_B=$4; CRASH_C=$5; TIME_STEPS=${6:-60}
export PYTHONPATH=scripts
COMMON="--epochs 2 --bs 16 --accum 1 --seed 1 --max_steps $STEPS --ckpt_steps $EVERY --ckpt_minutes 1000 --deterministic --attn_math"
run() {  # run NAME [extra args]
  local d=$OUT/$1; shift; mkdir -p $d/work
  python scripts/train_monitor.py $COMMON --out $d/model --calib_out $d/calibration.json --work_dir $d/work \
    --resume_dir $d/resume "$@"
}
timing() {  # timing NAME [extra args]: seed-like settings, no checkpoint saves inside the timed loop
  local d=$OUT/$1; shift; mkdir -p $d/work
  python scripts/train_monitor.py --epochs 1 --bs 16 --accum 1 --seed 1 --max_steps $TIME_STEPS \
    --out $d/model --calib_out $d/calibration.json --work_dir $d/work "$@"
}
rm -rf "$OUT"; mkdir -p "$OUT"
echo "== A (uninterrupted)";  run A  > $OUT/A.log 2>&1;  echo "rc=$?"
echo "== A2 (uninterrupted)"; run A2 > $OUT/A2.log 2>&1; echo "rc=$?"
for X in B C; do
  [ $X = B ] && CR=$CRASH_B || CR=$CRASH_C
  echo "== $X (crash at $CR)"; run $X --crash_at_step $CR > $OUT/${X}1.log 2>&1; echo "rc=$? (137 expected)"
  grep -E "saved state|crash_at" $OUT/${X}1.log | tail -2
  echo "== $X (resume)"; run $X > $OUT/${X}2.log 2>&1; echo "rc=$?"
  grep -E "RESUMED|Error|error" $OUT/${X}2.log | head -5
done
for X in B C A2; do
  echo "== A vs $X"
  python scripts/aaai27/compare_train_runs.py $OUT/A $OUT/$X > $OUT/cmp_A_$X.json 2> $OUT/cmp_A_$X.err
  cat $OUT/cmp_A_$X.json; tail -3 $OUT/cmp_A_$X.err
done
echo "== deterministic-kernel warnings in A.log:"; grep -i "deterministic" $OUT/A.log | sort | uniq -c | head -5
python scripts/aaai27/compare_train_runs.py --gate $OUT; GATE=$?
echo "== timing: fused";  timing TF > $OUT/TF.log 2>&1; echo "rc=$?"
echo "== timing: math";   timing TM --attn_math > $OUT/TM.log 2>&1; echo "rc=$?"
python - "$OUT" <<'EOF'
import json, sys
out = sys.argv[1]
c = {k: json.load(open(f"{out}/{k}/calibration.json")) for k in ("TF", "TM")}
sps = {k: v["train_loop_seconds"] / max(1, v["train_loop_steps"]) for k, v in c.items()}
ratio = sps["TM"] / sps["TF"]
choice = "math" if ratio <= 1.5 else "fused"
json.dump({"sec_per_step_fused": sps["TF"], "sec_per_step_math": sps["TM"], "ratio_math_over_fused": ratio,
           "rule": "math if ratio <= 1.5", "choice": choice}, open(f"{out}/timing.json", "w"), indent=1)
open(f"{out}/attn_choice.txt", "w").write(choice + "\n")
print(f"ATTN_TIMING fused {sps['TF']:.3f} s/step  math {sps['TM']:.3f} s/step  ratio {ratio:.2f}  -> {choice}")
EOF
for d in A A2 B C TF TM; do rm -rf $OUT/$d/model $OUT/$d/resume/state.pt; done  # keep logs, best.pt for inspection only
echo RESUME_TEST_DONE
exit $GATE
