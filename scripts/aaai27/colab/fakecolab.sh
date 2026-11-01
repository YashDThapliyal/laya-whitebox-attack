#!/bin/bash
# fake colab CLI for testing poll.py. FAKE_MODE: alive (static log, never progresses) | dead
case "$1" in
  status) [ "$FAKE_MODE" = dead ] && echo "[colab] Session 'x' not found." || echo "IDLE"; exit 0;;
  usage) echo "Current balance: 100.00 compute units"; exit 0;;
  download) [ "$FAKE_MODE" = dead ] && { echo "[colab] Session 'x' not found."; exit 1; }; [ "$FAKE_MODE" = nofile ] && { echo "Error: 404 file not found"; exit 1; }
            case "$5" in *.jsonl.part) printf '{"key":"a"}\n{"key":"b"}\n{"key":' > "$5";; *) echo "1/10 texts" > "$5";; esac; exit 0;;
esac
