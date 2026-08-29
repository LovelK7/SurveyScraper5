"""Shared vocabulary for the satellite tables around SB.

A *satellite* is a table that holds cave data and carries no SB row number:
the Liburnija Google Sheet, `Literatura`, `Katastar RH`. Each gets an adapter
that turns its rows into the types below; everything downstream — resolver,
sync, reports — is written against these and never against a specific table.

Design: [docs/sb-liburnija-hub.md](../../../docs/sb-liburnija-hub.md).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class CandidateState(str, Enum):
    """Where a satellite row sits in the *is this even a cave* lifecycle.

    LIDAR tables hold **probable** caves, so there are two states before SB's
    own lifecycle begins. Only ``TO_EXPLORE`` and ``EXPLORED`` are entitled to
    an SB row (user, 2026-08-29) — the crossing rule.
    """

    UNCHECKED = "neprovjeren"      # nobody has walked to the point
    NOT_A_CAVE = "nije objekt"     # someone did, and it is not a cave
    TO_EXPLORE = "za istražit"     # confirmed cave, not yet surveyed
    EXPLORED = "istražen"          # confirmed cave, surveyed

    @property
    def is_cave(self) -> bool:
        return self in (CandidateState.TO_EXPLORE, CandidateState.EXPLORED)


class LinkStatus(str, Enum):
    """What the resolver concluded about one satellite row."""

    LINKED = "linked"              # resolved to an SB row
    CANDIDATE = "candidate"        # a cave, no SB row — belongs in SB
    NOT_A_CAVE = "not_a_cave"      # checked and rejected; never enters SB
    UNCHECKED = "unchecked"        # nobody has been there yet
    OUT_OF_SCOPE = "out_of_scope"  # another society's cave
    CONFLICT = "conflict"          # two keys disagree, or two SB rows are equally close


@dataclass(frozen=True)
class Difference:
    """One cell the satellite has wrong, with the reason SB is believed.

    Rendered as a line a person carries out by hand in the browser — the
    satellite is never written to by machine (user, 2026-08-29).
    """

    row_id: str
    column: str
    current: str
    proposed: str
    reason: str


@dataclass(frozen=True)
class NewRow:
    """A confirmed cave the satellite has and SB does not, rendered for SB.

    ``values`` is keyed by SB column header, ready to be written out in SB's
    own column order.
    """

    row_id: str
    values: dict[str, str]
    warning: str | None = None


@dataclass(frozen=True)
class SBEdit:
    """One cell to ADD to a row SB already has.

    Distinct from ``Difference`` (which corrects the satellite) and from
    ``NewRow`` (which creates an SB row): this touches an existing SB row, and
    only ever by addition — ``proposed`` carries the current content plus the
    new value, never a replacement.
    """

    serial_number: int | None
    column: str
    current: str
    proposed: str
    reason: str
    row_id: str


@dataclass(frozen=True)
class Decision:
    """Something no rule may settle: a conflict, an ambiguity, an oddity."""

    row_id: str
    issue: str
    detail: str


@dataclass
class SyncResult:
    """The review lists one `sat sync` run produces, and the counts behind them."""

    to_sb: list[NewRow] = field(default_factory=list)
    to_sb_edits: list[SBEdit] = field(default_factory=list)
    to_sheet: list[Difference] = field(default_factory=list)
    to_decide: list[Decision] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)


__all__ = [
    "CandidateState",
    "Decision",
    "Difference",
    "LinkStatus",
    "NewRow",
    "SBEdit",
    "SyncResult",
]
