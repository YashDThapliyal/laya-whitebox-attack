#!/bin/bash
# heartbeat_test.sh NAME MINUTES LOG : bring up an A100 with only the heartbeat running (no job, no polling), kill the
# keep-alive daemon after 6 minutes to check that the heartbeat restarts it, and after MINUTES check that Colab has not
# pruned the VM. Then stop the VM and check that the heartbeat notices and exits. Prints HEARTBEAT_TEST PASS or FAIL.
set -u
: "${COLAB_WORK:?set COLAB_WORK}"
D=$(cd "$(dirname "$0")" && pwd)
NAME=$1; MINUTES=$2; LOG=$3
HIST=~/.config/colab-cli/history/$NAME.jsonl
T0=$(date +%s)
echo "$(date +%T) creating $NAME"
"$D/newvm.sh" "$NAME" "$LOG" | tail -1
sleep 360
KA=$(grep -o 'KEEPALIVE started pid=[0-9]*' "$LOG" | tail -1 | cut -d= -f2)
echo "$(date +%T) killing keep-alive pid=$KA to test the restart"; kill "$KA"
sleep $(( MINUTES * 60 - ($(date +%s) - T0) ))
STATUS=$("$D/colab7" status -s "$NAME" 2>&1 | tail -2)
echo "$(date +%T) after $(( ($(date +%s) - T0) / 60 )) min: $STATUS"
PRUNED=$(grep -c '"reason": "pruned"' "$HIST")  # releases of non-US VMs are user_requested, not prunes
RESTARTS=$(grep -c 'KEEPALIVE started' "$LOG")
BEATS=$(grep -c 'HB ok' "$LOG")
MAXGAP=$(grep 'HB ' "$LOG" | awk '{split($1,t,":"); s=t[1]*3600+t[2]*60+t[3]; if (p) {g=s-p; if (g>m) m=g}; p=s} END {print m+0}')
echo "beats_ok=$BEATS max_gap_s=$MAXGAP keepalive_starts=$RESTARTS pruned_events=$PRUNED"
FAILED=$(grep -c 'HB FAILED' "$LOG")
echo "beats_failed=$FAILED (pass needs 0 failed and at least $(( MINUTES * 60 / 240 - 1 )) ok)"
if [ "$PRUNED" = 0 ] && ! echo "$STATUS" | grep -qi "not found" && [ "$RESTARTS" -ge 2 ] && [ "$MAXGAP" -le 300 ] \
   && [ "$FAILED" = 0 ] && [ "$BEATS" -ge $(( MINUTES * 60 / 240 - 1 )) ]; then
  RESULT=PASS; else RESULT=FAIL; fi
"$D/colab7" stop -s "$NAME" 2>&1 | tail -1
for _ in $(seq 1 40); do grep -q "heartbeat end" "$LOG" && break; sleep 15; done
grep -q "heartbeat end" "$LOG" && echo "heartbeat exited after stop: yes" || { echo "heartbeat exited after stop: NO"; RESULT=FAIL; }
tail -3 "$LOG"
echo "HEARTBEAT_TEST $RESULT"
