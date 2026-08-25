"""Warning / blocker gating for a cave dossier.

Ported in substance from crospeleo-automation's
``services/readiness_validator.py`` (see docs/PORTING.md), which encodes the
MZOZT **Protokol v6** mandatory-field matrix:

* §6.1 **Tablica 2** — fields marked ``*`` are hard blockers, ``**`` are
  advisory warnings.
* §5.1 — year-conditional rules: GPS coordinates, an entrance photograph and
  the entrance plaque are mandatory iff exploration started in **2015 or
  later**.
* §5 caverns clause — the plaque rule does not apply to ``kaverna`` objects.

Two things are deliberately different from the crospeleo original:

1. **Rules declare which source feeds them.**  crospeleo validates a dossier
   that is already fully assembled; here the dossier is assembled milestone by
   milestone, so a rule whose source has not been gathered is reported as
   ``unchecked`` — never as a failure.  ``ready`` therefore requires both "no
   blockers" and "nothing left unchecked that could block".
2. **The gate sits before production, not before submission.**  A blocker here
   means the OSZ / Nacrt should not be produced or delivered yet; the national
   cadastre submission stays crospeleo-automation's gate downstream.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from cave_dossier.core.people import is_placeholder
from cave_dossier.dossier.model import (
    CaveDossier,
    DossierIssue,
    IssueCode,
    ReadinessReport,
    Severity,
    Source,
    UncheckedRule,
)

_YEAR_PATTERN = re.compile(r"(?:19|20)\d{2}")

#: §5.1 — from this exploration year on, GPS + entrance photo + plaque are mandatory.
PHOTO_REQUIRED_FROM_YEAR = 2015


@dataclass(frozen=True)
class Rule:
    """One gating rule.

    ``check`` returns ``None`` when the rule is satisfied, or an explanatory
    message when it is not.  ``sources`` lists every gathering step the rule
    needs; if any is missing the rule is reported as unchecked instead of run.
    """

    label: str          # the Croatian field name the operator knows
    code: IssueCode
    severity: Severity
    sources: tuple[Source, ...]
    check: Callable[[CaveDossier], str | None]


# ── Check helpers ─────────────────────────────────────────────────────


def _missing(label: str) -> str:
    return f"Missing '{label}' (Tablica 2 → {label})."


def _text(label: str, attribute: str) -> Callable[[CaveDossier], str | None]:
    def check(dossier: CaveDossier) -> str | None:
        value = getattr(dossier, attribute, None)
        if not isinstance(value, str) or is_placeholder(value):
            return _missing(label)
        return None

    return check


def _items(label: str, attribute: str) -> Callable[[CaveDossier], str | None]:
    def check(dossier: CaveDossier) -> str | None:
        return None if getattr(dossier, attribute, None) else _missing(label)

    return check


def _number(label: str, resolver: Callable[[CaveDossier], float | None]) -> Callable[[CaveDossier], str | None]:
    """Mandatory dimensions must be present *and* non-negative.

    A negative dimension is as good as missing: CroSpeleo rejects the value
    downstream, so catching it here keeps the bad number out of the OSZ.
    """

    def check(dossier: CaveDossier) -> str | None:
        value = resolver(dossier)
        if value is None:
            return _missing(label)
        if value < 0:
            return f"'{label}' is negative ({value:g}); only positive numbers are accepted."
        return None

    return check


def _coordinate_source(dossier: CaveDossier) -> str | None:
    georeference = dossier.georeference
    if georeference is None or is_placeholder(georeference.source):
        return _missing("Izvor koordinata")
    return None


def _georef_record(dossier: CaveDossier) -> str | None:
    georeference = dossier.georeference
    if georeference is None or is_placeholder(georeference.georef_record):
        return _missing("Georef zapis")
    return None


def _entrance_photo_flag_matches_archive(dossier: CaveDossier) -> str | None:
    """Cross-check the SB bookkeeping cell against what is actually on Drive.

    SB's "Fotografija ulaza = DA" is a human-maintained claim; the archive is
    the ground truth.  Disagreement in either direction is worth surfacing —
    it usually means the photo landed in the wrong folder, or the cell was
    never updated after the photo was filed.
    """
    claimed = (dossier.entrance_photo_flag or "").strip().casefold() in {"da", "yes", "1"}
    present = bool(dossier.entrance_photos)
    if claimed and not present:
        return (
            "SB says 'Fotografija ulaza: DA' but no entrance photo was found "
            "in the photo archive."
        )
    if present and not claimed:
        return (
            f"{len(dossier.entrance_photos)} entrance photo(s) found on Drive, but SB "
            f"'Fotografija ulaza' is {dossier.entrance_photo_flag or 'empty'} — SB cell is stale."
        )
    return None


# ── The rule table (Protokol v6, Tablica 2) ───────────────────────────
# Grouped by source so it stays readable as milestones fill the dossier in.

RULES: tuple[Rule, ...] = (
    # ── From SB (2.2) — available now ─────────────────────────────────
    Rule("Ime objekta", IssueCode.MISSING_FIELD, Severity.BLOCKER, (Source.SB,),
         _text("Ime objekta", "object_name")),
    Rule("Interni katastarski broj objekta u udruzi", IssueCode.MISSING_FIELD, Severity.BLOCKER, (Source.SB,),
         _text("Interni katastarski broj objekta u udruzi", "sue_number")),
    Rule("Najbliže mjesto", IssueCode.MISSING_FIELD, Severity.BLOCKER, (Source.SB,),
         _text("Najbliže mjesto", "nearest_place")),
    Rule("Lokalitet", IssueCode.MISSING_FIELD, Severity.BLOCKER, (Source.SB,),
         _text("Lokalitet", "locality")),
    Rule("Razdoblje istraživanja", IssueCode.MISSING_FIELD, Severity.BLOCKER, (Source.SB,),
         _text("Razdoblje istraživanja", "exploration_period")),
    Rule("Autori nacrta", IssueCode.MISSING_FIELD, Severity.BLOCKER, (Source.SB,),
         _items("Autori nacrta", "drawing_authors")),
    Rule("Dubina", IssueCode.MISSING_FIELD, Severity.BLOCKER, (Source.SB,),
         _number("Dubina", CaveDossier.effective_depth_m)),

    # ── From the survey (2.1a, M5) ────────────────────────────────────
    Rule("Horizontalna duljina", IssueCode.MISSING_FIELD, Severity.BLOCKER, (Source.SURVEY,),
         _number("Horizontalna duljina", CaveDossier.effective_horizontal_length_m)),
    Rule("Vertikalna razlika", IssueCode.MISSING_FIELD, Severity.BLOCKER, (Source.SURVEY,),
         _number("Vertikalna razlika", CaveDossier.effective_vertical_difference_m)),

    # ── From the OSZ (2.1b, M4) ───────────────────────────────────────
    Rule("Podrijetlo imena", IssueCode.MISSING_FIELD, Severity.BLOCKER, (Source.OSZ,),
         _text("Podrijetlo imena", "origin_of_name")),
    Rule("Položaj i pristup objektu", IssueCode.MISSING_FIELD, Severity.BLOCKER, (Source.OSZ,),
         _text("Položaj i pristup objektu", "location_access_text")),
    Rule("Vrsta objekta", IssueCode.MISSING_FIELD, Severity.BLOCKER, (Source.OSZ,),
         _text("Vrsta objekta", "object_type")),
    Rule("Hidrogeološka funkcija", IssueCode.MISSING_FIELD, Severity.BLOCKER, (Source.OSZ,),
         _text("Hidrogeološka funkcija", "hydrogeological_function")),
    Rule("Hidrološka karakteristika", IssueCode.MISSING_FIELD, Severity.BLOCKER, (Source.OSZ,),
         _text("Hidrološka karakteristika", "hydrological_characteristic")),
    Rule("Osnovni opis s tehničkim podacima", IssueCode.MISSING_FIELD, Severity.BLOCKER, (Source.OSZ,),
         _text("Osnovni opis s tehničkim podacima", "technical_description")),
    Rule("Perspektiva daljnjeg istraživanja", IssueCode.MISSING_FIELD, Severity.BLOCKER, (Source.OSZ,),
         _text("Perspektiva daljnjeg istraživanja", "future_exploration_perspective")),
    Rule("Zapisničar", IssueCode.MISSING_FIELD, Severity.BLOCKER, (Source.OSZ,),
         _text("Zapisničar", "recorder")),
    Rule("Članovi ekipe", IssueCode.MISSING_FIELD, Severity.BLOCKER, (Source.OSZ,),
         _items("Članovi ekipe", "team_members")),
    Rule("Istražile udruge", IssueCode.MISSING_FIELD, Severity.BLOCKER, (Source.OSZ,),
         _items("Istražile udruge", "organizations")),
    Rule("Širina ulaza", IssueCode.MISSING_FIELD, Severity.BLOCKER, (Source.OSZ,),
         _number("Širina ulaza", lambda d: d.entrance_width_m)),
    Rule("Visina/duljina ulaza", IssueCode.MISSING_FIELD, Severity.BLOCKER, (Source.OSZ,),
         _number("Visina/duljina ulaza", lambda d: d.entrance_height_or_length_m)),
    Rule("Izvor koordinata", IssueCode.MISSING_FIELD, Severity.BLOCKER, (Source.OSZ,),
         _coordinate_source),

    # ── Files on Drive (M2 intake) ────────────────────────────────────
    Rule("Zapisnik (OSZ DOCX)", IssueCode.MISSING_OSZ, Severity.BLOCKER, (Source.ARCHIVE,),
         lambda d: None if d.osz_document else "Missing the filled OSZ (Tablica 2 Prilozi → Zapisnik)."),
    Rule("Nacrt", IssueCode.MISSING_NACRT, Severity.BLOCKER, (Source.ARCHIVE,),
         lambda d: None if d.nacrt_pdfs else "Missing the Nacrt PDF (Tablica 2 Prilozi → Nacrt)."),
    Rule("Fotografija ulaza (SB ↔ arhiva)", IssueCode.MISSING_ENTRANCE_PHOTO, Severity.WARNING,
         (Source.SB, Source.ARCHIVE), _entrance_photo_flag_matches_archive),

    # ── Isječak karte (2.1c, M3) ──────────────────────────────────────
    Rule("Isječak karte", IssueCode.MISSING_MAP_EXCERPT, Severity.BLOCKER, (Source.MAP,),
         lambda d: None if d.map_excerpt else "Missing 'Isječak karte' (Tablica 2 Prilozi → Isječak karte)."),
    Rule("Georef zapis", IssueCode.MISSING_FIELD, Severity.BLOCKER, (Source.MAP,), _georef_record),
)


# ── Evaluation ────────────────────────────────────────────────────────


def evaluate(dossier: CaveDossier) -> ReadinessReport:
    """Run every rule that can run; return the verdict and store it on the dossier."""
    issues: list[DossierIssue] = []
    unchecked: list[UncheckedRule] = []

    for rule in RULES:
        missing_source = next((s for s in rule.sources if not dossier.has(s)), None)
        if missing_source is not None:
            unchecked.append(
                UncheckedRule(label=rule.label, source=missing_source, severity=rule.severity)
            )
            continue
        message = rule.check(dossier)
        if message:
            issues.append(
                DossierIssue(
                    code=rule.code,
                    severity=rule.severity,
                    message=message,
                    label=rule.label,
                    source=rule.sources[0],
                )
            )

    issues.extend(_year_conditional_issues(dossier, unchecked))
    issues.extend(_statement_issues(dossier, unchecked))
    issues.extend(_context_notes(dossier))

    report = ReadinessReport(
        ready=not any(i.severity is Severity.BLOCKER for i in issues)
        and not any(u.severity is Severity.BLOCKER for u in unchecked),
        issues=issues,
        unchecked=unchecked,
    )
    dossier.readiness = report
    return report


def start_year(dossier: CaveDossier) -> int | None:
    """Earliest 19xx/20xx year mentioned in the exploration period."""
    for candidate in (dossier.exploration_period, dossier.last_exploration_year):
        if not candidate:
            continue
        years = _YEAR_PATTERN.findall(candidate)
        if years:
            return min(int(year) for year in years)
    return None


def _year_conditional_issues(
    dossier: CaveDossier, unchecked: list[UncheckedRule]
) -> list[DossierIssue]:
    """Protokol §5.1 — GPS / entrance photo / plaque, mandatory from 2015 on.

    Below 2015 (or when no year can be read) the same three are warnings: the
    data is still worth having, but an old exploration cannot be gated on it.
    """
    issues: list[DossierIssue] = []
    if not dossier.has(Source.SB):
        return issues

    year = start_year(dossier)
    modern = year is not None and year >= PHOTO_REQUIRED_FROM_YEAR
    severity = Severity.BLOCKER if modern else Severity.WARNING
    qualifier = (
        f"exploration year {year} ≥ {PHOTO_REQUIRED_FROM_YEAR}"
        if modern
        else f"exploration year {year or 'unknown'} — Protokol §5.1 does not gate on it"
    )

    if dossier.exploration_period and not _YEAR_PATTERN.search(dossier.exploration_period):
        issues.append(
            DossierIssue(
                code=IssueCode.INVALID_FIELD,
                severity=Severity.WARNING,
                label="Razdoblje istraživanja",
                source=Source.SB,
                message=(
                    f"Malformed 'Razdoblje istraživanja' value "
                    f"{dossier.exploration_period!r}: no 4-digit year found, so the "
                    f"§5.1 year-conditional checks fall back to 'unknown year'."
                ),
            )
        )

    if dossier.georeference is None or not dossier.georeference.has_position:
        issues.append(
            DossierIssue(
                code=IssueCode.MISSING_COORDINATES,
                severity=severity,
                label="Koordinate ulaza",
                source=Source.SB,
                message=f"No entrance coordinates in SB ({qualifier}).",
            )
        )

    if not _is_cavern(dossier) and is_placeholder(dossier.plaque_number):
        issues.append(
            DossierIssue(
                code=IssueCode.MISSING_PLAQUE,
                severity=severity,
                label="Broj pločice",
                source=Source.SB,
                message=f"No 'Broj pločice' in SB ({qualifier}).",
            )
        )

    # The photo itself lives on Drive: only judge it once intake has run.
    if dossier.has(Source.ARCHIVE):
        if not dossier.entrance_photos:
            issues.append(
                DossierIssue(
                    code=IssueCode.MISSING_ENTRANCE_PHOTO,
                    severity=severity,
                    label="Fotografija ulaza",
                    source=Source.ARCHIVE,
                    message=f"No entrance photo in the photo archive ({qualifier}).",
                )
            )
    else:
        unchecked.append(
            UncheckedRule(label="Fotografija ulaza", source=Source.ARCHIVE, severity=severity)
        )

    return issues


def _statement_issues(
    dossier: CaveDossier, unchecked: list[UncheckedRule]
) -> list[DossierIssue]:
    """Per-author "Izjava za katastar" gating.

    Checked **per author**, never "are there any statement files at all": the
    2026-05-27 Konglomeratača case slipped through exactly that way — the photo
    author's izjava was present, so a non-empty list hid a missing drawing-author
    izjava.  Requires the statements dir, hence ``Source.ARCHIVE``.
    """
    if not dossier.has(Source.ARCHIVE):
        unchecked.append(
            UncheckedRule(
                label="Izjava za katastar (po autoru)",
                source=Source.ARCHIVE,
                severity=Severity.BLOCKER,
            )
        )
        return []

    # Provisional matcher: substring on the filename stem.  crospeleo's
    # `services/name_resolver.py` (initials, surname-only, diacritic folding)
    # is the planned port — it lands together with the M2 archive intake, at
    # which point this path stops being dead code.
    issues: list[DossierIssue] = []
    buckets = (
        ("nacrta", dossier.drawing_authors, dossier.drawing_author_statement_files),
        ("fotografija", dossier.photo_author_candidates, dossier.photo_author_statement_files),
    )
    for role, authors, files in buckets:
        matched = {file.path.stem.casefold() for file in files}
        missing = [
            author
            for author in authors
            if not any(author.casefold() in stem or stem.endswith(author.casefold()) for stem in matched)
        ]
        if missing:
            issues.append(
                DossierIssue(
                    code=IssueCode.MISSING_STATEMENT,
                    severity=Severity.BLOCKER,
                    label=f"Izjava za katastar (autori {role})",
                    source=Source.ARCHIVE,
                    message=(
                        f"Missing 'Izjava za katastar' for {role} author(s): "
                        f"{', '.join(missing)}. Expected `Izjava_<ime>.<ext>` in the "
                        f"statements folder."
                    ),
                )
            )
    return issues


def _context_notes(dossier: CaveDossier) -> list[DossierIssue]:
    """Non-gating context the operator should see before working the cave."""
    notes: list[DossierIssue] = []
    if dossier.queue_flag.queued:
        detail = dossier.queue_flag.note or "no note"
        old = f", old Za-istražit broj {dossier.queue_flag.old_number}" if dossier.queue_flag.old_number else ""
        notes.append(
            DossierIssue(
                code=IssueCode.QUEUE_ITEM,
                severity=Severity.WARNING,
                label="Za istražit",
                source=Source.SB,
                message=(
                    f"Still in the 'Za istražit' queue{old}: {detail}. SB data for "
                    f"queued objects is provisional (often no SUE number yet)."
                ),
            )
        )
    return notes


def _is_cavern(dossier: CaveDossier) -> bool:
    """Caverns are exempt from the plaque rule (Protokol §5)."""
    return "kavern" in (dossier.object_type or "").casefold()
