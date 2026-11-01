#!/bin/bash
# Job 8: two more training seeds (run-2 config) + in-distribution attacks at 20 swaps, per seed.
# SMOKE=1: tiny end-to-end run (1 epoch / 10 steps, 3 targets, 3 swaps) into smoke/ dirs.
set -u
cd /content/proj; export PYTHONPATH=scripts
SMOKE=${SMOKE:-0}
if [ "$SMOKE" = 1 ]; then TR="--epochs 1 --max_steps 10"; AT="--n 3 --budget 3"; P=smoke_; SEEDS="1"; else TR="--epochs 3"; AT="--n 200 --budget 20"; P=; SEEDS="1 2"; fi
step() { echo "[$(date +%H:%M:%S)] START $*"; "$@"; rc=$?; echo "[$(date +%H:%M:%S)] END rc=$rc $1 ${*: -1}"; return $rc; }

for s in $SEEDS; do
  M=monitor/${P}seed$s; W=runs/${P}seed$s; mkdir -p $W
  if [ -f $M/calibration.json ]; then echo "seed $s already trained"; continue; fi
  step python scripts/train_monitor.py $TR --bs 16 --accum 1 --max_minutes 60 --seed $s --out $M --calib_out $M/calibration.json --work_dir $W > $W/train.log 2>&1 \
    || { echo "TRAIN_FAILED seed $s"; tail -20 $W/train.log; }
done

chain() {
  s=$1; M=monitor/${P}seed$s; C=$M/calibration.json; O=out/${P}seed$s; mkdir -p $O/attack
  [ -f $C ] || { echo "no calibration for seed $s, skipping chain"; return 1; }
  BAR=$(python -c "import json;print(min(0.5, json.load(open('$C'))['threshold']))")
  echo "seed $s threshold $(python -c "import json;print(json.load(open('$C'))['threshold'])") run-to bar $BAR"
  cp $C $O/calibration.json; cp runs/${P}seed$s/train_log.jsonl $O/ 2>/dev/null
  L="--limit 5"; [ "$SMOKE" = 1 ] || L=""
  step python scripts/aaai27/score_texts.py --model $M --texts inputs/val_texts.jsonl --out $O/val_scores.jsonl $L > $O/val_scores.log 2>&1
  if [ "$SMOKE" = 0 ]; then step python scripts/eval_monitor.py --model $M --calib $C --tag seed$s --out $O > $O/eval_shade.log 2>&1; fi
  V="--model $M --calib $C --data data/train_pool.jsonl --scores compute $AT --threshold $BAR --resume"
  step python scripts/attack.py $V --scope agent --max_minutes 70 --out $O/attack/val_agent.jsonl > $O/attack/val_agent.log 2>&1
  step python scripts/attack.py $V --scope agent --fluent_k 20 --max_minutes 70 --out $O/attack/f_val_agent.jsonl > $O/attack/f_val_agent.log 2>&1
  step python scripts/attack.py $V --scope all --max_minutes 50 --out $O/attack/val_all.jsonl > $O/attack/val_all.log 2>&1
  echo "chain seed $s finished"
}
for s in $SEEDS; do chain $s > out/${P}chain$s.log 2>&1 & done
wait
cat out/${P}chain*.log
tar czf out/${P}results.tgz out/${P}seed* 2>/dev/null; echo "packed out/${P}results.tgz"
