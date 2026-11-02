"""Run a CLI command with a timeout that kills its whole process tree.

`uvx ... colab` runs the CLI as a grandchild; subprocess.run(timeout=...) kills only the uvx child, so a hung CLI
call (seen when the kernel websocket is slow to connect and the client stops before it is ready) is left running
forever. Starting the command in its own process group and killing the group avoids those orphans.

Lease: every call that names a session (-s NAME) touches $COLAB_WORK/lease_NAME, so the file's age says how long it
has been since a supervisor or poller last talked to that VM. heartbeat.py (which calls with lease=False) stops a VM
whose lease is older than its limit, so a killed supervisor cannot leave a VM running unattended.
"""
from __future__ import annotations

import os
import signal
import subprocess
from pathlib import Path


def lease_path(name: str) -> Path:
    return Path(os.environ["COLAB_WORK"]) / f"lease_{name}"


def touch_lease(cmd: list[str]) -> None:
    if "-s" in cmd and cmd.index("-s") + 1 < len(cmd):
        lease_path(cmd[cmd.index("-s") + 1]).touch()


def run_cli(cmd: list[str], timeout: int, lease: bool = True) -> tuple[int, str]:
    """Return (returncode, stdout+stderr); (124, "timeout") if it did not finish in time."""
    if lease:
        touch_lease(cmd)
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                         text=True, start_new_session=True)
    try:
        out, _ = p.communicate(timeout=timeout)
        return p.returncode, out
    except subprocess.TimeoutExpired:
        try:
            os.killpg(p.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        p.communicate()
        return 124, "timeout"
