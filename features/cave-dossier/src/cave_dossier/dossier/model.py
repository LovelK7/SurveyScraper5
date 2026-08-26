"""The cave dossier — everything known about one cave, from every source.

Adapted from crospeleo-automation's ``models/dossier.py`` (see docs/PORTING.md),
but pointed the other way round: crospeleo builds a dossier in order to *submit*
a finished cave to the national cadastre, while this tool builds one in order to
*produce* the two deliverables (OSZ + Nacrt).  So the model is organised by
**which pipeline part supplies a field**, and it is explicit about which sources
have been gathered at all — a field that is empty because nobody looked yet must
never be reported as a field that is missing.

Source map (part numbers per repo-root ARCHITECTURE.md):

| Source             | Part | Supplies                                                 |
|--------------------|------|----------------------------------------------------------|
| ``Source.SB``      | 2.2  | identity, coordinates, dimensions, year, drawing authors |
| ``Source.ARCHIVE`` | 2.1  | files on Drive: nacrt, izjave, fotografije ulaza, OSZ    |
| ``Source.SURVEY``  | 2.1a | processed survey: Nacrt PDF + measured dimensions        |
| ``Source.OSZ``     | 2.1b | fields read back out of a filled zapisnik                |
| ``Source.MAP``     | 2.1c | isječak karte PNG + georef record                        |
| ``Source.PHOTOS``  | 2.1d | entrance photos downsized + renamed for the archive      |

Only ``Source.SB`` is implemented at M2; the remaining fields are declared (so
the gating table can already name them) and stay empty until their milestone.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class Source(StrEnum):
    """A pipeline part that feeds the dossier. See the table in the module docstring."""

    SB = "sb"
    ARCHIVE = "archive"
    SURVEY = "survey"
    OSZ = "osz"
    MAP = "map"
    PHOTOS = "photos"


class GateLevel(StrEnum):
    """The two gates a cave passes, in order (confirmed by the user 2026-08-26).

    ``SUE`` — the society's own acceptance step: a readable Nacrt, an OSZ with
    its mandatory fields filled, entrance photos, a pločica, and an izjava per
    author. Passing it is what earns the cave its **katastarski broj SUE**,
    which is what moves it into the *Istraženi* view of SB.

    ``CROSPELEO`` — the stricter national-cadastre bar (Protokol v6), a
    superset of ``SUE``. A cave holding a SUE number is "almost a certain go";
    the submission itself stays crospeleo-automation's job downstream.
    """

    SUE = "sue"
    CROSPELEO = "crospeleo"


GATE_LABELS: dict[GateLevel, str] = {
    GateLevel.SUE: "katastarski broj (SUE)",
    GateLevel.CROSPELEO: "CroSpeleo",
}


def applies_at(rule_level: GateLevel, gate: GateLevel) -> bool:
    """CroSpeleo includes every SUE rule; the SUE gate ignores CroSpeleo-only ones."""
    return gate is GateLevel.CROSPELEO or rule_level is GateLevel.SUE


class LifecycleState(StrEnum):
    """Where the cave sits in SB — derived exactly as SB's own Power Query does.

    Extracted from the workbook's ``Formulas/Section1.m`` (2026-08-26):

    * ``IO_v2_1`` **Istraženi** — ``Katastarski broj SUE`` is not empty. That is
      the whole filter: holding a SUE number *is* the definition.
    * ``ZI_v2_1`` **Za istražit** — Napomena contains ``za istražit``.
    * ``NO_v2_1`` **Nesređeni** — Napomena contains any of ``neistraženo``,
      ``fali nacrt``, ``fali zapisnik``, ``<5 m``, ``puhalica``, ``ponor``,
      ``ponoviti``, ``nastaviti``, ``umjetan objekt``.

    SB's views overlap (29 caves have a SUE number *and* say "ponoviti"); this
    enum resolves to a single state, SUE number first, because holding one
    means gate 1 is already passed. ``UNCLASSIFIED`` is a real state, not a
    bug: 47 named rows carry neither a SUE number nor any flag, so they show up
    in none of SB's three views.
    """

    ISTRAZENI = "istraženi"
    ZA_ISTRAZIT = "za istražit"
    NESREDENI = "nesređeni"
    UNCLASSIFIED = "nesvrstano"


class Severity(StrEnum):
    """Two-tier gating, inherited from crospeleo-automation.

    ``WARNING`` is advisory — the operator sees it and decides.  ``BLOCKER``
    is a hard gate on the final action (producing / delivering the dossier).
    """

    WARNING = "warning"
    BLOCKER = "blocker"


class IssueCode(StrEnum):
    """Stable machine-readable code for an issue, so callers can filter."""

    MISSING_FIELD = "missing_field"
    INVALID_FIELD = "invalid_field"
    MISSING_OSZ = "missing_osz"
    MISSING_NACRT = "missing_nacrt"
    MISSING_ENTRANCE_PHOTO = "missing_entrance_photo"
    MISSING_STATEMENT = "missing_statement"
    MISSING_MAP_EXCERPT = "missing_map_excerpt"
    MISSING_COORDINATES = "missing_coordinates"
    MISSING_PLAQUE = "missing_plaque"
    QUEUE_ITEM = "queue_item"
    PARSE_NOTE = "parse_note"


class FileRole(StrEnum):
    """What an archive file is, independent of where it was found."""

    OSZ_DOCX = "osz_docx"
    NACRT_PDF = "nacrt_pdf"
    ENTRANCE_PHOTO = "entrance_photo"
    STATEMENT_DRAWING_AUTHOR = "statement_drawing_author"
    STATEMENT_PHOTO_AUTHOR = "statement_photo_author"
    STATEMENT = "statement"
    MAP_EXCERPT = "map_excerpt"
    SURVEY_SOURCE = "survey_source"  # TopoDroid .tdx / cSurvey .csx / .csz
    OTHER = "other"


class ArchiveFile(BaseModel):
    """One file resolved on the local Drive mount.

    ``size_bytes`` feeds part 2.1d (entrance-photo processing): field photos
    routinely land in the archive at full camera resolution, and they are meant
    to be downsized and renamed to the ``<SUE>_…`` convention before they are
    filed into ``!!Fotografije ulaza``.
    """

    path: Path
    role: FileRole
    exists: bool = True
    size_bytes: int | None = None
    source: str = "local_drive"


class Georeference(BaseModel):
    """Entrance position. HTRS96/TM is the SB-native CRS; lat/lon is derived."""

    x_htrs: float | None = None
    y_htrs: float | None = None
    z_m: float | None = None          # SB column "Z" — entrance elevation
    latitude: float | None = None
    longitude: float | None = None
    source: str | None = None         # "Izvor koordinata" (GPS, LIDAR, …)
    georef_record: str | None = None  # georef.hr record text (2.1c, M3)

    @property
    def has_position(self) -> bool:
        return any(
            value is not None
            for value in (self.x_htrs, self.y_htrs, self.latitude, self.longitude)
        )


class SurveyResult(BaseModel):
    """Dimensions handed over by 2.1a (csx-to-survey), M5.

    Kept separate from the SB values rather than overwriting them: a freshly
    processed survey disagreeing with the SB row is itself information (it is
    exactly what M6 writes back), so both numbers stay visible side by side.
    """

    length_m: float | None = None
    depth_m: float | None = None
    horizontal_length_m: float | None = None
    vertical_difference_m: float | None = None
    station_count: int | None = None
    source_path: Path | None = None


class QueueFlag(BaseModel):
    """The SB v3.0 "still to be explored" marker, parsed out of **Napomena**.

    Format (decision 2026-08-22, executed in the v3.0 restructure):
    ``za istražit, [<old Broj>,] <note>`` — the old Za-istražit Broj is
    **optional** (``Ponor Gotovž``: ``za istražit, detalji u literaturi``),
    so it is only ever a hint, never a key.
    """

    queued: bool = False
    old_number: str | None = None
    note: str | None = None
    raw: str | None = None


class DossierIssue(BaseModel):
    """One gating finding. ``label`` is the Croatian field name the operator knows."""

    code: IssueCode
    severity: Severity
    message: str
    level: GateLevel = GateLevel.SUE
    label: str | None = None
    source: Source | None = None

    @property
    def blocking(self) -> bool:
        return self.severity is Severity.BLOCKER


class UncheckedRule(BaseModel):
    """A rule that could not run because its source has not been gathered.

    The honest middle ground between "passes" and "fails": at M2 nothing but
    SB is gathered, so every file-based mandatory lands here instead of
    firing a blocker nobody could act on yet.
    """

    label: str
    source: Source
    severity: Severity
    level: GateLevel = GateLevel.SUE


class ReadinessReport(BaseModel):
    """Verdict of ``cave_dossier.dossier.gating.evaluate`` — one verdict per gate.

    Findings live in one flat list, each tagged with the gate it belongs to;
    the ``*_for`` helpers slice it. ``ready_sue`` / ``ready_crospeleo`` are
    stored rather than computed so they survive ``model_dump_json``.
    """

    ready_sue: bool = False
    ready_crospeleo: bool = False
    issues: list[DossierIssue] = Field(default_factory=list)
    unchecked: list[UncheckedRule] = Field(default_factory=list)

    def issues_for(self, gate: GateLevel) -> list[DossierIssue]:
        return [issue for issue in self.issues if applies_at(issue.level, gate)]

    def blockers_for(self, gate: GateLevel) -> list[DossierIssue]:
        return [i for i in self.issues_for(gate) if i.severity is Severity.BLOCKER]

    def warnings_for(self, gate: GateLevel) -> list[DossierIssue]:
        return [i for i in self.issues_for(gate) if i.severity is Severity.WARNING]

    def unchecked_for(self, gate: GateLevel) -> list[UncheckedRule]:
        return [rule for rule in self.unchecked if applies_at(rule.level, gate)]

    def ready_for(self, gate: GateLevel) -> bool:
        """No blockers at this gate, and nothing left unchecked that could block."""
        return not self.blockers_for(gate) and not [
            rule for rule in self.unchecked_for(gate) if rule.severity is Severity.BLOCKER
        ]

    @property
    def blockers(self) -> list[DossierIssue]:
        """Every blocker, both gates — for callers that do not care which."""
        return [issue for issue in self.issues if issue.severity is Severity.BLOCKER]

    @property
    def warnings(self) -> list[DossierIssue]:
        return [issue for issue in self.issues if issue.severity is Severity.WARNING]


class CaveDossier(BaseModel):
    """Everything known about one cave, plus the gating verdict."""

    # ── Provenance ────────────────────────────────────────────────────
    gathered: set[Source] = Field(default_factory=set)

    # ── Identity (SB) ─────────────────────────────────────────────────
    sb_row_number: int | None = None       # 1-based Excel row — the M6 write-back handle
    # "Redni broj" — the cave's identity BEFORE it earns a SUE number (user,
    # 2026-08-26). Distinct from sb_row_number: this is stored data that
    # survives edits above it, which is why intake folders and staged photo
    # filenames key on it. It stops being the working ID once sue_number exists.
    serial_number: int | None = None
    object_name: str | None = None
    sue_number: str | None = None          # "Katastarski broj SUE" — empty on queue rows
    plaque_number: str | None = None       # "Broj pločice"
    marker_value: str | None = None        # "Katastarski broj RH"
    crospeleo_round: str | None = None     # "CroSpeleo unos"
    synonyms: list[str] = Field(default_factory=list)
    sb_record: dict[str, Any] = Field(default_factory=dict)  # the raw row, verbatim

    # ── Location (SB now, refined by 2.1c) ────────────────────────────
    locality: str | None = None            # "Lokalitet"
    nearest_place: str | None = None       # "Najbliže mjesto"
    georeference: Georeference | None = None

    # ── Dimensions (SB now, 2.1a later) ───────────────────────────────
    length_m: float | None = None          # SB "Duljina"
    depth_m: float | None = None           # SB "Dubina"
    survey: SurveyResult | None = None

    # ── Exploration history (SB) ──────────────────────────────────────
    exploration_period: str | None = None     # "Godina ili period istraživanja"
    last_exploration_year: str | None = None  # "Godina zadnjeg istraživanja"
    drawing_authors: list[str] = Field(default_factory=list)  # "Autori nacrta", names only
    # Author -> the society written in brackets after the name ("A.Lipovac (SOV)").
    # In SB that bracket is a FLAG: the sketch was drawn by someone from outside
    # SUE. It is not part of the person's name, so it is kept separately.
    drawing_author_societies: dict[str, str] = Field(default_factory=dict)
    photo_author_candidates: list[str] = Field(default_factory=list)

    # ── SB bookkeeping cells (DA/NE flags + free text) ────────────────
    note: str | None = None                # "Napomena"
    lifecycle: LifecycleState = LifecycleState.UNCLASSIFIED
    nesredeni_keywords: list[str] = Field(default_factory=list)  # which NO_v2_1 words hit
    queue_flag: QueueFlag = Field(default_factory=QueueFlag)
    entrance_photo_flag: str | None = None        # "Fotografija ulaza"
    pollution_flag: str | None = None             # "Zagađenost"
    ice_cave_flag: str | None = None              # "Ledenica"
    supplementary_record_flag: str | None = None  # "Dopunski zapisnik?"
    nacrt_link: str | None = None                 # "Link Nacrt"
    zapisnik_link: str | None = None              # "Link Zapisnik"

    # ── Archive files on Drive (M2 intake — not populated yet) ────────
    local_folder: Path | None = None
    osz_document: ArchiveFile | None = None
    nacrt_pdfs: list[ArchiveFile] = Field(default_factory=list)
    entrance_photos: list[ArchiveFile] = Field(default_factory=list)
    statement_files: list[ArchiveFile] = Field(default_factory=list)
    drawing_author_statement_files: list[ArchiveFile] = Field(default_factory=list)
    photo_author_statement_files: list[ArchiveFile] = Field(default_factory=list)
    map_excerpt: ArchiveFile | None = None

    # ── Fields the OSZ supplies (2.1b, M4 — not populated yet) ────────
    # Names match crospeleo-automation's dossier so the ported readiness
    # rules — and later the OSZ fetcher — read across without translation.
    osz_fields: dict[str, str] = Field(default_factory=dict)
    object_type: str | None = None                  # "Vrsta objekta"
    origin_of_name: str | None = None               # "Podrijetlo imena"
    location_access_text: str | None = None         # "Položaj i pristup objektu"
    technical_description: str | None = None        # "Osnovni opis s tehničkim podacima"
    hydrogeological_function: str | None = None     # "Hidrogeološka funkcija"
    hydrological_characteristic: str | None = None  # "Hidrološka karakteristika"
    future_exploration_perspective: str | None = None  # "Perspektiva daljnjeg istraživanja"
    recorder: str | None = None                     # "Zapisničar"
    team_members: list[str] = Field(default_factory=list)
    organizations: list[str] = Field(default_factory=list)
    entrance_width_m: float | None = None
    entrance_height_or_length_m: float | None = None
    horizontal_length_m: float | None = None
    vertical_difference_m: float | None = None

    # ── Verdict ───────────────────────────────────────────────────────
    readiness: ReadinessReport = Field(default_factory=ReadinessReport)

    # ── Helpers ───────────────────────────────────────────────────────

    def has(self, source: Source) -> bool:
        return source in self.gathered

    @property
    def is_queued(self) -> bool:
        """Anything that has not passed gate 1 is work still waiting to be done.

        Per the user (2026-08-26) the worklist is "everything not in Istraženi" —
        za istražit, nesređeni and the unclassified rows alike.
        """
        return self.lifecycle is not LifecycleState.ISTRAZENI

    def mark_gathered(self, source: Source) -> None:
        self.gathered.add(source)

    @property
    def display_name(self) -> str:
        name = self.object_name or "<bez imena>"
        return f"{name} (SUE {self.sue_number})" if self.sue_number else name

    @property
    def working_id(self) -> str | None:
        """The identifier every processing step should file this cave under.

        The SUE number once it exists, the Redni broj before that (user,
        2026-08-26). Delivery renames pre-SUE artefacts to the SUE number as
        the last step, which is exactly when the SUE number appears.
        """
        if self.sue_number:
            return self.sue_number
        return str(self.serial_number) if self.serial_number is not None else None

    def effective_length_m(self) -> float | None:
        """A processed survey outranks the SB cell (SB is what M6 updates)."""
        if self.survey and self.survey.length_m is not None:
            return self.survey.length_m
        return self.length_m

    def effective_depth_m(self) -> float | None:
        if self.survey and self.survey.depth_m is not None:
            return self.survey.depth_m
        return self.depth_m

    def effective_horizontal_length_m(self) -> float | None:
        if self.survey and self.survey.horizontal_length_m is not None:
            return self.survey.horizontal_length_m
        return self.horizontal_length_m

    def effective_vertical_difference_m(self) -> float | None:
        """Falls back to depth — for jama-shaped objects the two are identical.

        Same rule crospeleo-automation applies (user direction 2026-05-31):
        recorders routinely leave the redundant cell blank, and blocking on it
        would gate almost every dossier.
        """
        if self.survey and self.survey.vertical_difference_m is not None:
            return self.survey.vertical_difference_m
        if self.vertical_difference_m is not None:
            return self.vertical_difference_m
        return self.effective_depth_m()
