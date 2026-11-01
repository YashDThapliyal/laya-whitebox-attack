"""heartbeat.py NAME ENDPOINT LOG : keep a Colab VM from being idle-pruned, for the life of the VM.

Colab pruned our VMs 11 to 13 minutes after the last kernel command when nothing pinged them; file downloads and a
busy GPU did not count as activity. So, every INTERVAL seconds:
  1. run a trivial kernel command on the VM (`colab exec`), and log the result;
  2. check that the keep-alive daemon (0.6.0 CLI, which pings /keep-alive/ every 60 s) is running and that its last
     HTTP 200 ping for this endpoint is recent; if not, (re)start it and log why.
Exits (stopping its keep-alive) once the session is gone, e.g. after `colab stop`.
Start it detached (newvm.sh does), so stopping the supervisor that allocated the VM does not kill it.
"""
from __future__ import annotations

import datetime as dt
import os
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORK = Path(os.environ["COLAB_WORK"])
C7 = str(HERE / "colab7")
PY6 = "/Users/yash/.local/share/uv/tools/google-colab-cli/bin/python"  # the 0.6.0 CLI, which has keep-alive
CLI_LOG = Path.home() / ".config" / "colab-cli" / "colab.log"
INTERVAL = 240  # seconds between kernel commands (requirement: at most 5 minutes)
PING_STALE = 180  # keep-alive pings every 60 s; no 200 for this long means it is not working
GONE_RE = re.compile(r"session '[^']*' not found|no active sessions", re.IGNORECASE)


def ts() -> str:
    return time.strftime("%H:%M:%S")


def run(cmd: list[str], timeout: int) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        return p.returncode, p.stdout + p.stderr
    except subprocess.TimeoutExpired:
        return 124, "timeout"


def last_ping_age(endpoint: str) -> float | None:
    """Seconds since the last HTTP 200 keep-alive ping for endpoint in the CLI debug log (its last 4 MB)."""
    if not CLI_LOG.exists():
        return None
    with CLI_LOG.open("rb") as fh:
        fh.seek(max(0, CLI_LOG.stat().st_size - (4 << 20)))
        text = fh.read().decode("utf-8", errors="replace")
    pat = re.compile(r"^(\S+ \S+),\d+ .*/tun/m/" + re.escape(endpoint) + r"/keep-alive/\S* HTTP/1\.1\" 200", re.MULTILINE)
    hits = pat.findall(text)
    if not hits:
        return None
    last = dt.datetime.strptime(hits[-1], "%Y-%m-%d %H:%M:%S")
    return (dt.datetime.now() - last).total_seconds()


class Heartbeat:
    def __init__(self, name: str, endpoint: str, log: Path) -> None:
        self.name, self.endpoint, self.log_path = name, endpoint, log
        self.ka: subprocess.Popen | None = None
        self.ka_started = 0.0
        self.code = WORK / f"hb_{name}.py"
        self.code.write_text("import time\nprint('HB_OK', time.time())\n")

    def log(self, msg: str) -> None:
        with self.log_path.open("a") as fh:
            fh.write(f"{ts()} {msg}\n")

    def start_keepalive(self, why: str) -> None:
        if self.ka and self.ka.poll() is None:
            self.ka.terminate()
        out = (WORK / f"keepalive_{self.name}.log").open("a")
        self.ka = subprocess.Popen([PY6, "-m", "colab_cli.cli", "--config", str(WORK / "colab_sessions.json"),
                                    "keep-alive", self.endpoint, self.name], stdout=out, stderr=subprocess.STDOUT)
        self.ka_started = time.time()
        self.log(f"KEEPALIVE started pid={self.ka.pid} ({why})")

    def check_keepalive(self) -> str:
        age = last_ping_age(self.endpoint)
        if self.ka is None or self.ka.poll() is not None:
            self.start_keepalive(f"daemon not running, exit={None if self.ka is None else self.ka.returncode}")
        elif time.time() - self.ka_started > PING_STALE and (age is None or age > PING_STALE):
            self.start_keepalive(f"no 200 ping for {'ever' if age is None else int(age)}s")
        return f"keepalive pid={self.ka.pid} last_ping={'none' if age is None else f'{int(age)}s ago'}"

    def gone(self) -> bool:
        _, out = run([C7, "status", "-s", self.name], 120)
        return bool(GONE_RE.search(out))

    def beat(self) -> bool:
        """One heartbeat; returns False once the session is gone."""
        t0 = time.time()
        rc, out = run([C7, "exec", "-s", self.name, "-f", str(self.code)], 150)
        ok = "HB_OK" in out
        if not ok and (GONE_RE.search(out) or self.gone()):
            self.log("session gone, heartbeat exiting")
            return False
        detail = "ok" if ok else f"FAILED rc={rc} {out.strip()[-120:]!r} (kernel busy or transient; VM still up)"
        self.log(f"HB {detail} {time.time() - t0:.1f}s | {self.check_keepalive()}")
        return True

    def run(self) -> None:
        self.log(f"heartbeat start name={self.name} endpoint={self.endpoint} interval={INTERVAL}s pid={os.getpid()}")
        self.start_keepalive("initial")
        try:
            t0 = time.time()
            while self.beat():  # fixed cadence: a slow exec does not stretch the gap past INTERVAL
                t0 += INTERVAL
                time.sleep(max(5.0, t0 - time.time()))
        finally:
            if self.ka and self.ka.poll() is None:
                self.ka.terminate()
            self.log("heartbeat end")


if __name__ == "__main__":
    Heartbeat(sys.argv[1], sys.argv[2], Path(sys.argv[3])).run()
