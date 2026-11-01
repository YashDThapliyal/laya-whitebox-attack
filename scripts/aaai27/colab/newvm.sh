#!/bin/bash
# newvm.sh NAME HB_LOG : allocate an A100 with the 0.7.5 CLI, then start heartbeat.py detached (its own process
# session, so stopping the caller does not kill it). The heartbeat runs a kernel command every 4 minutes and keeps the
# 0.6.0 keep-alive daemon pinging; without them Colab idle-prunes a VM 10 to 15 minutes after the last kernel command.
# Prints "NEWVM_OK NAME endpoint=... heartbeat_pid=..." on success.
set -u
: "${COLAB_WORK:?set COLAB_WORK}"
D=$(cd "$(dirname "$0")" && pwd)
NAME=$1; HB_LOG=$2
"$D/tmo" 600 "$D/colab7" new -s "$NAME" --gpu A100 2>&1 | tail -3
EP=$(python3 -c "import json; d=json.load(open('$COLAB_WORK/colab_sessions.json')); s=d.get('sessions',d).get('$NAME') or {}; print(s.get('endpoint',''))")
[ -z "$EP" ] && { echo "NEWVM_FAIL no endpoint for $NAME"; exit 1; }
mkdir -p "$(dirname "$HB_LOG")"
PID=$(python3 -c 'import subprocess,sys; print(subprocess.Popen(sys.argv[1:], start_new_session=True, stdin=subprocess.DEVNULL, stdout=open(sys.argv[-1] + ".out", "a"), stderr=subprocess.STDOUT).pid)' \
      python3 "$D/heartbeat.py" "$NAME" "$EP" "$HB_LOG")
echo "NEWVM_OK $NAME endpoint=$EP heartbeat_pid=$PID"
