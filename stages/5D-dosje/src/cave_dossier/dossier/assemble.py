"""Assemble a cave's dossier from its SB row — the one shared recipe.

``cavedossier report``, ``cavedossier people check --broj`` and the local
dashboard all need the same thing: SB mapping, the izjave scan through the
people registry, then the gating verdict. Keeping it here means the three can
never drift apart.

Fail-soft exactly like the report always was: an unconfigured or unreachable
izjave dir (Drive not mounted) leaves ``Source.STATEMENTS`` ungathered, so the
statement gates honestly report "not checked yet" instead of failing.

``people`` and ``georef`` are imported lazily: ``people.statements`` imports
``dossier.model`` (a top-level import would be a cycle), and ``georef`` drags
in the georef.hr flow modules that a plain ``import cave_dossier.dossier``
should not need.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from cave_dossier.dossier.gating import evaluate
from cave_dossier.dossier.model import CaveDossier
from cave_dossier.dossier.sb_mapper import build_from_sb

if TYPE_CHECKING:
    from cave_dossier.core.config import Settings
    from cave_dossier.sb.loader import CaveRow, SBReader


def assemble(settings: Settings, cave: CaveRow) -> CaveDossier:
    """SB row → mapped dossier → izjave linkage → evaluated (``readiness`` set)."""
    from cave_dossier.people.registry import PersonRegistry
    from cave_dossier.people.statements import enrich as enrich_statements

    dossier = build_from_sb(cave, settings)
    # The izjave dir is shared (not per-cave), so it can be scanned before
    # archive intake exists. Unreachable Drive → enrich returns False and the
    # statement gates stay "not checked yet".
    registry = PersonRegistry.load(settings.people_registry_path)
    enrich_statements(dossier, settings, registry)
    evaluate(dossier)
    return dossier


def view_for_serial(
    settings: Settings, serial: int, reader: SBReader | None = None
) -> dict | None:
    """The dashboard view (``report.to_view``) of the cave with this Redni broj.

    ``None`` when no SB row carries that Redni broj. Pass ``reader`` to reuse
    an already-loaded ``SBReader`` (the dashboard server keeps one around).
    """
    from cave_dossier.dossier.report import to_view
    from cave_dossier.georef import find_by_serial
    from cave_dossier.sb.loader import SBReader

    cave = find_by_serial(reader or SBReader(settings), settings, serial)
    if cave is None:
        return None
    return to_view(assemble(settings, cave))
