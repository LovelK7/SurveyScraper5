"""Part 2.1e orchestrator: SB row → prefilled sastavnica PDF.

``cavedossier sastavnica <Redni broj>``:

1. resolve the SB row (the Redni broj is the only input, as everywhere else);
2. find the cave's intake leaf and, in it, the FILLED OSZ — five of the
   fifteen cells are survey facts SB does not carry (tlocrtna duljina,
   mjerili, ekipa, the real datum), and the OSZ is where they live;
3. run the locality + elevation finders for Lokacija and Nadmorska visina
   (both fail-soft, both SB-wins);
4. render the values onto the blank template (``render.py``);
5. deliver ``SB_<padded>_sastavnica.pdf`` into that same leaf, beside the
   OSZ, and keep run artifacts under ``runs/sastavnica/<padded>/``.

Precedence per field: **SB wins** for identity and location, the **OSZ wins**
for survey facts (SB's author cell holds the *source* for queued caves, not the
drafter). A finder value SB lacks never gets written — it leaves as a
``dopune-sb.csv`` row a person pastes, the same route as `osz prefill`.

Two cells are never data-driven (user, 2026-09-19): Katastarski broj keeps the
template's ``0000`` because the archivist assigns the number last and edits the
PDF by hand, and Mjerilo keeps ``1:`` because the drafter picks the scale while
drawing. See ``addresses.CONSTANTS``.
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from cave_dossier import georef
from cave_dossier.core.config import Settings
from cave_dossier.core.paths import workspace
from cave_dossier.core.normalization import parse_optional_float
from cave_dossier.core.people import split_authors
from cave_dossier.core.person_aliases import to_sb_shorthand
from cave_dossier.geo import elevation as elevation_mod
from cave_dossier.geo import locality as locality_mod
from cave_dossier.intake.scanner import find_cave_leaf
from cave_dossier.osz.prefill import intake_folder_name, write_sb_updates
from cave_dossier.sastavnica import addresses, fonts, render as render_mod
from cave_dossier.sastavnica.models import (
    FieldValue,
    PlacedField,
    SastavnicaResult,
    SBUpdate,
)
from cave_dossier.sb.loader import CaveRow, SBReader

RUNS_DIR = workspace("runs", "sastavnica")

# Stamped into the delivered PDF's metadata so a re-run can tell ITS OWN output
# apart from a file somebody else put under the same name — including our own
# output after a drafter edited and re-saved it in Illustrator, which replaces
# the producer. That is what makes "refuse on collision" (user, 2026-09-19)
# safe to apply without also refusing every ordinary re-run.
STAMP = "cave-dossier sastavnica prefill"


class SastavnicaError(RuntimeError):
    """Hard failure — no document produced; message is CLI-ready."""


@dataclass(frozen=True)
class SastavnicaOutcome:
    result: SastavnicaResult
    pdf_path: Path                # the run-dir copy (always exists on success)
    delivered_path: Path | None   # the Drive copy, when it could be written
    sidecar_path: Path
    sb_updates_path: Path | None


def run_prefill(settings: Settings, serial: int, *, offline: bool = False,
                local_only: bool = False, force: bool = False) -> SastavnicaOutcome:
    reader = SBReader(settings)
    cave = georef.find_by_serial(reader, settings, serial)
    if cave is None:
        raise SastavnicaError(f"No SB row carries Redni broj {serial}.")

    result = SastavnicaResult(
        serial=serial,
        cave_name=cave.object_name or "",
        sue_number=cave.sue_number or None,
        template_version=addresses.TEMPLATE_VERSION,
    )

    try:
        font = fonts.resolve(settings.sastavnica_font_path)
    except fonts.FontUnavailable as exc:
        raise SastavnicaError(str(exc)) from exc
    result.font, result.font_tier = font.path.name, font.tier
    if font.note:
        result.notes.append(font.note)

    intake_folder = _intake_folder(settings, serial)
    osz_values = _read_osz(intake_folder, result)

    x_htrs = _sb_float(cave, settings.sb_x_htrs_column)
    y_htrs = _sb_float(cave, settings.sb_y_htrs_column)
    finding = kota_finding = None
    if x_htrs is not None and y_htrs is not None:
        finding = locality_mod.build_finder(settings, offline=offline).locate(
            x_htrs, y_htrs,
            sb_lokalitet=_sb_text(cave, _field_column(settings, "locality")),
            sb_najblize_mjesto=_sb_text(cave, _field_column(settings, "nearest_place")),
        )
        kota_finding = elevation_mod.build_finder(settings, offline=offline).kota(
            x_htrs, y_htrs
        )
    else:
        result.notes.append(
            "SB red nema upotrebljive X/Y HTRS koordinate — koordinate, "
            "nadmorska visina i lokacija preskočene."
        )

    _resolve_fields(settings, cave, result, osz_values, x_htrs, y_htrs,
                    finding, kota_finding)

    values = {key: fv.value for key, fv in result.fields.items() if fv.value}
    try:
        pdf_bytes, placed = render_mod.render(
            addresses.BLANK_TEMPLATE, values, font.path,
            metadata={"title": f"Sastavnica {_sb_prefix(serial)}",
                      "subject": result.cave_name,
                      "creator": STAMP,
                      "producer": f"{STAMP} ({addresses.TEMPLATE_VERSION})"},
        )
    except render_mod.RenderError as exc:
        raise SastavnicaError(str(exc)) from exc

    result.placed = [
        PlacedField(key=p.key, text=p.text, font_size=p.font_size,
                    width_pt=round(p.width, 2), overflowed=p.overflowed)
        for p in placed
    ]
    for item in result.placed:
        if item.overflowed:
            result.notes.append(
                f"'{addresses.V1[item.key].label}' ne stane u ćeliju ni na "
                f"{addresses.MIN_FONT_SIZE:g} pt — skrati tekst u Illustratoru."
            )

    run_dir = RUNS_DIR / georef.padded_serial(serial)
    run_dir.mkdir(parents=True, exist_ok=True)
    pdf_name = f"{_sb_prefix(serial)}_sastavnica.pdf"
    pdf_path = run_dir / pdf_name
    pdf_path.write_bytes(pdf_bytes)

    delivered_path = None
    if local_only:
        result.notes.append("--local: isporuka na Drive preskočena.")
    else:
        delivered_path = _deliver(settings, cave, serial, pdf_path, pdf_name,
                                  result, intake_folder=intake_folder, force=force)

    sidecar_path = run_dir / "sastavnica.json"
    sidecar_path.write_text(result.model_dump_json(indent=2), encoding="utf-8")

    sb_updates_path = None
    if result.sb_updates:
        sb_updates_path = run_dir / "dopune-sb.csv"
        write_sb_updates(sb_updates_path, serial, result.sb_updates)

    return SastavnicaOutcome(result, pdf_path, delivered_path, sidecar_path,
                             sb_updates_path)


# ── field resolution ─────────────────────────────────────────────────
def _resolve_fields(settings: Settings, cave: CaveRow, result: SastavnicaResult,
                    osz: dict[str, str | None], x_htrs: float | None,
                    y_htrs: float | None, finding, kota_finding) -> None:
    fields = result.fields

    for key, text in addresses.CONSTANTS.items():
        fields[key] = FieldValue(value=text, source="constant")

    if cave.object_name:
        fields["ime_objekta"] = FieldValue(value=cave.object_name, source="sb")
    plaque = _sb_text(cave, settings.sb_plaque_column)
    if plaque:
        fields["broj_plocice"] = FieldValue(value=plaque, source="sb")

    # Integer metres, X then Y — the form the authored template uses.
    if x_htrs is not None and y_htrs is not None:
        fields["htrs"] = FieldValue(
            value=f"{int(round(x_htrs))} {int(round(y_htrs))}", source="sb"
        )

    _resolve_kota(settings, cave, result, kota_finding)
    _resolve_lokacija(settings, cave, result, finding)

    # Survey facts: the OSZ wins. SB's "Autori nacrta ili izvor" holds the
    # SOURCE for a queued cave (often a literature citation), not the drafter,
    # so it is only the fallback.
    _set_first(fields, "stvarna_duljina", [
        (_metres(osz.get("duljina")), "osz"),
        (_metres(_sb_text(cave, _field_column(settings, "length_m"))), "sb"),
    ])
    _set_first(fields, "tlocrtna_duljina", [
        (_metres(osz.get("horizontalna_duljina")), "osz"),
    ])
    _set_first(fields, "dubina", [
        (_metres(osz.get("visinska_razlika")), "osz"),
        (_depth(osz.get("dubina")), "osz"),
        (_depth(_sb_text(cave, _field_column(settings, "depth_m"))), "sb"),
    ])
    _set_first(fields, "crtali", [
        (_people(osz.get("crtali")), "osz"),
        (_people(_sb_text(cave, settings.sb_drawing_authors_column)), "sb"),
    ])
    _set_first(fields, "mjerili", [
        (_people(_join(osz.get("mjerili"), osz.get("mjerili_2"))), "osz"),
    ])
    _set_first(fields, "ekipa", [
        (_people(_join(osz.get("clanovi_ekipe"), osz.get("clanovi_ekipe_2"),
                       osz.get("clanovi_ekipe_3"))), "osz"),
    ])
    # Istražili: whatever the OSZ names, else this society (user, 2026-09-19).
    _set_first(fields, "istrazili", [
        (_join(osz.get("istrazile_udruge"), osz.get("istrazile_udruge_2")), "osz"),
        (settings.sastavnica_society, "default"),
    ])
    _set_first(fields, "datum", [
        (osz.get("datum_istrazivanja"), "osz"),
        (_sb_text(cave, settings.sb_exploration_period_column), "sb"),
    ])

    missing = [addresses.V1[key].label for key in addresses.V1
               if not (fields.get(key) and fields[key].value)]
    if missing:
        result.notes.append(
            "Prazno (popuni u Illustratoru): " + ", ".join(missing)
        )


def _resolve_kota(settings: Settings, cave: CaveRow, result: SastavnicaResult,
                  kota_finding) -> None:
    """SB wins; the DMV grid only fills an empty cell, and a disagreement is
    a note — the same rule as `osz prefill`, so the two documents can never
    disagree about the same cave."""
    # Whole metres: SB's Z carries the grid's decimals (1285,92) and sub-metre
    # precision is noise on a printed nacrt — the authored template shows a
    # bare "1033 m".
    sb_z = _sb_float(cave, _field_column(settings, "entrance_elevation_m"))
    computed = kota_finding.elevation_m if kota_finding is not None else None
    label = settings.geo_elevation_source_label

    if sb_z is not None:
        result.fields["nadmorska_visina"] = FieldValue(
            value=f"{_number(round(sb_z))} m", source="sb"
        )
        if computed is not None and abs(computed - sb_z) > settings.geo_elevation_tolerance_m:
            result.notes.append(
                f"Nadmorska visina: SB kaže {_number(sb_z)} m, {label} kaže "
                f"{_number(computed)} m — zadržana SB vrijednost."
            )
        return
    if computed is not None:
        result.fields["nadmorska_visina"] = FieldValue(
            value=f"{_number(round(computed))} m", source="dmv-dgu"
        )
        result.sb_updates.append(SBUpdate(
            column=_field_column(settings, "entrance_elevation_m") or "Z",
            value=_number(computed),
            source=label,
            note=kota_finding.tile_name or "",
        ))


def _resolve_lokacija(settings: Settings, cave: CaveRow, result: SastavnicaResult,
                      finding) -> None:
    """``Lokalitet, Najbliže mjesto`` — just those two (user, 2026-09-19):
    the cell is narrow, and those are the two the society actually records.

    The locality finder already applies SB-wins internally, so its result is
    preferred; without coordinates (or offline with no data) the SB cells are
    read directly. Anything the finder produced that SB lacks leaves as a
    review row, never a write."""
    if finding is not None:
        result.notes.extend(finding.notes)
        lokalitet, najblize = finding.lokalitet, finding.najblize_mjesto
        if finding.lokalitet_source == "geo-rgi" and lokalitet:
            result.sb_updates.append(SBUpdate(
                column=_field_column(settings, "locality") or "Lokalitet",
                value=lokalitet,
                source="RGI (najbliži toponim)",
            ))
        if finding.najblize_mjesto_source == "geo-admin" and najblize:
            sb_current = _sb_text(cave, _field_column(settings, "nearest_place"))
            if not sb_current:
                result.sb_updates.append(SBUpdate(
                    column=_field_column(settings, "nearest_place") or "Najbliže mjesto",
                    value=najblize,
                    source="DGU naselja (točka ulaza)",
                ))
        source = finding.lokalitet_source or finding.najblize_mjesto_source or "geo"
    else:
        lokalitet = _sb_text(cave, _field_column(settings, "locality"))
        najblize = _sb_text(cave, _field_column(settings, "nearest_place"))
        source = "sb"

    text = ", ".join(part for part in (lokalitet, najblize) if part)
    if text:
        result.fields["lokacija"] = FieldValue(value=text, source=source)


# ── the filled OSZ in the cave's leaf ────────────────────────────────
def _read_osz(folder: Path | None, result: SastavnicaResult) -> dict[str, str | None]:
    """Every v10 cell of the leaf's filled zapisnik, or {} when there is none.

    Fail-soft by design: without an OSZ the five survey cells simply stay
    blank and the note says so — the sastavnica is still worth generating
    before the zapisnik exists.
    """
    if folder is None:
        result.notes.append(
            "Objekt još nema intake mapu — podaci iz zapisnika (mjerili, ekipa, "
            "duljine, datum) nisu dostupni."
        )
        return {}
    try:
        from cave_dossier.osz.backfill import pick_osz_docx
        from cave_dossier.osz.reader import read_osz
    except ImportError:
        result.notes.append(
            "OSZ čitač nije dostupan na ovom računalu (nedostaje [osz] dodatak) — "
            "podaci iz zapisnika preskočeni."
        )
        return {}

    path, pool = pick_osz_docx(folder)
    if pool:
        result.notes.append(
            "Više OSZ kandidata u intake mapi — zapisnik preskočen: "
            + ", ".join(f.name for f in pool)
        )
        return {}
    if path is None:
        result.notes.append(
            f"U mapi {folder.name} nema OSZ zapisnika — mjerili, ekipa, duljine "
            "i datum ostaju prazni."
        )
        return {}
    try:
        values = read_osz(path)
    except Exception as exc:  # noqa: BLE001 — an unreadable OSZ must not kill the run
        result.notes.append(f"OSZ {path.name} nije pročitan ({exc}) — preskočen.")
        return {}
    result.osz_source = path.name
    return {key: (value.strip() if isinstance(value, str) else value)
            for key, value in values.items()}


# ── delivery ─────────────────────────────────────────────────────────
def _deliver(settings: Settings, cave: CaveRow, serial: int, pdf_path: Path,
             pdf_name: str, result: SastavnicaResult, *,
             intake_folder: Path | None, force: bool) -> Path | None:
    """Copy into the cave's intake leaf, beside its OSZ.

    Collision rule (user, 2026-09-19): a drafter names their own PDF
    differently, so a file already sitting under OUR name is almost certainly
    ours — unless it has been edited, which strips our metadata stamp. An
    unstamped file is therefore REFUSED with a warning rather than
    overwritten; `--force` is the way past it. Everything else is fail-soft:
    the run-dir copy is always the fallback.
    """
    subdir = settings.archive_dirs.get("intake_dir")
    if not settings.local_drive_root or not subdir:
        result.notes.append(
            "Nije konfiguriran archive.intake_dir / LOCAL_DRIVE_ROOT — "
            "dokument je ostao samo lokalno."
        )
        return None
    intake_root = settings.local_drive_root / subdir
    try:
        if not intake_root.is_dir():
            result.notes.append(
                f"Intake mapa nije dostupna ({intake_root}) — dokument je ostao lokalno."
            )
            return None
        folder = intake_folder or find_cave_leaf(intake_root, serial)
        if folder is None:
            folder = intake_root / intake_folder_name(cave, serial, settings)
            folder.mkdir(parents=True, exist_ok=True)
            result.notes.append(f"Stvorena intake mapa: {folder.name}")
        target = folder / pdf_name

        if target.exists() and not force and not _is_ours(target):
            result.notes.append(
                f"{target.name} već postoji i NIJE ga napravio ovaj alat "
                "(vjerojatno ga je netko uredio) — isporuka odbijena da se rad ne "
                "prepiše. Preimenuj ili makni tu datoteku, ili pokreni s --force."
            )
            return None

        shutil.copy2(pdf_path, target)
    except OSError as exc:
        result.notes.append(
            f"Isporuka na Drive nije uspjela ({exc.__class__.__name__}: {exc}) — "
            f"dokument je ostao lokalno; zatvori {pdf_name} i ponovi."
        )
        return None
    return target


def _is_ours(path: Path) -> bool:
    """Does this PDF still carry our stamp? An Illustrator re-save does not."""
    try:
        import pymupdf

        with pymupdf.open(path) as doc:
            meta = doc.metadata or {}
    except Exception:  # noqa: BLE001 — unreadable means "not provably ours"
        return False
    return STAMP in f"{meta.get('creator', '')} {meta.get('producer', '')}"


def _intake_folder(settings: Settings, serial: int) -> Path | None:
    subdir = settings.archive_dirs.get("intake_dir")
    if not settings.local_drive_root or not subdir:
        return None
    intake_root = settings.local_drive_root / subdir
    if not intake_root.is_dir():
        return None
    return find_cave_leaf(intake_root, serial)


# ── small helpers ────────────────────────────────────────────────────
def _set_first(fields: dict[str, FieldValue], key: str,
               candidates: list[tuple[str | None, str]]) -> None:
    """First non-empty candidate wins; the pair's second item is its source."""
    for value, source in candidates:
        if value:
            fields[key] = FieldValue(value=value, source=source)
            return


def _join(*parts: str | None) -> str | None:
    """Continuation cells ("Mjerili" + "Mjerili 2") read as one list."""
    seen: list[str] = []
    for part in parts:
        text = (part or "").strip().strip(",;")
        if text and text not in seen:
            seen.append(text)
    return ", ".join(seen) or None


def _number(value: float) -> str:
    """Croatian rendering: integers bare, decimals with a comma."""
    if float(value).is_integer():
        return str(int(value))
    return f"{value:g}".replace(".", ",")


def _metres(raw: str | None) -> str | None:
    """A length cell as ``<n> m``; a value that already carries a unit or any
    non-numeric text is passed through untouched.

    A **zero** reads as "not surveyed yet", which is what SB and an untouched
    zapisnik both mean by it — and "0 m" printed on a nacrt is worse than an
    empty box the drafter fills in.
    """
    if not raw:
        return None
    text = str(raw).strip()
    number = _strict_float(text)
    if number is None:
        return text
    if number == 0:
        return None
    return f"{_number(number)} m"


def _depth(raw: str | None) -> str | None:
    """A DEPTH cell as ``-<n> m``.

    *Dubina* is measured downward by definition, and the authored template
    shows it signed (``-60 m``) — so a bare positive number gets the sign. A
    value that is already signed, or that is not a plain number, is left
    exactly as written; a zero is "not surveyed yet", as in ``_metres``.
    """
    if not raw:
        return None
    text = str(raw).strip()
    number = _strict_float(text)
    if number is None:
        return text
    if number == 0:
        return None
    if number > 0 and not text.startswith(("+", "-")):
        number = -number
    return f"{_number(number)} m"


def _strict_float(text: str) -> float | None:
    """The cell as a number only when it is NOTHING BUT a number.

    Deliberately stricter than ``parse_optional_float``, which digs a number
    out of any text: a recorder's "oko 20" is a hedge, and printing it as a
    flat "20 m" on a nacrt would turn an estimate into a measurement.
    """
    try:
        return float(text.replace(",", ".").rstrip("."))
    except ValueError:
        return None


# "F.Karabaić" -> "F. Karabaić": the template's own spacing.
_SHORTHAND_SPACING = re.compile(r"(?<=\.)(?=[^\W\d_])", re.UNICODE)


def _people(raw: str | None) -> str | None:
    """An author cell in the drafter's own form: ``D. Maršanić, M. Vrkić``.

    The sastavnica is a printed map and the authored template abbreviates
    every people cell. Shortening here is not cosmetic — it is what keeps
    three names at 10 pt instead of shrinking them to 6 pt to fit. A name that
    is not a plain "First Last" passes through unchanged (``to_sb_shorthand``
    is an honest passthrough), and an outside-society bracket survives: the
    nacrt credit is exactly where that matters.
    """
    names, societies = split_authors(raw)
    out: list[str] = []
    for name in names:
        short = _SHORTHAND_SPACING.sub(" ", to_sb_shorthand(name))
        society = societies.get(name)
        out.append(f"{short} ({society})" if society else short)
    return ", ".join(out) or None


def _field_column(settings: Settings, key: str) -> str | None:
    return settings.sb_field_columns.get(key)


def _sb_text(cave: CaveRow, column: str | None) -> str | None:
    if not column:
        return None
    return SBReader._cell_as_text(cave.values, column) or None


def _sb_float(cave: CaveRow, column: str | None) -> float | None:
    return parse_optional_float(_sb_text(cave, column))


def _sb_prefix(serial: int) -> str:
    from cave_dossier.core.matching import SB_PREFIX

    return f"{SB_PREFIX}{georef.padded_serial(serial)}"
