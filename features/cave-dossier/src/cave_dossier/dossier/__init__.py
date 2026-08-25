"""Per-cave dossier: the model, its gathering steps, and the gating verdict.

Pipeline part 2.1 (see repo-root ARCHITECTURE.md).  M2 implements the model
plus SB gathering; archive intake, survey handoff (2.1a), OSZ read-back (2.1b)
and isječak karte (2.1c) fill the remaining sources in later milestones.
"""

from cave_dossier.dossier.gating import RULES, evaluate, start_year
from cave_dossier.dossier.model import (
    ArchiveFile,
    CaveDossier,
    DossierIssue,
    FileRole,
    Georeference,
    IssueCode,
    QueueFlag,
    ReadinessReport,
    Severity,
    Source,
    SurveyResult,
    UncheckedRule,
)
from cave_dossier.dossier.report import render
from cave_dossier.dossier.sb_mapper import build_from_sb, parse_queue_flag

__all__ = [
    "ArchiveFile",
    "CaveDossier",
    "DossierIssue",
    "FileRole",
    "Georeference",
    "IssueCode",
    "QueueFlag",
    "RULES",
    "ReadinessReport",
    "Severity",
    "Source",
    "SurveyResult",
    "UncheckedRule",
    "build_from_sb",
    "evaluate",
    "parse_queue_flag",
    "render",
    "start_year",
]
