"""Which obligatory OSZ fields are still empty — ``cavedossier osz provjera <broj>``.

Read-only. The point (user, 2026-10-04) is to know **before 3N** what the
zapisnik still lacks: 3N KORAK 3c composes the nacrt's title block from the
OSZ, and a missing *Nacrt uredio* only surfaced there, as a ``?`` on the
printed page, when it could have been typed into the zapisnik long before.

Every requirement says who needs it:

- ``3N`` — the sastavnica (KORAK 3c / 4S) reads it from the zapisnik and has
  no other source, so an empty cell prints as ``?``;
- ``SUE`` — gate 1 of 5D (the katastarski broj): Tablica 2 ``*`` fields that
  come from the OSZ (``dossier/gating.py`` is the authority, this list
  mirrors its OSZ-sourced rules);
- ``CroSpeleo`` — gate 2 only.

Cells the survey answers — Duljina, Horizontalna duljina, Dubina, Visinska
razlika, Broj / Širina / Visina-duljina ulaza — are **not** reported missing:
3N KORAK 4 (``osz backfill``) writes them from ``<ime>_dimenzije.json``. They
are listed apart as "3N upisuje" so the operator does not type them by hand.

Checkbox groups (Vrsta objekta, Podrijetlo imena, the two hydrology groups)
count as filled when any of their options is ticked; labels are compared
diacritic-insensitively so a re-typed template still matches.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path

from cave_dossier.core.normalization import normalize_lookup_key
from cave_dossier.core.people import is_placeholder

#: Who needs a field, in the order the report groups them.
NEEDED_BY_ORDER = ("3N", "SUE", "CroSpeleo")


@dataclass(frozen=True)
class Requirement:
    key: str
    label: str                       # the zapisnik's own Croatian heading
    needed_by: tuple[str, ...]
    cells: tuple[str, ...] = ()      # addresses.V10 keys — any filled satisfies
    group: tuple[str, ...] = ()      # checkbox labels — any ticked satisfies
    filled_by: str | None = None     # "3N" — KORAK 4 writes it, never a gap
    hint: str = ""


_VRSTA = ("jama", "špilja", "jama sa špiljskim ulazom", "špilja s jamskim ulazom",
          "kaverna", "kompleksni objekt", "jamski sustav", "špiljski sustav")
_PODRIJETLO = ("smišljeno novo", "smišljeno prema toponimu", "preuzeto iz literature",
               "preuzeto kao lokalni naziv", "preuzeto sa karte", "nepoznato podrijetlo")
_HIDROLOSKA = ("suh", "nakapnica/prokapnica", "povremena stajaća voda",
               "stalna stajaća voda", "povremeni tok", "stalni tok",
               "povremeno potopljen", "potopljen")
_HIDROGEOLOSKA = ("nema", "povremeni ponor", "stalni ponor", "povremeni izvor",
                  "stalni izvor", "estavela", "protočan objekt", "vrulja",
                  "anhijalini objekt", "morski objekt")
_PERSPEKTIVA = ("potpuno istražen", "potrebno proširivanje", "nastavlja se spuštanjem",
                "nastavlja se penjanjem", "nastavlja se prečkanjem",
                "nastavlja se provlačenjem", "nastavlja se",
                "nastavlja se preko vodenog tijela", "potrebno ronjenje", "nije poznato",
                "moguć nastavak u slučaju topljenja ledenog čepa",
                "potrebno ukloniti prepreke (eksplozivne naprave, otpad, strvine, kamenja...)")

# The 3N fields first: they are the ones this check exists for. Crtali and
# Datum have an SB fallback in the sastavnica, but SB holds the SOURCE for a
# queued cave, not the trip — the zapisnik is where they belong.
REQUIREMENTS: tuple[Requirement, ...] = (
    Requirement("nacrt_uredio", "Nacrt uredio", ("3N",), cells=("nacrt_uredio",),
                hint="tko je nacrt doradio"),
    Requirement("crtali", "Crtali", ("3N",), cells=("crtali",)),
    Requirement("mjerili", "Mjerili", ("3N",), cells=("mjerili", "mjerili_2")),
    Requirement("clanovi_ekipe", "Članovi ekipe", ("3N", "SUE"),
                cells=("clanovi_ekipe", "clanovi_ekipe_2", "clanovi_ekipe_3")),
    Requirement("datum_istrazivanja", "Datum ili razdoblje istraživanja", ("3N",),
                cells=("datum_istrazivanja",)),
    Requirement("istrazile_udruge", "Istražile udruge", ("CroSpeleo",),
                cells=("istrazile_udruge", "istrazile_udruge_2"),
                hint="sastavnica bez njega upisuje zadanu udrugu"),
    Requirement("ime_objekta", "Ime objekta", ("SUE",), cells=("ime_objekta",),
                hint="dolazi iz SB-a – pokreni osz prefill"),
    Requirement("koordinate", "Koordinate ulaza (HTRS96/TM)", ("SUE",),
                cells=("x_htrs",), hint="dolazi iz SB-a – pokreni osz prefill"),
    Requirement("izvor_koordinata", "Izvor koordinata", ("CroSpeleo",),
                cells=("izvor_koordinata",)),
    Requirement("podrijetlo_imena", "Podrijetlo imena", ("SUE",), group=_PODRIJETLO),
    Requirement("polozaj_pristup", "Položaj i pristup objektu", ("SUE",),
                cells=("polozaj_pristup",)),
    Requirement("vrsta_objekta", "Vrsta objekta", ("SUE",), group=_VRSTA),
    Requirement("hidroloska", "Hidrološka karakteristika", ("SUE",), group=_HIDROLOSKA),
    Requirement("hidrogeoloska", "Hidrogeološka funkcija", ("SUE",), group=_HIDROGEOLOSKA),
    Requirement("opis", "Osnovni opis s tehničkim podacima", ("SUE",), cells=("opis",)),
    Requirement("perspektiva", "Perspektiva daljnjeg istraživanja", ("SUE",),
                cells=("perspektiva",), group=_PERSPEKTIVA),
    Requirement("zapisnicar", "Zapisničar", ("SUE",), cells=("zapisnicar",)),
    # Answered by the survey — 3N KORAK 4 writes them.
    Requirement("duljina", "Duljina", ("SUE",), cells=("duljina",), filled_by="3N"),
    Requirement("horizontalna_duljina", "Horizontalna duljina", ("SUE",),
                cells=("horizontalna_duljina",), filled_by="3N"),
    Requirement("dubina", "Dubina", ("SUE",), cells=("dubina",), filled_by="3N"),
    Requirement("visinska_razlika", "Visinska razlika", ("CroSpeleo",),
                cells=("visinska_razlika",), filled_by="3N"),
    Requirement("sirina_ulaza", "Širina ulaza", ("SUE",), cells=("sirina_ulaza",),
                filled_by="3N"),
    Requirement("visina_duljina_ulaza", "Visina/duljina ulaza", ("SUE",),
                cells=("visina_duljina_ulaza",), filled_by="3N"),
)


@dataclass(frozen=True)
class Gap:
    key: str
    label: str
    needed_by: tuple[str, ...]
    hint: str = ""


@dataclass
class OszCheck:
    #: obligatory and empty — the operator's to fill
    missing: list[Gap] = field(default_factory=list)
    #: empty, but 3N KORAK 4 writes it from the survey
    deferred: list[Gap] = field(default_factory=list)
    filled: int = 0
    total: int = 0
    osz: str | None = None
    notes: list[str] = field(default_factory=list)

    @property
    def missing_for_3n(self) -> list[Gap]:
        return [g for g in self.missing if "3N" in g.needed_by]

    def to_json(self) -> dict:
        data = asdict(self)
        data["missing_for_3n"] = [g.label for g in self.missing_for_3n]
        return data


class ProvjeraError(RuntimeError):
    """No zapisnik to check; the message is CLI-ready (Croatian)."""


def _has_text(value: str | None) -> bool:
    return not is_placeholder(value)


def check_content(fields: dict[str, str | None], ticked=()) -> OszCheck:
    """The verdict for already-read cells + ticked checkbox labels (pure)."""
    ticked_keys = {normalize_lookup_key(label) for label in ticked if label}
    result = OszCheck()
    for req in REQUIREMENTS:
        ok = any(_has_text(fields.get(cell)) for cell in req.cells)
        if not ok and req.group:
            ok = any(normalize_lookup_key(label) in ticked_keys for label in req.group)
        if req.filled_by is None:
            result.total += 1
            result.filled += ok
        if ok:
            continue
        gap = Gap(req.key, req.label, req.needed_by, req.hint)
        (result.deferred if req.filled_by else result.missing).append(gap)
    return result


def check_file(path: Path) -> OszCheck:
    """Read a v10 zapisnik and check it; ``OszReadError`` propagates."""
    from cave_dossier.osz.reader import read_osz_content

    content = read_osz_content(path)
    result = check_content(content.fields, content.ticked)
    result.osz = path.name
    return result


def run_check(settings, serial: int) -> tuple[OszCheck, Path]:
    """Find the cave's zapisnik in its intake leaf (as KORAK 4 does) and check it."""
    from cave_dossier.osz import prefill
    from cave_dossier.osz.dopune import pick_osz_docx
    from cave_dossier.osz.reader import OszReadError

    folder = prefill._existing_intake_folder(settings, serial)
    if folder is None:
        raise ProvjeraError(
            f"Objekt {serial} nema mapu pod !Za digitalizirat – prvo `cavedossier osz prefill {serial}`."
        )
    path, pool = pick_osz_docx(folder)
    if path is None:
        raise ProvjeraError(
            f"U mapi {folder.name} nema (jednoznačnog) OSZ-a – prvo `cavedossier osz prefill {serial}`."
        )
    try:
        result = check_file(path)
    except OszReadError as exc:
        raise ProvjeraError(
            f"{path.name} nije v10 zapisnik ({exc}) – `cavedossier osz prefill {serial}` ga migrira."
        ) from exc
    if pool:
        result.notes.append("Više OSZ kandidata u mapi – provjeren " + path.name
                            + " (ostali: " + ", ".join(p.name for p in pool) + ").")
    return result, path


def describe(gap: Gap) -> str:
    """One line for the CLI and the dashboard: label – who needs it (hint)."""
    who = " + ".join(_WHO[n] for n in NEEDED_BY_ORDER if n in gap.needed_by)
    return f"{gap.label} – {who}" + (f" ({gap.hint})" if gap.hint else "")


_WHO = {"3N": "3N sastavnica", "SUE": "katastarski broj", "CroSpeleo": "CroSpeleo"}
