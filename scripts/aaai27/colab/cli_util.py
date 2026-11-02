"""Run a CLI command with a timeout that kills its whole process tree.

`uvx ... colab` runs the CLI as a grandchild; subprocess.run(timeout=...) kills only the uvx child, so a hung CLI
call (seen when the kernel websocket is slow to connect and the client stops before it is ready) is left running
forever. Starting the command in its own process group and killing the group avoids those orphans.
"""
from __future__ import annotations

import os
import signal
import subprocess


def run_cli(cmd: list[str], timeout: int) -> tuple[int, str]:
    """Return (returncode, stdout+stderr); (124, "timeout") if it did not finish in time."""
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
