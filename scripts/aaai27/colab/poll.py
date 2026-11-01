"""poll.py: watch a background job on a Colab VM, pulling its outputs locally, and exit on any failure.

Exit codes (always preceded by one line "POLL_EXIT <code> <REASON> <detail>"):
  0 FINISHED        the remote log contains JOB_EXIT=0
  1 JOB_FAILED      the remote log contains JOB_EXIT=<nonzero>   (the job itself errored)
  2 SESSION_GONE    the session/VM is gone or unreachable          (infrastructure: relaunch, not a job failure)
  3 LOW_BALANCE     compute-unit balance below the top-up floor (15)
  5 CU_CAP          this task's own VM usage (task_usage.py) reached --task_cap units
  4 STALLED         the log's last line has not changed for --stall seconds while the VM is up

Downloads are atomic and never shrink a local file: each file is fetched to <name>.part, and for .jsonl only
complete lines are kept; the local copy is replaced only if the new one has at least as many complete lines.
So a failed or partial download can never truncate a local checkpoint that a resume depends on.

Usage: poll.py --name laya6c --rdir /content/proj --log job6.log --ldir DIR [--interval 90] [--stall 300]
               [--task_cap UNITS] [--colab PATH] FILE [FILE ...]     (FILE and --log are paths relative to --rdir,
               mirrored under --ldir)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

S = Path(__file__).resolve().parent
sys.path.insert(0, str(S))
from task_usage import task_units

BALANCE_FLOOR = 15.0
GONE_RE = re.compile(r"session '[^']*' not found|no active sessions", re.IGNORECASE)  # the CLI's own wording only;
# a missing remote *file* also says "not found"/404 and must not count as a dead session


def run(cmd: list[str], timeout: int) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        return p.returncode, (p.stdout + p.stderr)
    except subprocess.TimeoutExpired:
        return 124, "timeout"


def complete_lines(path: Path) -> list[str]:
    data = path.read_bytes().decode("utf-8", errors="replace")
    lines = data.split("\n")[:-1]  # drop the trailing piece after the last newline (partial or empty)
    good = []
    for line in lines:
        try:
            json.loads(line)
        except json.JSONDecodeError:
            break
        good.append(line)
    return good


def fetch(colab: str, name: str, remote: str, local: Path) -> str:
    part = local.with_name(local.name + ".part")
    part.unlink(missing_ok=True)
    rc, out = run([colab, "download", "-s", name, remote, str(part)], 600)
    if rc != 0 or not part.exists():
        part.unlink(missing_ok=True)
        return "gone" if GONE_RE.search(out) else "fail"
    if local.suffix == ".jsonl":
        new = complete_lines(part)
        old = complete_lines(local) if local.exists() else []
        if len(new) < len(old):
            part.unlink()
            return "ok"  # never shrink a local checkpoint
        part.write_text("".join(line + "\n" for line in new))
    os.replace(part, local)
    return "ok"


def session_state(colab: str, name: str) -> str:
    rc, out = run([colab, "status", "-s", name], 120)
    if GONE_RE.search(out):
        return "gone"  # `colab status` exits 0 even when the session is gone, so read the text
    return "up" if rc == 0 else "unknown"


def balance(colab: str) -> float | None:
    _, out = run([colab, "usage"], 120)
    m = re.search(r"balance:\s*([0-9.]+)", out)
    return float(m.group(1)) if m else None


def finish(code: int, reason: str, detail: str = "") -> None:
    print(f"{time.strftime('%H:%M:%S')} POLL_EXIT {code} {reason} {detail}".rstrip(), flush=True)
    sys.exit(code)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--rdir", required=True)
    ap.add_argument("--log", required=True)
    ap.add_argument("--ldir", required=True)
    ap.add_argument("--interval", type=int, default=90)
    ap.add_argument("--stall", type=int, default=300)
    ap.add_argument("--max_unreachable", type=int, default=3, help="consecutive rounds with every download failing")
    ap.add_argument("--colab", default=str(S / "colab7"))
    ap.add_argument("--task_cap", type=float, default=60.0, help="exit 5 when this task's VMs have used this many units")
    ap.add_argument("files", nargs="*")
    a = ap.parse_args()
    ldir = Path(a.ldir)
    ldir.mkdir(parents=True, exist_ok=True)
    log_local = ldir / a.log
    last_line, last_change, unreachable = None, time.time(), 0
    while True:
        state = session_state(a.colab, a.name)
        if state == "gone":
            finish(2, "SESSION_GONE", f"session {a.name} no longer exists")
        for f in [*a.files, a.log]:
            (ldir / f).parent.mkdir(parents=True, exist_ok=True)
        results = [fetch(a.colab, a.name, f"{a.rdir}/{f}", ldir / f) for f in [*a.files, a.log]]
        if "gone" in results:
            finish(2, "SESSION_GONE", f"download reports the session is gone ({a.name})")
        unreachable = unreachable + 1 if all(r != "ok" for r in results) else 0
        if unreachable >= a.max_unreachable:
            finish(2, "SESSION_GONE", f"VM unreachable for {unreachable} rounds ({a.name})")
        text = log_local.read_text(errors="replace") if log_local.exists() else ""
        tail = text.strip().splitlines()[-1][:160] if text.strip() else ""
        bal = balance(a.colab)
        print(f"{time.strftime('%H:%M:%S')} bal={bal if bal is not None else '?'} task={task_units():.2f} {tail}", flush=True)
        m = re.search(r"JOB_EXIT=(\d+)", text)
        if m:  # the job has exited: fetch outputs once more, since they may have been fetched before it finished
            for f in a.files:
                fetch(a.colab, a.name, f"{a.rdir}/{f}", ldir / f)
            finish(0, "FINISHED") if m.group(1) == "0" else finish(1, "JOB_FAILED", f"JOB_EXIT={m.group(1)}")
        if bal is not None and bal < BALANCE_FLOOR:
            finish(3, "LOW_BALANCE", f"{bal}")
        used = task_units()
        if used >= a.task_cap:
            finish(5, "CU_CAP", f"task VMs used {used:.2f} >= cap {a.task_cap}")
        if tail != last_line:
            last_line, last_change = tail, time.time()
        elif time.time() - last_change > a.stall:
            finish(4, "STALLED", f"no new log line for {int(time.time() - last_change)}s: {tail[:80]}")
        time.sleep(a.interval)


if __name__ == "__main__":
    main()
