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
from cave_dossier.core.people import society_shorthand, split_authors
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

# `cavedossier nacrt` reuses this prefill to get the title-block PAGE, not a
# delivered sastavnica, so it passes local_only=True — and then drops this one
# note, which would otherwise read like a flag the operator had set.
LOCAL_SKIP_NOTE = "--local: isporuka na Drive preskočena."


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
                local_only: bool = False, force: bool = False,
                use_dimensions: bool = False) -> SastavnicaOutcome:
    """``use_dimensions`` switches on the **cSurvey route's** extra source: the
    ``<name>_dimenzije.json`` KORAK 3 leaves in the leaf, which knows the three
    lengths and the printed Mjerilo exactly. Only ``cavedossier nacrt`` sets it;
    plain ``cavedossier sastavnica`` serves the Illustrator route and keeps the
    ``1:`` stub of decision 3 (docs/sastavnica-design.md).
    """
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
    dims = _read_dimensions(intake_folder, result) if use_dimensions else None

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
                    finding, kota_finding, dims=dims,
                    font_path=font.path)

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
        result.notes.append(LOCAL_SKIP_NOTE)
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
                    y_htrs: float | None, finding, kota_finding,
                    dims: dict | None = None,
                    font_path: Path | None = None) -> None:
    fields = result.fields
    # The cSurvey route's own numbers, when `cavedossier nacrt` asked for them:
    # measured off the very survey that is being composed onto this page, so
    # they outrank both the zapisnik and SB for the three dimension cells and
    # they are the only source that knows the printed Mjerilo.
    measured = _dimension_values(dims, font_path) if dims else {}

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
    if measured.get("mjerilo"):
        fields["mjerilo"] = FieldValue(value=measured["mjerilo"], source="nacrt")

    _set_first(fields, "stvarna_duljina", [
        (measured.get("stvarna_duljina"), "nacrt"),
        (_metres(osz.get("duljina")), "osz"),
        (_metres(_sb_text(cave, _field_column(settings, "length_m"))), "sb"),
    ])
    _set_first(fields, "tlocrtna_duljina", [
        (measured.get("tlocrtna_duljina"), "nacrt"),
        (_metres(osz.get("horizontalna_duljina")), "osz"),
    ])
    _set_first(fields, "dubina", [
        (measured.get("dubina"), "nacrt"),
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
        (_societies(_join(osz.get("istrazile_udruge"),
                          osz.get("istrazile_udruge_2"))), "osz"),
        (_societies(settings.sastavnica_society), "default"),
    ])
    _set_first(fields, "datum", [
        (osz.get("datum_istrazivanja"), "osz"),
        (_sb_text(cave, settings.sb_exploration_period_column), "sb"),
    ])

    # Nothing is delivered empty: a cell with no value gets a stub, so the
    # person finishing the document types over a text box instead of creating
    # one (user, 2026-09-20). See addresses.STUB_UNKNOWN.
    missing = []
    for key in addresses.V1:
        if fields.get(key) and fields[key].value:
            continue
        missing.append(addresses.V1[key].label)
        fields[key] = FieldValue(value=addresses.stub_for(key), source="stub")
    if missing:
        # Route-aware wording: on the cSurvey route the delivered page is a
        # finished nacrt, not an Illustrator asset, so "fill it in in
        # Illustrator" would be an instruction the operator cannot follow.
        where = "dopuni prije predaje" if measured else "popuni u Illustratoru"
        result.notes.append(f"Bez podatka ({where}): " + ", ".join(missing))


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


# ── the cSurvey route's measured numbers ─────────────────────────────
def _read_dimensions(folder: Path | None, result: SastavnicaResult) -> dict | None:
    """``<name>_dimenzije.json`` from the leaf, or None.

    Fail-soft like everything else here: a cave that has not been through
    KORAK 3 simply falls back to the zapisnik and SB, with a note.
    """
    from cave_dossier.sastavnica import compose as compose_mod

    if folder is None:
        return None
    found = sorted(folder.glob("*_dimenzije.json"),
                   key=lambda path: path.stat().st_mtime, reverse=True)
    if not found:
        result.notes.append(
            f"U mapi {folder.name} nema <ime>_dimenzije.json — duljine i "
            "mjerilo dolaze iz zapisnika/SB-a, ne iz izmjere."
        )
        return None
    try:
        data = compose_mod.read_dimensions(found[0])
    except compose_mod.ComposeError as exc:
        result.notes.append(f"{exc} — duljine i mjerilo iz zapisnika/SB-a.")
        return None
    result.dimensions_source = found[0].name
    if not data.get("calculated"):
        result.notes.append(
            f"{found[0].name} kaže da survey nije izracunat — provjeri duljine."
        )
    return data


# Below this the combined Dubina form (-9/+1 m) is dropped for the depth alone.
# The cell is 43 pt wide and shrink-to-fit floors at 6 pt, so without a bar like
# this a four-digit cave would print its two numbers at the floor size where the
# depth alone would have sat at the authored 10 pt — smaller AND less legible
# for the sake of a number the cell is not named after.
MIN_COMBINED_SIZE = 7.0


def _measuring_font(font_path: Path | None):
    """A PyMuPDF font for width measurement, or None when it cannot be had.

    Only ``_drop`` needs one — the combined Dubina form is used *if it fits*,
    and fitting can only be decided by measuring. Without a font the combined
    form is used unconditionally; the renderer's own fit-and-shrink then keeps
    it legible either way.
    """
    if font_path is None:
        return None
    try:
        import pymupdf

        return pymupdf.Font(fontfile=str(font_path))
    except Exception:  # noqa: BLE001 - measurement is a nicety, never a blocker
        return None


def _dimension_values(dims: dict, font_path: Path | None) -> dict[str, str]:
    """The four title-block cells the dimensions JSON can answer.

    ``l``/``pl``/``nvr``/``pvr`` are whole metres straight out of cSurvey's
    per-cave speleometrics; ``mjerilo`` is the scale the two designs were
    actually printed at, which is why it supersedes decision 3's ``1:`` stub
    on this route.
    """
    out: dict[str, str] = {}
    length = _metres(_dim_number(dims.get("l")))
    if length:
        out["stvarna_duljina"] = length
    plan_length = _metres(_dim_number(dims.get("pl")))
    if plan_length:
        out["tlocrtna_duljina"] = plan_length
    # The finisher's own height and depth win where it measured them: they are
    # bounded by the boundary wall and the shots, where cSurvey's pvr/nvr take
    # the profile design's whole bounding box and so count a symbol drawn above
    # the entrance as cave (user, 2026-09-20; SB 1103's entrance sign made a
    # cave that does not rise above its entrance report pvr = 1 m).
    nvr = dims["nvr_m"] if dims.get("nvr_m") is not None else dims.get("nvr")
    pvr = dims["pvr_m"] if dims.get("pvr_m") is not None else dims.get("pvr")
    drop = _drop(nvr, pvr, _measuring_font(font_path))
    if drop:
        out["dubina"] = drop
    mjerilo = (dims.get("mjerilo") or "").strip()
    if mjerilo:
        out["mjerilo"] = mjerilo
    return out


def _dim_number(value) -> str | None:
    """A JSON number as the text the length formatters expect."""
    if value is None:
        return None
    return _number(float(value))


def _drop(nvr, pvr, font) -> str | None:
    """Dubina from the speleometrics: ``-9 m``, or ``-9/+1 m`` when it fits.

    A cave with a chimney above its entrance has both numbers, and the drafter's
    own form shows them together — but the cell is 43 pt wide, so the combined
    form is only used when it still fits above the floor size. Otherwise the
    depth alone is printed, which is what the cell is called after.
    """
    # Whole metres, like the kota: the finisher measures to the centimetre and
    # sub-metre precision is noise on a printed nacrt.
    down = round(abs(float(nvr))) if nvr not in (None, "") else 0
    up = round(abs(float(pvr))) if pvr not in (None, "") else 0
    if not down and not up:
        return None
    if not down:
        return f"+{_number(up)} m"          # a cave that only goes up
    plain = f"{_number(-down)} m"
    if not up:
        return plain
    combined = f"{_number(-down)}/+{_number(up)} m"
    if font is None:
        return combined
    size, _width, overflowed = render_mod.fit_size(
        font, combined, addresses.V1["dubina"])
    return plain if overflowed or size < MIN_COMBINED_SIZE else combined


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
             intake_folder: Path | None, force: bool,
             stamp: str = STAMP) -> Path | None:
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

        if target.exists() and not force and not _is_ours(target, stamp):
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


def _is_ours(path: Path, stamp: str = STAMP) -> bool:
    """Does this PDF still carry our stamp? An Illustrator re-save does not.

    ``stamp`` is a parameter because `cavedossier nacrt` delivers a different
    document under a different name with its own stamp, and the two must not
    recognise each other's output as replaceable.
    """
    try:
        import pymupdf

        with pymupdf.open(path) as doc:
            meta = doc.metadata or {}
    except Exception:  # noqa: BLE001 — unreadable means "not provably ours"
        return False
    return stamp in f"{meta.get('creator', '')} {meta.get('producer', '')}"


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


def _societies(raw: str | None) -> str | None:
    """The Istražili cell: one society written out, several abbreviated.

    The cell is 55 pt wide and holds ``SU Estavela`` comfortably; a second
    society written out does not fit at any readable size, and the abbreviation
    (``SUE``, ``SOV``) is the form a caver writes anyway (user, 2026-09-20).
    Abbreviating a lone society would only make the common case harder to read,
    so the short form is used **only when two or more** entries are recognisable
    societies. Anything the rule does not recognise is left exactly as written —
    including the ``, <Grad>`` tail of a canonical name, which is why a single
    canonical does not trip the count.
    """
    if not raw:
        return None
    parts = [part.strip() for part in raw.split(",") if part.strip()]
    shorthands = [society_shorthand(part) for part in parts]
    if sum(1 for short in shorthands if short) < 2:
        return raw
    return ", ".join(short or part for short, part in zip(shorthands, parts))


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
