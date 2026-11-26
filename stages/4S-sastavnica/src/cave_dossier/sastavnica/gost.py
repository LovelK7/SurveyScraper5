"""The guest route: 3N for a survey that is not in the Speleo baza.

Everything else on the cSurvey route is keyed by a Redni broj — the file is
picked from the cave's ``SB_<broj>_…`` intake leaf on the Drive, and the title
block is prefilled from the SB row, the filled OSZ and the geo finders. A caver
from another club has none of that: no SB row, no intake leaf, no zapisnik. What
they do have is a TopoDroid export and the dozen facts the title block prints.

So a **guest project** (gost) is a plain local folder holding the survey files
and one ``podaci.json`` with the title-block values typed in by hand:

    <gost root>/<Ime objekta>/
        podaci.json                      the hand-entered cells (this module)
        <name>.csx                       the TopoDroid export, dropped in
        <name>_prep.csx … _postp_resolved.csx, _plan.pdf, _profile.pdf,
        <name>_dimenzije.json            the same 3N KORAK 1–3b tools, by path
        <Ime objekta>_nacrt.pdf          `cavedossier gost nacrt` (here)

The 3N scripts already take a plain file path and never read SB, so KORAK 1–3b
run unchanged. Only KORAK 3c — composing the sheet — needed an SB-free twin of
``nacrt.run_nacrt``, and that is ``run_gost_nacrt``. It reuses the sastavnica's
renderer, formatters and the composer, so a guest nacrt and an archive nacrt
look identical; what differs is only where the cells come from:

    typed in podaci.json  >  measured (dimenzije.json)  >  geo finders  >  stub

The hand entry wins because it is the guest's explicit answer; the measured
numbers fill what was left empty, which is the normal case for the lengths,
the depth and the Mjerilo. Nothing here touches SB, the Drive or the OSZ, and
there is no delivery step: the folder IS the destination (decision record,
2026-11-25).

The root is ``%LOCALAPPDATA%\\CaveDossier\\gost`` — outside the versioned prod
workspace, so an upgrade of the bundle never takes a guest's project with it.
``CAVEDOSSIER_GOST_DIR`` overrides it (tests, or a USB stick).
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

from cave_dossier.core.config import Settings
from cave_dossier.sastavnica import addresses, compose as compose_mod, fonts
from cave_dossier.sastavnica import render as render_mod
from cave_dossier.sastavnica.compose import ComposeError, Layout
from cave_dossier.sastavnica.models import (
    FieldValue,
    NacrtResult,
    PlacedField,
    SastavnicaResult,
)

GOST_DIR_ENV = "CAVEDOSSIER_GOST_DIR"
DATA_FILE = "podaci.json"
SIDECAR = "nacrt.json"
STAMP = "cave-dossier gost nacrt"

#: The society logo cell of template v2, in points: the box the Estavela mark
#: is drawn in (vector art, measured 41.4–80.6 x 42.8–100.6 on the blank). A
#: guest's nacrt must not carry another club's logo, so the art fully inside
#: this box is removed — the cell border only touches it and survives — and
#: the guest's own ``logo.png``/``logo.jpg`` goes in its place when present.
LOGO_BOX = (41.0, 42.4, 81.0, 101.0)
LOGO_NAMES = ("logo.png", "logo.jpg", "logo.jpeg")

#: The cells a guest types, in the order the form shows them. Katastarski broj
#: is editable here (unlike the archive route, decision 2026-09-19) because a
#: guest's cave may already have its national cadastre number.
EDITABLE: tuple[tuple[str, str], ...] = (
    ("ime_objekta", "npr. Jama pod Kukom"),
    ("katastarski_broj", "prazno = 0000"),
    ("broj_plocice", "prazno = /"),
    ("htrs", "X Y u HTRS96/TM, npr. 345678 4987654"),
    ("nadmorska_visina", "npr. 812 – prazno: iz DMV-a prema HTRS-u"),
    ("lokacija", "Najbliže mjesto, Lokalitet – prazno: iz HTRS-a"),
    ("crtali", "Ime Prezime, Ime Prezime"),
    ("mjerili", "Ime Prezime, Ime Prezime"),
    ("ekipa", "ostali članovi ekipe"),
    ("istrazili", "udruga/e"),
    ("nacrt_uredio", "Ime Prezime"),
    ("datum", "npr. 14. 9. 2026."),
    ("stvarna_duljina", "prazno = iz izmjere"),
    ("tlocrtna_duljina", "prazno = iz izmjere"),
    ("dubina", "prazno = iz izmjere"),
    ("mjerilo", "prazno = iz KORAKA 3a"),
)
EDITABLE_KEYS = frozenset(key for key, _hint in EDITABLE)

#: Characters Windows refuses in a folder name.
_BAD_NAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


class GostError(RuntimeError):
    """Hard failure — no document produced; message is operator-ready."""


# ── projects ─────────────────────────────────────────────────────────
def projects_root() -> Path:
    override = os.environ.get(GOST_DIR_ENV)
    if override:
        return Path(override).expanduser()
    base = os.environ.get("LOCALAPPDATA") or str(Path.home())
    return Path(base) / "CaveDossier" / "gost"


def folder_name(name: str) -> str:
    """The cave's name as a Windows-safe folder name (diacritics kept)."""
    clean = _BAD_NAME.sub(" ", name or "").strip().strip(".")
    clean = re.sub(r"\s+", " ", clean)
    return clean[:80].rstrip() or "Novi objekt"


def create_project(name: str, root: Path | None = None) -> Path:
    """A new project folder named after the cave; never reuses an existing one."""
    root = root or projects_root()
    root.mkdir(parents=True, exist_ok=True)
    base = folder_name(name)
    folder, n = root / base, 2
    while folder.exists():
        folder, n = root / f"{base} ({n})", n + 1
    folder.mkdir()
    save_data(folder, {"ime_objekta": (name or "").strip()})
    return folder


def list_projects(root: Path | None = None) -> list[dict]:
    root = root or projects_root()
    if not root.is_dir():
        return []
    out = []
    for folder in root.iterdir():
        if not folder.is_dir():
            continue
        data = load_data(folder)
        stamp = max((p.stat().st_mtime for p in folder.iterdir() if p.is_file()),
                    default=folder.stat().st_mtime)
        out.append({"id": folder.name, "path": str(folder),
                    "name": data.get("ime_objekta") or folder.name,
                    "modified": stamp})
    out.sort(key=lambda p: p["modified"], reverse=True)
    return out


def project_folder(project_id: str, root: Path | None = None) -> Path:
    """The folder of ``project_id``, refusing anything that escapes the root."""
    root = (root or projects_root()).resolve()
    folder = (root / str(project_id)).resolve()
    if folder.parent != root or not folder.is_dir():
        raise GostError(f"Nema gostujućeg projekta „{project_id}”.")
    return folder


def resolve_project(target: str, root: Path | None = None) -> Path:
    """A project id (folder name under the root) or any folder path."""
    path = Path(target).expanduser()
    if path.is_dir():
        return path.resolve()
    return project_folder(target, root)


def load_data(folder: Path) -> dict[str, str]:
    """``podaci.json``, or {} — a missing or hand-broken file is not fatal."""
    try:
        raw = json.loads((folder / DATA_FILE).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}
    if not isinstance(raw, dict):
        return {}
    return {k: str(v).strip() for k, v in raw.items()
            if k in EDITABLE_KEYS and v is not None and str(v).strip()}


def save_data(folder: Path, data: dict) -> dict[str, str]:
    clean = {k: str(v).strip() for k, v in (data or {}).items()
             if k in EDITABLE_KEYS and v is not None and str(v).strip()}
    (folder / DATA_FILE).write_text(
        json.dumps(clean, ensure_ascii=False, indent=2), encoding="utf-8")
    return clean


# ── the nacrt ────────────────────────────────────────────────────────
@dataclass(frozen=True)
class GostOutcome:
    result: NacrtResult
    pdf_path: Path
    sidecar_path: Path


def run_gost_nacrt(folder: Path, settings: Settings | None = None, *,
                   offline: bool = False, force: bool = False) -> GostOutcome:
    """KORAK 3c for a guest project: plan + profile onto the title block,
    written as ``<folder>_nacrt.pdf`` into the project folder itself.

    ``settings`` is optional — only the font path and the geo finders use it,
    and a guest machine without a working config.yaml still gets its nacrt.
    """
    from cave_dossier.sastavnica import prefill as p

    folder = Path(folder)
    if not folder.is_dir():
        raise GostError(f"Mapa projekta ne postoji: {folder}")
    inputs = compose_mod.find_inputs(folder)
    dims = compose_mod.read_dimensions(inputs.dimensions)
    layout = Layout.from_mapping(dims, pad_m=compose_mod.read_pad_m(inputs.layout_sidecar))
    typed = load_data(folder)

    try:
        font = fonts.resolve(settings.sastavnica_font_path if settings else None)
    except fonts.FontUnavailable as exc:
        raise GostError(str(exc)) from exc

    page = SastavnicaResult(serial=0, cave_name=typed.get("ime_objekta", folder.name),
                            template_version=addresses.TEMPLATE_VERSION,
                            font=font.path.name, font_tier=font.tier,
                            dimensions_source=inputs.dimensions.name)
    if font.note:
        page.notes.append(font.note)
    if not dims.get("calculated"):
        page.notes.append(f"{inputs.dimensions.name} kaže da survey nije "
                          "izračunat – provjeri duljine.")
    resolve_fields(page, typed, p._dimension_values(dims, font.path),
                   settings=settings, offline=offline, font_path=font.path)

    values = {key: fv.value for key, fv in page.fields.items() if fv.value}
    try:
        page_pdf, placed = render_mod.render(
            addresses.BLANK_TEMPLATE, values, font.path,
            metadata={"title": f"Sastavnica – {page.cave_name}",
                      "subject": page.cave_name, "creator": STAMP,
                      "producer": f"{STAMP} ({addresses.TEMPLATE_VERSION})"})
    except render_mod.RenderError as exc:
        raise GostError(str(exc)) from exc
    page.placed = [PlacedField(key=x.key, text=x.text, font_size=x.font_size,
                               width_pt=round(x.width, 2), overflowed=x.overflowed)
                   for x in placed]
    for item in page.placed:
        if item.overflowed:
            page.notes.append(f"'{addresses.V2[item.key].label}' ne stane u ćeliju "
                              f"ni na {addresses.MIN_FONT_SIZE:g} pt – skrati tekst.")

    page_pdf = swap_logo(page_pdf, find_logo(folder), page.notes)

    placements = compose_mod.placements(inputs.plan, inputs.profile, layout)
    for item in placements:
        if item.cut:
            page.notes.append(f"{item.source.name}: ispis prelazi "
                              f"{' i '.join(item.cut)} rub stranice – ponovi KORAK 3.")
    composed = compose_mod.compose_nacrt(page_pdf, inputs.plan, inputs.profile, layout)
    composed = _stamp(composed, page.cave_name)

    from cave_dossier.sastavnica.nacrt import _placed

    result = NacrtResult(
        serial=0, cave_name=page.cave_name, sastavnica=page,
        inputs=[path.name for path in inputs.files], mjerilo=layout.mjerilo,
        arrangement=layout.arrangement, plan_scale=layout.plan_scale,
        profile_scale=layout.profile_scale,
        drawings=[_placed(item) for item in placements], notes=list(page.notes))

    pdf_path = folder / f"{folder_name(folder.name)}_nacrt.pdf"
    if pdf_path.exists() and not force and not p._is_ours(pdf_path, STAMP):
        raise GostError(
            f"{pdf_path.name} već postoji i NIJE ga napravio ovaj alat (vjerojatno "
            "je uređen) – preimenuj ga ili pokreni s --force.")
    try:
        pdf_path.write_bytes(composed)
    except OSError as exc:
        raise GostError(f"{pdf_path.name} se ne može zapisati ({exc}) – "
                        "zatvori ga u PDF pregledniku i ponovi.") from exc
    sidecar_path = folder / SIDECAR
    sidecar_path.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    return GostOutcome(result, pdf_path, sidecar_path)


def resolve_fields(page: SastavnicaResult, typed: dict[str, str],
                   measured: dict[str, str], *, settings: Settings | None,
                   offline: bool, font_path: Path | None) -> None:
    """typed > measured > geo > stub, with the archive route's formatting."""
    from cave_dossier.sastavnica import prefill as p

    fields = page.fields
    for key, text in addresses.CONSTANTS.items():
        fields[key] = FieldValue(value=text, source="constant")
    for key, value in measured.items():
        fields[key] = FieldValue(value=value, source="nacrt")

    formatters = {
        "stvarna_duljina": p._metres, "tlocrtna_duljina": p._metres,
        "nadmorska_visina": p._metres, "dubina": p._depth,
        "crtali": p._people, "mjerili": p._people, "nacrt_uredio": p._people,
    }
    for key, raw in typed.items():
        if key in ("htrs", "ekipa", "istrazili"):
            continue
        fmt = formatters.get(key)
        value = (fmt(raw) if fmt else None) or raw
        fields[key] = FieldValue(value=value, source="ručno")

    xy = parse_htrs(typed.get("htrs"))
    if xy:
        fields["htrs"] = FieldValue(value=f"{round(xy[0])} {round(xy[1])}", source="ručno")
    elif typed.get("htrs"):
        fields["htrs"] = FieldValue(value=typed["htrs"], source="ručno")
        page.notes.append("HTRS koordinate nisu dva broja (X Y) – ispisane kako su "
                          "upisane, nadmorska visina i lokacija se ne traže.")

    credited = [fields[k].value for k in ("crtali", "mjerili") if k in fields]
    if typed.get("ekipa"):
        rest = p._people(typed["ekipa"], exclude=credited)
        fields["ekipa"] = FieldValue(value=rest or addresses.stub_for("ekipa"),
                                     source="ručno")
    if typed.get("istrazili"):
        fields["istrazili"] = FieldValue(
            value=p._societies(typed["istrazili"], p._measuring_font(font_path))
            or typed["istrazili"], source="ručno")

    if xy and settings is not None:
        _fill_from_geo(page, xy, settings, offline)

    missing = []
    for key in addresses.V2:
        if fields.get(key) and fields[key].value:
            continue
        missing.append(addresses.V2[key].label)
        fields[key] = FieldValue(value=addresses.stub_for(key), source="stub")
    if missing:
        page.notes.append("Bez podatka (upiši u Podatke i ponovi): " + ", ".join(missing))


def _fill_from_geo(page: SastavnicaResult, xy: tuple[float, float],
                   settings: Settings, offline: bool) -> None:
    """Lokacija and Nadmorska visina from the coordinates, only into an EMPTY
    cell, fail-soft: the guest's cave may well be outside Croatia's data."""
    from cave_dossier.sastavnica import prefill as p

    fields = page.fields
    if "nadmorska_visina" not in fields:
        try:
            kota = p.elevation_mod.build_finder(settings, offline=offline).kota(*xy)
            if kota.elevation_m is not None:
                fields["nadmorska_visina"] = FieldValue(
                    value=f"{p._number(round(kota.elevation_m))} m", source="dmv-dgu")
        except Exception as exc:  # noqa: BLE001 — a nicety, never a blocker
            page.notes.append(f"Nadmorska visina iz DMV-a nije dostupna ({exc}).")
    if "lokacija" not in fields:
        try:
            found = p.locality_mod.build_finder(settings, offline=offline).locate(*xy)
            text = ", ".join(x for x in (found.najblize_mjesto, found.lokalitet) if x)
            if text:
                fields["lokacija"] = FieldValue(value=text, source="geo")
        except Exception as exc:  # noqa: BLE001
            page.notes.append(f"Lokacija iz koordinata nije dostupna ({exc}).")


def parse_htrs(raw: str | None) -> tuple[float, float] | None:
    """``"345678 4987654"`` / ``"345678, 4987654"`` / ``"X=345678 Y=4987654"``."""
    if not raw:
        return None
    numbers = re.findall(r"\d+(?:[.,]\d+)?", raw)
    if len(numbers) != 2:
        return None
    x, y = (float(n.replace(",", ".")) for n in numbers)
    # HTRS96/TM: X (easting) is six digits, Y (northing) seven. Typed the other
    # way round, swap — the printed cell is always "X Y".
    if x > 1_000_000 > y:
        x, y = y, x
    return x, y


def find_logo(folder: Path) -> Path | None:
    for name in LOGO_NAMES:
        for path in folder.iterdir():
            if path.is_file() and path.name.lower() == name:
                return path
    return None


def swap_logo(page_pdf: bytes, logo: Path | None, notes: list[str]) -> bytes:
    """The title block without the archive's own logo, with the guest's in its place."""
    import pymupdf

    box = pymupdf.Rect(*LOGO_BOX)
    with pymupdf.open("pdf", page_pdf) as doc:
        page = doc[0]
        page.add_redact_annot(box, fill=False)
        page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE,
                              graphics=pymupdf.PDF_REDACT_LINE_ART_REMOVE_IF_COVERED,
                              text=pymupdf.PDF_REDACT_TEXT_NONE)
        if logo is not None:
            try:
                page.insert_image(box + (1, 1, -1, -1), filename=str(logo),
                                  keep_proportion=True)
            except Exception as exc:  # noqa: BLE001 — a bad image just leaves the cell empty
                notes.append(f"{logo.name} se ne može umetnuti ({exc}) – polje loga ostaje prazno.")
        return doc.tobytes(garbage=4, deflate=True)


def _stamp(pdf_bytes: bytes, cave_name: str) -> bytes:
    import pymupdf

    with pymupdf.open("pdf", pdf_bytes) as doc:
        doc.set_metadata({**(doc.metadata or {}), "title": f"Nacrt – {cave_name}",
                          "subject": cave_name, "creator": STAMP,
                          "producer": f"{STAMP} ({addresses.TEMPLATE_VERSION})"})
        return doc.tobytes(garbage=4, deflate=True)


__all__ = ["ComposeError", "DATA_FILE", "EDITABLE", "GostError", "GostOutcome",
           "create_project", "folder_name", "list_projects", "load_data",
           "parse_htrs", "project_folder", "projects_root", "resolve_project",
           "run_gost_nacrt", "save_data"]
