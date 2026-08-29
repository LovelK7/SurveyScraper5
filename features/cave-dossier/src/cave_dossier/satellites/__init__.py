"""Satellite tables around SB — the communication hub (part 2.2).

SB (`Svi objekti`) is the master cave registry, but four other tables hold cave
data and **none of them carries an SB row number**: the Liburnija Google Sheet
(the *LiDAR Kristal* table, live and edited in the field), `Literatura`,
`Katastar RH`, and whatever the next LIDAR campaign produces.

This package is the one place that knows how to line them up with SB:

* `liburnija` — the adapter for one satellite; a new table means a new module
  here and nothing else.
* `resolver` — ranked join keys (plaque → `LiDAR Kristal N` synonym →
  coordinates → name), never a local row id.
* `sync` — the three review lists a run produces. Nothing is written by machine.

Design and the measurements behind every threshold:
`docs/sb-liburnija-hub.md`.
"""

from cave_dossier.satellites import liburnija, resolver, sync
from cave_dossier.satellites.model import (
    CandidateState,
    Decision,
    Difference,
    LinkStatus,
    NewRow,
    SyncResult,
)
from cave_dossier.satellites.resolver import (
    Resolution,
    SBRecord,
    build_sb_index,
    resolve_rows,
)

__all__ = [
    "CandidateState",
    "Decision",
    "Difference",
    "LinkStatus",
    "NewRow",
    "Resolution",
    "SBRecord",
    "SyncResult",
    "build_sb_index",
    "liburnija",
    "resolve_rows",
    "resolver",
    "sync",
]
