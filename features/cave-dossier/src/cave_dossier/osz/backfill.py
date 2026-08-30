"""SB backfill from a filled OSZ (part 2.1b/M4 — the fetcher direction).

Compares what a filled zapisnik says against the cave's SB row and proposes
what to carry back (user, 2026-08-30):

- **Broj pločice** — filled when SB's cell is empty;
- **Ime objekta / Sinonimi** — when the OSZ gave the cave a NEW name, the
  OSZ name replaces SB's and the old SB name moves into Sinonimi (plus any
  OSZ synonyms SB lacks);
- **Duljina / Dubina** — filled when SB's cells are empty;
- **Godina ili period istraživanja** — the OSZ's "Datum ili razdoblje
  istraživanja" cropped to SB's convention: a single year ("2025") or a
  period ("2018-2019");
- **Autori nacrta ili izvor** — the OSZ's Crtali, full names converted to
  SB's shorthand ("Lovel Kukuljan" → "L.Kukuljan", core/person_aliases);
  spellings are matched across the two conventions so an author already in
  SB is never duplicated.

Precedence mirrors the rest of the tool: an EMPTY SB cell gets a proposal;
a conflicting non-empty cell gets a difference note, never an override —
and, as everywhere, nothing writes to SB automatically: the output is a
review CSV a person carries into Excel (write-back lands at M6).
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from pathlib import Path

from cave_dossier.core.config import Settings
from cave_dossier.core.normalization import normalize_lookup_key, parse_optional_float
from cave_dossier.core.people import is_placeholder, split_authors, split_person_names
from cave_dossier.core.person_aliases import same_person, to_sb_shorthand
from cave_dossier.sb.loader import CaveRow, SBReader

BACKFILL_CSV_COLUMNS = (
    "Redni broj", "Stupac", "Sadašnja SB vrijednost", "Nova vrijednost", "Izvor",
)

_YEAR_RE = re.compile(r"\b(1[89]\d{2}|20\d{2})\b")


@dataclass(frozen=True)
class BackfillProposal:
    column: str          # the SB column header
    current: str         # what SB says now ("" when empty)
    proposed: str        # what the OSZ supports writing
    reason: str


@dataclass
class BackfillResult:
    proposals: list[BackfillProposal] = field(default_factory=list)
    differences: list[str] = field(default_factory=list)  # SB kept, human decides
    matches: list[str] = field(default_factory=list)      # confirmed identical
    notes: list[str] = field(default_factory=list)


def build_backfill(cave: CaveRow, osz: dict[str, str | None],
                   settings: Settings) -> BackfillResult:
    result = BackfillResult()
    _compare_plain(result, "Broj pločice",
                   _sb_text(cave, settings.sb_plaque_column), osz.get("broj_plocice"))
    _resolve_name_and_synonyms(result, cave, osz, settings)
    _compare_number(result, _column(settings, "length_m", "Duljina"),
                    _sb_text(cave, _column(settings, "length_m", "Duljina"), cave_row=True),
                    osz.get("duljina"))
    _compare_number(result, _column(settings, "depth_m", "Dubina"),
                    _sb_text(cave, _column(settings, "depth_m", "Dubina"), cave_row=True),
                    osz.get("dubina"))
    _resolve_year(result, cave, osz, settings)
    _resolve_authors(result, cave, osz, settings)
    return result


def write_backfill_csv(path: Path, serial: int, result: BackfillResult) -> None:
    """Same dialect as every other review CSV (utf-8-sig, comma, CRLF)."""
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\r\n")
        writer.writerow(BACKFILL_CSV_COLUMNS)
        for p in result.proposals:
            writer.writerow([serial, p.column, p.current, p.proposed, p.reason])


# ── year / period ────────────────────────────────────────────────────
def extract_year_period(datum_text: str | None) -> str | None:
    """SB's convention out of the OSZ's free-form date cell.

    "10.05.2025." → "2025"; "10.5.2014 – 17.5.2025" → "2014-2025";
    "2019" → "2019". No 4-digit year → None.
    """
    if not datum_text:
        return None
    years = sorted({int(y) for y in _YEAR_RE.findall(datum_text)})
    if not years:
        return None
    if len(years) == 1:
        return str(years[0])
    return f"{years[0]}-{years[-1]}"


# ── field resolvers ──────────────────────────────────────────────────
def _resolve_name_and_synonyms(result: BackfillResult, cave: CaveRow,
                               osz: dict[str, str | None], settings: Settings) -> None:
    name_col = settings.sb_object_name_column
    syn_col = _column(settings, "synonyms", "Sinonimi")
    sb_name = (cave.object_name or "").strip()
    osz_name = (osz.get("ime_objekta") or "").strip()
    sb_syns = _split_names_list(_sb_text(cave, syn_col, cave_row=True))
    osz_syns = _split_names_list(osz.get("sinonimi"))

    if not osz_name:
        if sb_name:
            result.notes.append("OSZ nema Ime objekta — ime i sinonimi preskočeni.")
        return

    renamed = sb_name and normalize_lookup_key(sb_name) != normalize_lookup_key(osz_name)
    if renamed:
        # The OSZ gave the cave a new name: it replaces SB's, and the old
        # SB name survives as a synonym (user, 2026-08-30).
        result.proposals.append(BackfillProposal(
            column=name_col, current=sb_name, proposed=osz_name,
            reason="OSZ daje novo ime; staro ime seli u Sinonimi",
        ))
    elif sb_name:
        result.matches.append(f"Ime objekta: '{sb_name}'")
    elif osz_name:
        result.proposals.append(BackfillProposal(
            column=name_col, current="", proposed=osz_name, reason="OSZ Ime objekta",
        ))

    merged = list(sb_syns)
    if renamed:
        _add_unique(merged, sb_name)
    for syn in osz_syns:
        _add_unique(merged, syn)
    merged = [s for s in merged if normalize_lookup_key(s) != normalize_lookup_key(osz_name)]
    if [normalize_lookup_key(s) for s in merged] != [normalize_lookup_key(s) for s in sb_syns]:
        result.proposals.append(BackfillProposal(
            column=syn_col, current=", ".join(sb_syns), proposed=", ".join(merged),
            reason="staro ime + sinonimi iz OSZ-a" if renamed else "sinonimi iz OSZ-a",
        ))
    elif sb_syns:
        result.matches.append(f"Sinonimi: '{', '.join(sb_syns)}'")


def _resolve_year(result: BackfillResult, cave: CaveRow,
                  osz: dict[str, str | None], settings: Settings) -> None:
    column = settings.sb_exploration_period_column or "Godina ili period istraživanja"
    sb_value = _sb_text(cave, column)
    osz_period = extract_year_period(osz.get("datum_istrazivanja"))
    if osz_period is None:
        if osz.get("datum_istrazivanja"):
            result.notes.append(
                f"Datum istraživanja '{osz['datum_istrazivanja']}' ne sadrži godinu."
            )
        return
    if not sb_value:
        result.proposals.append(BackfillProposal(
            column=column, current="", proposed=osz_period,
            reason=f"iz OSZ Datum istraživanja '{osz['datum_istrazivanja']}'",
        ))
    elif sb_value.replace("–", "-").replace(" ", "") == osz_period:
        result.matches.append(f"{column}: '{sb_value}'")
    else:
        result.differences.append(
            f"{column}: SB kaže '{sb_value}', OSZ podupire '{osz_period}' "
            f"(iz '{osz['datum_istrazivanja']}'). SB vrijednost je zadržana."
        )


def _resolve_authors(result: BackfillResult, cave: CaveRow,
                     osz: dict[str, str | None], settings: Settings) -> None:
    column = settings.sb_drawing_authors_column or "Autori nacrta ili izvor"
    sb_raw = _sb_text(cave, column)
    osz_people = split_person_names(osz.get("crtali"))
    if not osz_people:
        return
    shorthands = [to_sb_shorthand(p) for p in osz_people]

    if is_placeholder(sb_raw):
        result.proposals.append(BackfillProposal(
            column=column, current=sb_raw or "", proposed=", ".join(shorthands),
            reason="OSZ Crtali (puno ime → SB kratica)",
        ))
        return

    sb_people, _societies = split_authors(sb_raw)
    missing = [shorthands[i] for i, person in enumerate(osz_people)
               if not any(same_person(person, sb_person) for sb_person in sb_people)]
    extra = [sb_person for sb_person in sb_people
             if not any(same_person(sb_person, person) for person in osz_people)]
    if not missing:
        result.matches.append(
            f"{column}: '{sb_raw}' pokriva OSZ Crtali ({', '.join(osz_people)})"
        )
    else:
        # A later survey legitimately ADDS authors — merge, never drop.
        merged = sb_people + missing
        result.proposals.append(BackfillProposal(
            column=column, current=sb_raw or "", proposed=", ".join(merged),
            reason=f"OSZ Crtali dodaje: {', '.join(missing)}",
        ))
    if extra:
        result.notes.append(
            f"{column}: SB navodi i {', '.join(extra)} — OSZ Crtali ih nema "
            "(možda raniji nacrt); zadržani."
        )


# ── generic comparators ──────────────────────────────────────────────
def _compare_plain(result: BackfillResult, column: str | None,
                   sb_value: str | None, osz_value: str | None) -> None:
    if not column or not osz_value:
        return
    if not sb_value:
        result.proposals.append(BackfillProposal(
            column=column, current="", proposed=osz_value.strip(), reason="iz OSZ-a",
        ))
    elif normalize_lookup_key(sb_value) == normalize_lookup_key(osz_value):
        result.matches.append(f"{column}: '{sb_value}'")
    else:
        result.differences.append(
            f"{column}: SB kaže '{sb_value}', OSZ kaže '{osz_value}'. "
            "SB vrijednost je zadržana."
        )


def _compare_number(result: BackfillResult, column: str | None,
                    sb_text: str | None, osz_text: str | None) -> None:
    if not column or not osz_text:
        return
    osz_value = parse_optional_float(osz_text)
    if osz_value is None:
        return
    sb_value = parse_optional_float(sb_text)
    if sb_value is None:
        result.proposals.append(BackfillProposal(
            column=column, current="", proposed=_number_text(osz_value), reason="iz OSZ-a",
        ))
    elif abs(sb_value - osz_value) < 0.05:
        result.matches.append(f"{column}: {_number_text(sb_value)}")
    else:
        result.differences.append(
            f"{column}: SB kaže {_number_text(sb_value)}, OSZ kaže "
            f"{_number_text(osz_value)}. SB vrijednost je zadržana."
        )


# ── helpers ──────────────────────────────────────────────────────────
def _column(settings: Settings, key: str, fallback: str) -> str:
    return settings.sb_field_columns.get(key, fallback)


def _sb_text(cave: CaveRow, column: str | None, *, cave_row: bool = True) -> str | None:
    if not column:
        return None
    return SBReader._cell_as_text(cave.values, column) or None


def _split_names_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [part.strip() for part in re.split(r"[;,]", raw) if part.strip()]


def _add_unique(items: list[str], candidate: str) -> None:
    if candidate and normalize_lookup_key(candidate) not in {
        normalize_lookup_key(existing) for existing in items
    }:
        items.append(candidate)


def _number_text(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return f"{value:g}".replace(".", ",")
