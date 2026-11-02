"""sup.py SPEC.json : run a job's remote steps on a Colab A100, one step at a time, surviving VM reclaims.

For each step not yet done (state in <ldir>/sup_state.json):
  ensure a live VM (allocate + keep-alive daemon + setup + restore outputs of finished steps when it is new),
  upload the step's partial outputs (so --resume continues), launch it in the background, poll it (poll.py),
  then on FINISHED download its big outputs (chunked, sha-verified) before the next step starts.
Poll outcomes: SESSION_GONE = reclaim -> new VM and relaunch, not counted as a failure; JOB_FAILED or STALLED ->
failure (stalled processes are killed first); a step that fails twice is skipped. CU_CAP (this task's own VM usage,
task_usage.py, reached spec "task_cap") -> stop the VM and exit 5. LOW_BALANCE (account balance < 15) -> exit 3
leaving the VM up (top-up needed). A connection error on a VM that is still up is a failure, not a reclaim, and more
than MAX_RECLAIMS reclaims in one run stops the job (exit 6). The VM is stopped when the job ends or exits early.
Every VM gets heartbeat.py (newvm.sh), logged to <ldir>/heartbeat/<vm>.log.

Paths: code lives next to this file; sessions, staging, transfer chunks and step scripts live in $COLAB_WORK.
Spec strings may use {work} and {repo}, expanded at load time.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
S = Path(os.environ["COLAB_WORK"])  # working dir: session file, staging, chunks, step scripts
C7 = str(HERE / "colab7")
sys.path.insert(0, str(HERE))
from cli_util import run_cli

CHUNK = "50m"
MAX_RECLAIMS = 8  # per supervisor run; beyond this something is wrong, stop and report
MAX_FAILS = 2
GONE_RE = re.compile(r"session '[^']*' not found|no active sessions", re.IGNORECASE)


def now() -> str:
    return time.strftime("%H:%M:%S")


class Sup:
    def __init__(self, spec_path: str) -> None:
        raw = Path(spec_path).read_text().replace("{work}", str(S)).replace("{repo}", str(REPO))
        self.spec = json.loads(raw)
        self.ldir = Path(self.spec["ldir"])
        self.ldir.mkdir(parents=True, exist_ok=True)
        self.state_path = self.ldir / "sup_state.json"
        self.st = json.loads(self.state_path.read_text()) if self.state_path.exists() else \
            {"done": [], "skipped": {}, "fails": {}, "reclaims": 0, "vms": [], "vm": None, "vm_ready": False}
        self.run_reclaims = 0  # reclaims in this supervisor run (st["reclaims"] is the all-time count)

    # ---------- bookkeeping
    def log(self, msg: str) -> None:
        line = f"{now()} {msg}"
        print(line, flush=True)
        with (self.ldir / "sup.log").open("a") as fh:
            fh.write(line + "\n")

    def save(self) -> None:
        self.state_path.write_text(json.dumps(self.st, indent=1))

    # ---------- remote primitives
    def cli(self, *args: str, timeout: int = 300) -> tuple[int, str]:
        return run_cli([C7, *args], timeout)

    def rsh(self, cmd: str, timeout: int = 600, tries: int = 4) -> str:
        """Run a short shell command on the VM through the kernel; returns its output, raises on failure."""
        code = ("import subprocess\nr = subprocess.run(" + repr(cmd) + ", shell=True, capture_output=True, text=True)\n"
                "print(r.stdout[-4000:]); print(r.stderr[-2000:]); print('__RC__', r.returncode)\n")
        fd, fname = tempfile.mkstemp(prefix="rsh_", suffix=".py", dir=S)  # one file per call: calls run in parallel
        os.close(fd)
        f = Path(fname)
        f.write_text(code)
        try:
            return self._rsh_try(f, cmd, timeout, tries)
        finally:
            f.unlink(missing_ok=True)

    def _rsh_try(self, f: Path, cmd: str, timeout: int, tries: int) -> str:
        out = ""
        for t in range(tries):
            _, out = self.cli("exec", "-s", self.st["vm"], "-f", str(f), timeout=timeout)
            m = re.search(r"__RC__ (-?\d+)", out)
            if m:
                if m.group(1) != "0":
                    raise RuntimeError(f"remote command failed rc={m.group(1)}: {cmd[:120]}\n{out[-1500:]}")
                return out
            if GONE_RE.search(out):
                raise ConnectionError("session gone")
            time.sleep(10 * (t + 1))
        raise ConnectionError(f"remote exec never completed: {out[-300:]}")

    def up(self, local: str, remote: str) -> None:
        self.rsh(f"mkdir -p {shlex.quote(str(Path(remote).parent))}")  # the contents API returns 500 if the dir is missing
        for _ in range(4):
            _, out = self.cli("upload", "-s", self.st["vm"], local, remote, timeout=600)
            if "uploaded" in out.lower():
                return
            if GONE_RE.search(out):
                raise ConnectionError("session gone")
        raise ConnectionError(f"upload failed: {local}")

    def launch_bg(self, script_remote: str, log_remote: str) -> None:
        """Start script_remote in the background, logging to log_remote and appending JOB_EXIT=<rc>.
        A lock (held by the job and all its children) makes a duplicate launch, e.g. a retried exec whose reply
        was lost, exit immediately; only the winning launch rotates the old log, so a stale JOB_EXIT never leaks."""
        inner = (f"exec 9>{log_remote}.lock; flock -n 9 || exit 0; mv -f {log_remote} {log_remote}.prev 2>/dev/null; "
                 f"exec > {log_remote} 2>&1; bash {script_remote}; echo JOB_EXIT=$?")
        self.rsh(f"mkdir -p $(dirname {log_remote}) && (nohup bash -c {shlex.quote(inner)} > /dev/null 2>&1 &)")

    def poll(self, log_rel: str, files: list[str], rdir: str, stall: int) -> int:
        cmd = [sys.executable, str(HERE / "poll.py"), "--name", self.st["vm"], "--rdir", rdir, "--log", log_rel,
               "--ldir", str(self.ldir), "--interval", str(self.spec.get("interval", 90)), "--stall", str(stall),
               "--task_cap", str(self.spec["task_cap"]), *files]
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, text=True)
        last = ""
        for line in p.stdout:
            last = line.rstrip()
            self.log("  poll " + last)
        return p.wait()

    # ---------- big files: chunked, parallel, sha-verified
    @staticmethod
    def sha(path: Path) -> str:
        h = hashlib.sha256()
        with path.open("rb") as fh:
            for b in iter(lambda: fh.read(1 << 24), b""):
                h.update(b)
        return h.hexdigest()

    def push_big(self, local: str, remote: str) -> None:
        lp = Path(local)
        digest = self.sha(lp)
        cdir = S / "xfer" / digest[:12]
        if not cdir.exists() or not any(cdir.iterdir()):
            cdir.mkdir(parents=True, exist_ok=True)
            subprocess.run(["split", "-b", CHUNK, str(lp), str(cdir) + "/c_"], check=True)
        rtmp = f"/content/xin_{digest[:12]}"
        self.rsh(f"mkdir -p {rtmp}")
        chunks = sorted(cdir.iterdir())
        with ThreadPoolExecutor(4) as ex:
            list(ex.map(lambda c: self.up(str(c), f"{rtmp}/{c.name}"), chunks))
        out = self.rsh(f"mkdir -p $(dirname {remote}) && cat {rtmp}/c_* > {remote} && sha256sum {remote} && rm -rf {rtmp}")
        if digest not in out:
            raise RuntimeError(f"sha mismatch after push of {local}")
        self.log(f"pushed {lp.name} ({len(chunks)} chunks, sha ok)")

    def pull_big(self, remote: str, local: str) -> None:
        tag = hashlib.sha1(remote.encode()).hexdigest()[:10]
        rtmp = f"/content/xout_{tag}"
        out = self.rsh(f"rm -rf {rtmp} && mkdir -p {rtmp} && split -b {CHUNK} {remote} {rtmp}/c_ && sha256sum {remote} "
                       f"&& ls {rtmp}")
        digest = re.search(r"([0-9a-f]{64})\s", out).group(1)
        names = sorted(set(re.findall(r"\bc_[a-z]+\b", out)))
        ldir = Path(local).parent
        ldir.mkdir(parents=True, exist_ok=True)
        cdir = ldir / f".chunks_{tag}"
        cdir.mkdir(exist_ok=True)

        def get(n: str) -> None:
            for _ in range(4):
                rc, _ = self.cli("download", "-s", self.st["vm"], f"{rtmp}/{n}", str(cdir / n), timeout=900)
                if rc == 0 and (cdir / n).exists():
                    return
            raise ConnectionError(f"download failed {n}")
        with ThreadPoolExecutor(4) as ex:
            list(ex.map(get, names))
        part = Path(local + ".part")
        with part.open("wb") as fh:
            for n in names:
                fh.write((cdir / n).read_bytes())
        if self.sha(part) != digest:
            raise RuntimeError(f"sha mismatch pulling {remote}")
        part.replace(local)
        shutil.rmtree(cdir, ignore_errors=True)
        self.rsh(f"rm -rf {rtmp}")
        self.log(f"pulled {remote} -> {local} ({len(names)} chunks, sha {digest[:12]} ok)")

    # ---------- VM lifecycle
    def alive(self) -> bool:
        if not self.st["vm"]:
            return False
        _, out = self.cli("status", "-s", self.st["vm"], timeout=120)
        return not GONE_RE.search(out)

    def new_vm(self) -> None:
        for attempt in range(4):
            name = f"{self.spec['name']}{len(self.st['vms']) + 1}"
            self.st["vms"].append(name)
            self.st["vm"], self.st["vm_ready"] = name, False
            self.save()
            hb_log = self.ldir / "heartbeat" / f"{name}.log"
            p = subprocess.run([str(HERE / "newvm.sh"), name, str(hb_log)], capture_output=True, text=True, timeout=900, check=False)
            self.log(f"newvm {name}: {p.stdout.strip().splitlines()[-1] if p.stdout.strip() else p.stderr[-200:]}")
            if "NEWVM_OK" in p.stdout:
                return
            time.sleep(120)
        raise SystemExit("could not allocate an A100 after 4 attempts")

    def setup_vm(self) -> None:
        su = self.spec["setup"]
        for local, remote in su.get("uploads", []):
            self.up(local, remote)
        (S / "steps").mkdir(exist_ok=True)
        script = S / "steps" / f"{self.spec['name']}_setup.sh"
        script.write_text("set -e\ncd /content\n" + su["cmd"] + "\n")
        self.up(str(script), "/content/setup.sh")
        self.launch_bg("/content/setup.sh", "/content/setup.log")
        rc = self.poll("setup.log", [], "/content", 900)
        if rc == 2:
            raise ConnectionError("VM gone during setup")
        if rc != 0:
            raise RuntimeError(f"setup failed (poll rc {rc})")
        for local, remote in su.get("big_uploads", []):
            self.push_big(local, remote)
        pending = [s for s in self.spec["steps"] if s["name"] not in self.st["done"]]
        needed = {d for s in pending for d in s.get("needs", [])}
        for step in self.spec["steps"]:  # restore only what the remaining steps need from finished ones
            if step["name"] in self.st["done"] and step["name"] in needed:
                self.restore(step)
        self.st["vm_ready"] = True
        self.save()

    def restore(self, step: dict) -> None:
        rdir = self.spec["rdir"]
        for rel in step.get("restore", []):
            lp = self.ldir / rel
            (self.push_big if lp.stat().st_size > 200e6 else self.up)(str(lp), f"{rdir}/{rel}")
        for rel, local in step.get("big_outputs", []):
            self.push_big(local, f"{rdir}/{rel}")
        if step.get("restore_cmd"):
            self.rsh(f"cd {rdir} && {step['restore_cmd']}")
        self.log(f"restored outputs of {step['name']}")

    def ensure_vm(self) -> None:
        if self.alive() and self.st["vm_ready"]:
            return
        if self.st["vm"] and not self.alive():
            self.log(f"VM {self.st['vm']} is gone")
        if not self.alive():
            self.new_vm()
        self.setup_vm()

    def stop_vm(self) -> None:
        if self.st["vm"]:
            self.cli("stop", "-s", self.st["vm"], timeout=180)
            self.log(f"stopped {self.st['vm']}")
            self.st["vm"], self.st["vm_ready"] = None, False
            self.save()

    # ---------- steps
    def step_script(self, step: dict) -> str:
        logs = [log for _, log in step["cmds"]]
        lines = ["cd " + self.spec["rdir"], "export PYTHONPATH=scripts", "PIDS=''"]
        dirs = sorted({str(Path(rel).parent) for rel in step.get("outputs", [])} - {"."})
        if dirs:  # scripts open their outputs for append and do not create the folder
            lines.append("mkdir -p " + " ".join(shlex.quote(d) for d in dirs))
        for cmd, log in step["cmds"]:
            lines += [f"mkdir -p $(dirname {log})", f"( {cmd} ) > {log} 2>&1 &", "PIDS=\"$PIDS $!\""]
        tails = " ".join(shlex.quote(x) for x in logs)
        lines += [
            "hb() { while sleep 60; do echo \"HB $(for f in " + tails + "; do tail -c 400 $f 2>/dev/null | tr '\\r' '\\n'"
            " | grep -v '^[[:space:]]*$' | tail -n1 | cut -c1-70; done | paste -sd'|' -)\"; done; }",
            "hb & HB=$!", "RC=0", "for p in $PIDS; do wait $p || RC=1; done", "kill $HB 2>/dev/null",
            f"for f in {tails}; do echo \"== $f\"; tail -n 4 $f; done", "exit $RC"]
        return "\n".join(lines) + "\n"

    def run_step(self, step: dict) -> str:
        name, rdir = step["name"], self.spec["rdir"]
        outputs = step.get("outputs", [])
        sublogs = [log for _, log in step["cmds"]]
        while True:
            try:
                self.ensure_vm()
                for rel in outputs:  # partial outputs -> VM, so --resume continues where the last VM stopped
                    if (self.ldir / rel).exists() and step.get("resume", False):
                        self.rsh(f"mkdir -p $(dirname {rdir}/{rel})")
                        self.up(str(self.ldir / rel), f"{rdir}/{rel}")
                script = S / "steps" / f"{self.spec['name']}_{name}.sh"
                script.write_text(self.step_script(step))
                self.up(str(script), f"{rdir}/steps/{name}.sh")
                self.launch_bg(f"{rdir}/steps/{name}.sh", f"{rdir}/steps/{name}.log")
                self.log(f"step {name}: launched on {self.st['vm']}")
                rc = self.poll(f"steps/{name}.log", outputs + sublogs, rdir, step.get("stall", 300))
            except ConnectionError as e:
                self.log(f"step {name}: connection/session problem: {e}")
                # a reclaim only if the VM is really gone; an error on a live VM is a failure, so it cannot loop
                rc = 2 if not self.alive() else 1
                if rc == 1:
                    self.log(f"step {name}: VM {self.st['vm']} is still up, so this is an error, not a reclaim")
            if rc == 0:
                for rel, local in step.get("big_outputs", []):
                    self.pull_big(f"{rdir}/{rel}", local)
                return "done"
            if rc == 2:
                if self.run_reclaims >= MAX_RECLAIMS:
                    return "too_many_reclaims"
                self.run_reclaims += 1
                self.st["reclaims"] += 1
                self.st["vm_ready"] = False
                self.save()
                self.log(f"step {name}: VM reclaimed (reclaim #{self.st['reclaims']}), relaunching; not a job failure")
                continue
            if rc in (3, 5):
                return {3: "low_balance", 5: "cu_cap"}[rc]
            if rc == 4:
                try:
                    self.rsh("pkill -f '[s]teps/' ; pkill -f '[p]ython scripts/' ; true")  # [x] so pkill spares this shell
                except (ConnectionError, RuntimeError) as e:
                    self.log(f"kill after stall failed: {e}")
            self.st["fails"][name] = self.st["fails"].get(name, 0) + 1
            self.save()
            self.log(f"step {name}: {'STALLED' if rc == 4 else 'JOB_FAILED'} (failure {self.st['fails'][name]}/{MAX_FAILS})")
            if self.st["fails"][name] >= MAX_FAILS:
                return "skipped"

    def run(self) -> int:
        self.log(f"supervisor start: {self.spec['name']}  done={self.st['done']}")
        try:
            for step in self.spec["steps"]:
                if step["name"] in self.st["done"] or step["name"] in self.st["skipped"]:
                    continue
                if any(d not in self.st["done"] for d in step.get("needs", [])):
                    self.st["skipped"][step["name"]] = "dependency not done"
                    self.save()
                    self.log(f"step {step['name']}: skipped, a dependency did not finish")
                    continue
                res = self.run_step(step)
                if res == "done":
                    self.st["done"].append(step["name"])
                elif res == "skipped":
                    self.st["skipped"][step["name"]] = "failed twice"
                else:
                    self.save()
                    self.log(f"STOPPING: {res}")
                    if res == "cu_cap":
                        self.stop_vm()
                    if res == "too_many_reclaims":
                        self.stop_vm()
                        return 6
                    return 5 if res == "cu_cap" else 3
                self.save()
                self.log(f"step {step['name']}: {res}")
        except Exception as e:  # noqa: BLE001 - last-resort guard so the VM is always released
            self.log(f"SUPERVISOR ERROR: {type(e).__name__}: {e}")
            self.stop_vm()
            return 1
        self.stop_vm()
        self.log(f"supervisor end: done={self.st['done']} skipped={self.st['skipped']} reclaims={self.st['reclaims']}")
        return 0


if __name__ == "__main__":
    sys.exit(Sup(sys.argv[1]).run())
