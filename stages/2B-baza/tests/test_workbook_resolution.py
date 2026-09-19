"""LIVE-first workbook resolution (user, 2026-08-30): default to the live SB,
fall back to the local copy on conflict, keep that copy fresh while live is
healthy. All on tmp files — the probe/refresh helpers are pure filesystem."""

from __future__ import annotations

import os
from pathlib import Path

from cave_dossier.core.config import resolve_live_workbook
from cave_dossier.sb.safe_io import probe_live_workbook, refresh_fallback_copy


def _workbook(path: Path, content: bytes = b"live-bytes") -> Path:
    path.write_bytes(content)
    return path


# ── probe ──────────────────────────────────────────────────────────


def test_probe_passes_a_healthy_workbook(tmp_path: Path) -> None:
    live = _workbook(tmp_path / "sb.xlsm")
    assert probe_live_workbook(live) is None


def test_probe_flags_a_missing_workbook(tmp_path: Path) -> None:
    reason = probe_live_workbook(tmp_path / "nope.xlsm")
    assert reason is not None and "nedostupan" in reason


def test_probe_flags_an_excel_lock_file(tmp_path: Path) -> None:
    live = _workbook(tmp_path / "sb.xlsm")
    (tmp_path / "~$sb.xlsm").write_bytes(b"")
    reason = probe_live_workbook(live)
    assert reason is not None and "otvoren" in reason


# ── fallback refresh ───────────────────────────────────────────────


def test_refresh_copies_when_the_copy_is_missing_or_stale(tmp_path: Path) -> None:
    live = _workbook(tmp_path / "sb.xlsm")
    fallback = tmp_path / "copy" / "sb.xlsm"
    assert refresh_fallback_copy(live, fallback) is True
    assert fallback.read_bytes() == b"live-bytes"
    # Identical size+mtime → no copy the second time.
    assert refresh_fallback_copy(live, fallback) is False
    # Live changes (newer mtime) → refreshed again.
    _workbook(live, b"newer-live")
    os.utime(live, (live.stat().st_atime, fallback.stat().st_mtime + 60))
    assert refresh_fallback_copy(live, fallback) is True
    assert fallback.read_bytes() == b"newer-live"


# ── resolution ─────────────────────────────────────────────────────


def test_healthy_live_wins_and_refreshes_the_fallback(tmp_path: Path) -> None:
    live = _workbook(tmp_path / "sb.xlsm")
    fallback = tmp_path / "copy.xlsm"
    workbook, mode, reason = resolve_live_workbook(live, fallback)
    assert (workbook, mode, reason) == (live, "LIVE", None)
    assert fallback.read_bytes() == b"live-bytes"  # refreshed as a side effect


def test_locked_live_falls_back_with_a_reason(tmp_path: Path) -> None:
    live = _workbook(tmp_path / "sb.xlsm")
    (tmp_path / "~$sb.xlsm").write_bytes(b"")
    fallback = _workbook(tmp_path / "copy.xlsm", b"cached")
    workbook, mode, reason = resolve_live_workbook(live, fallback)
    assert workbook == fallback
    assert mode == "FALLBACK"
    assert reason is not None and "otvoren" in reason


def test_no_usable_fallback_stays_live(tmp_path: Path) -> None:
    # Conflict + no fallback copy on disk → LIVE anyway, so the read-time
    # safe_io diagnosis (not a silent wrong file) is what the user sees.
    live = tmp_path / "missing.xlsm"
    workbook, mode, reason = resolve_live_workbook(live, tmp_path / "no-copy.xlsm")
    assert (workbook, mode, reason) == (live, "LIVE", None)
    workbook, mode, reason = resolve_live_workbook(live, None)
    assert (workbook, mode, reason) == (live, "LIVE", None)
