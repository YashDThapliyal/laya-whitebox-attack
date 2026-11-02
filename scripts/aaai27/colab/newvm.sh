#!/bin/bash
# newvm.sh NAME HB_LOG : allocate an A100 with the 0.7.5 CLI, then start heartbeat.py detached (its own process
# session, so stopping the caller does not kill it). The heartbeat runs a kernel command every 4 minutes and keeps the
# 0.6.0 keep-alive daemon pinging; without them Colab idle-prunes a VM 10 to 15 minutes after the last kernel command.
# Non-US VMs are released and re-requested (see below).
# Prints "NEWVM_OK NAME endpoint=... heartbeat_pid=..." on success.
set -u
: "${COLAB_WORK:?set COLAB_WORK}"
D=$(cd "$(dirname "$0")" && pwd)
NAME=$1; HB_LOG=$2
# Only US regions: on an asia-southeast1 VM the kernel websocket took 19 to 33 s to connect (US: 0 to 2 s) and the
# CLI's exec raced it and hung, so take a US VM or release it and ask again.
for TRY in 1 2 3 4 5 6; do
  "$D/tmo" 600 "$D/colab7" new -s "$NAME" --gpu A100 2>&1 | tail -3
  EP=$(python3 -c "import json; d=json.load(open('$COLAB_WORK/colab_sessions.json')); s=d.get('sessions',d).get('$NAME') or {}; print(s.get('endpoint',''))")
  [ -z "$EP" ] && { echo "NEWVM_FAIL no endpoint for $NAME"; exit 1; }
  echo "$EP" | grep -Eq -- '-ft-(kkb-)?us[a-z]+[0-9]' && break
  echo "try $TRY: $EP is not in a US region, releasing it"
  "$D/tmo" 180 "$D/colab7" stop -s "$NAME" 2>&1 | tail -1
  EP=""; sleep 20
done
[ -z "$EP" ] && { echo "NEWVM_FAIL no US A100 after 6 tries"; exit 1; }
mkdir -p "$(dirname "$HB_LOG")"
PID=$(python3 -c 'import subprocess,sys; print(subprocess.Popen(sys.argv[1:], start_new_session=True, stdin=subprocess.DEVNULL, stdout=open(sys.argv[-1] + ".out", "a"), stderr=subprocess.STDOUT).pid)' \
      python3 "$D/heartbeat.py" "$NAME" "$EP" "$HB_LOG")
echo "NEWVM_OK $NAME endpoint=$EP heartbeat_pid=$PID"
