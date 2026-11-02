"""Compute units used by this task's own VMs, from the Colab CLI's per-session history.

The cap for the AAAI-27 Phase B work is counted by this task's VMs only (not the account balance, which other
sessions also draw on). A VM counts if its session name matches TASK_VM_RE. Its time runs from session_created to
session_terminated, or to now if it is still up. Every task VM is an A100 (Standard shape), billed at A100_RATE.

Usage: python task_usage.py            prints one line per VM and the total
"""
from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path

HISTORY = Path.home() / ".config" / "colab-cli" / "history"
TASK_VM_RE = re.compile(r"^laya(6|6b|6c|7\d+|8\d+|hb\d+)$")  # job 6 (3 VMs), job 7 laya7N, job 8 laya8N, heartbeat test
A100_RATE = 6.73  # units per hour for one A100, as reported by `colab usage` with a single assignment


def vm_minutes(path: Path, now: dt.datetime) -> tuple[float, bool]:
    events = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    total, start = 0.0, None  # a name can be reused (newvm.sh releases non-US VMs), so sum each up-interval
    for e in events:
        if e["event_type"] == "session_created" and start is None:
            start = dt.datetime.fromisoformat(e["timestamp"])
        elif e["event_type"] == "session_terminated" and start is not None:
            total += (dt.datetime.fromisoformat(e["timestamp"]) - start).total_seconds() / 60
            start = None
    if start is not None:
        total += (now - start).total_seconds() / 60
    return total, start is not None


def task_vms() -> list[tuple[str, float, bool]]:
    now = dt.datetime.now(dt.UTC)
    rows = []
    for p in sorted(HISTORY.glob("*.jsonl")):
        if TASK_VM_RE.match(p.stem):
            minutes, live = vm_minutes(p, now)
            rows.append((p.stem, minutes, live))
    return rows


def task_units() -> float:
    return sum(m for _, m, _ in task_vms()) / 60 * A100_RATE


def main() -> None:
    for name, minutes, live in task_vms():
        print(f"{name:10s} {minutes:7.1f} min {minutes / 60 * A100_RATE:6.2f} units{'  (live)' if live else ''}")
    print(f"total {task_units():.2f} units")


if __name__ == "__main__":
    main()
