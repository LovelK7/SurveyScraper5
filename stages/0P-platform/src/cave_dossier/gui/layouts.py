"""KORAK 3a's layout menu as data, so the card can draw the sheets.

``nacrt_finish.py --layouts-json`` runs the whole finisher on the chosen
``_postp`` file without writing it, and leaves the menu the console would print,
with the page, the title block, every proposal's placements and each design's
wall outline, in one JSON file. The dashboard draws one A4 thumbnail per entry,
and a click puts its number into ``--layout`` (user, 2026-10-04: "now it's just
a blank field to enter a number").

The finisher is run as a script, not imported: it is a kit tool that prints as
it goes, and it is what the run itself will execute, so the thumbnails cannot
drift from the menu the run then reads. It takes well under a second, and the
answer is cached per (path, mtime, size).
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import threading
from pathlib import Path

from cave_dossier.gui.jobs import script_argv

TIMEOUT_S = 60
_CACHE: dict[tuple[str, int, int], dict] = {}
_LOCK = threading.Lock()


class LayoutError(Exception):
    """The menu could not be computed; the message is for the operator."""


def menu(tools: Path, survey: Path, timeout: float = TIMEOUT_S) -> dict:
    """The --layouts-json payload for ``survey``, from cache when unchanged."""
    script = tools / "nacrt_finish.py"
    if not script.is_file():
        raise LayoutError(f"Nema skripte {script}.")
    try:
        stat = survey.stat()
    except OSError as exc:
        raise LayoutError(f"Ne mogu pročitati {survey.name}: {exc}") from exc
    key = (str(survey), stat.st_mtime_ns, stat.st_size)
    with _LOCK:
        if key in _CACHE:
            return _CACHE[key]

    with tempfile.TemporaryDirectory(prefix="cd-layouts-") as tmp:
        out = Path(tmp) / "layouts.json"
        try:
            done = subprocess.run(
                script_argv(script, [str(survey), "--layouts-json", str(out)]),
                capture_output=True, timeout=timeout, encoding="utf-8",
                errors="replace", cwd=str(tools), stdin=subprocess.DEVNULL,
                env=dict(os.environ, PYTHONIOENCODING="utf-8"),
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        except subprocess.TimeoutExpired as exc:
            raise LayoutError(f"Izračun rasporeda traje dulje od {timeout:.0f} s.") from exc
        if not out.is_file():
            tail = (done.stderr or done.stdout or "").strip().splitlines()[-3:]
            raise LayoutError("Raspored nije izračunat: " + (" ".join(tail) or
                                                               f"izlazni kod {done.returncode}"))
        payload = json.loads(out.read_text(encoding="utf-8"))

    with _LOCK:
        _CACHE[key] = payload
    return payload
