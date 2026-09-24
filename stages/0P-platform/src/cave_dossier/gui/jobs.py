"""Running tools for the page: one subprocess per job, output kept in memory.

The page polls ``output(since)`` for new text and can type into the process's
stdin — the 3N tools ask questions (which file, which layout) the same way the
``.bat`` kit does, and answering them from the page is what keeps those tools
unchanged. Every job's full output is also written to ``runs/gui/`` so a run
can be read back after the server is gone.
"""

from __future__ import annotations

import codecs
import itertools
import os
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

#: Keep the last N finished jobs; older ones are dropped from memory (the log stays).
MAX_JOBS = 50

#: Runs a ``cavedossier`` subcommand with this very interpreter, so the page
#: always uses the venv the server was started from — no PATH lookup.
CLI_BOOTSTRAP = "import sys; from cave_dossier.cli import main; sys.exit(main())"


@dataclass
class Job:
    id: int
    title: str
    argv: list[str]
    display: str
    cwd: Path
    log_path: Path | None
    started: float = field(default_factory=time.time)
    finished: float | None = None
    returncode: int | None = None
    _chunks: list[str] = field(default_factory=list)
    _proc: subprocess.Popen | None = None
    _lock: threading.Lock = field(default_factory=threading.Lock)

    @property
    def running(self) -> bool:
        return self.returncode is None

    def append(self, text: str) -> None:
        with self._lock:
            self._chunks.append(text)
        if self.log_path is not None:
            try:
                with self.log_path.open("a", encoding="utf-8") as fh:
                    fh.write(text)
            except OSError:
                pass

    def output(self, since: int = 0) -> tuple[str, int]:
        """Text from character offset ``since`` on, and the new offset."""
        with self._lock:
            text = "".join(self._chunks)
        return text[since:], len(text)

    def send(self, line: str) -> bool:
        proc = self._proc
        if proc is None or proc.stdin is None or not self.running:
            return False
        try:
            proc.stdin.write((line + "\n").encode("utf-8"))
            proc.stdin.flush()
        except OSError:
            return False
        self.append(f"{line}\n")  # echo, like a console would
        return True

    def kill(self) -> None:
        proc = self._proc
        if proc is None or not self.running:
            return
        if os.name == "nt":
            # /T takes cSurvey and PowerShell children with it.
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                           capture_output=True, check=False)
        else:
            proc.kill()

    def to_json(self, since: int = 0) -> dict:
        text, offset = self.output(since)
        return {
            "id": self.id, "title": self.title, "display": self.display,
            "running": self.running, "returncode": self.returncode,
            "started": self.started, "finished": self.finished,
            "log": str(self.log_path) if self.log_path else None,
            "text": text, "offset": offset,
        }


class JobManager:
    def __init__(self, log_dir: Path | None = None) -> None:
        self._jobs: dict[int, Job] = {}
        self._ids = itertools.count(1)
        self._log_dir = log_dir
        self._lock = threading.Lock()

    def start(self, title: str, argv: list[str], display: str, cwd: Path) -> Job:
        job_id = next(self._ids)
        log_path = None
        if self._log_dir is not None:
            try:
                self._log_dir.mkdir(parents=True, exist_ok=True)
                stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
                slug = "".join(c if c.isalnum() else "-" for c in title.lower())[:40]
                log_path = self._log_dir / f"{stamp}_{job_id:03d}_{slug}.log"
            except OSError:
                log_path = None
        job = Job(job_id, title, argv, display, cwd, log_path)
        job.append(f"> {display}\n\n")
        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        try:
            job._proc = subprocess.Popen(
                argv, cwd=str(cwd), env=env, stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=0,
                creationflags=flags,
            )
        except OSError as exc:
            job.append(f"ERROR: ne mogu pokrenuti: {exc}\n")
            job.returncode = 99
            job.finished = time.time()
        else:
            threading.Thread(target=self._pump, args=(job,), daemon=True).start()
        with self._lock:
            self._jobs[job_id] = job
            for old in sorted(self._jobs)[:-MAX_JOBS]:
                if not self._jobs[old].running:
                    del self._jobs[old]
        return job

    @staticmethod
    def _pump(job: Job) -> None:
        proc = job._proc
        assert proc is not None and proc.stdout is not None
        decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        fd = proc.stdout.fileno()
        while True:
            try:
                data = os.read(fd, 4096)
            except OSError:
                break
            if not data:
                break
            text = decoder.decode(data).replace("\r\n", "\n")
            if text:
                job.append(text)
        tail = decoder.decode(b"", final=True)
        if tail:
            job.append(tail)
        rc = proc.wait()
        job.append(f"\n[gotovo, izlazni kod {rc}]\n")
        job.finished = time.time()
        job.returncode = rc

    def get(self, job_id: int) -> Job | None:
        return self._jobs.get(job_id)

    def list(self) -> list[Job]:
        return [self._jobs[k] for k in sorted(self._jobs, reverse=True)]


def cli_argv(args: list[str]) -> list[str]:
    return [sys.executable, "-c", CLI_BOOTSTRAP, *args]


def script_argv(script: Path, args: list[str]) -> list[str]:
    return [sys.executable, str(script), *args]
