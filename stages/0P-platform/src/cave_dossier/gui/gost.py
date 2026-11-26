"""The dashboard's guest page (/gost): 3N for a survey that is not in SB.

The main page is built around a Redni broj — its cave picker reads SB and its
files come from the cave's Drive intake leaf. A guest from another club has
neither, so this page works over the local guest projects of
``sastavnica/gost.py`` instead: pick or create a project, drop the TopoDroid
export into it, type the title-block cells, and run the same 3N steps.

The steps are the catalog's own 3N actions (KORAK 1, 2, 3a, 3b — scripts that
take a file path and never read SB) plus ``cavedossier gost nacrt`` for 3c.
Every file argument is checked against the project's own files of the right
kind, so the page can still only run what is written down here.

The TDX mapping and the symbol theme are the main page's own Mapiranje
(``gui/mapping.py``, ``static/mapping.js``) pointed at the project folder: its
``tdx-mapping-objekt.json`` is found by KORAK 1 and 2 beside the survey file.
The KORAK 3a layout menu is ``gui/layouts.py`` on the project's _postp.

Nothing here writes to the Drive or SB: a guest's project is a local folder,
so the main page's confirm-before-write rule has nothing to guard and the
runs go with one click.
"""

from __future__ import annotations

import re
from pathlib import Path

from cave_dossier.gui import catalog, layouts, mapping
from cave_dossier.gui.state import FILE_KINDS, classify, tools_dir
from cave_dossier.sastavnica import addresses
from cave_dossier.sastavnica import gost as core

#: Page step -> catalog action. 3c is not a catalog action (it takes a folder,
#: not a Redni broj) and is built in ``step_args``.
STEPS: tuple[dict, ...] = (
    {"id": "k1", "action": "3n-k1", "step": "KORAK 1", "title": "Pripremi sirovi .csx",
     "kind": "raw", "options": {"--force": True}},
    {"id": "m1", "manual": True, "step": "cSurvey", "kind": "prep",
     "title": "cSurvey: otvori _prep i spremi",
     "help": "Otvori <ime>_prep.csx u cSurveyu, pa File › Save As (isto ime)."},
    {"id": "k2", "action": "3n-k2", "step": "KORAK 2", "title": "Dovrši uvoz",
     "kind": "prep", "options": {"--force": True}},
    {"id": "m2", "manual": True, "step": "cSurvey", "kind": "postp",
     "title": "cSurvey: ispravi skicu",
     "help": "Otvori <ime>_postp.csx u cSurveyu, ispravi skicu i spremi."},
    {"id": "k3a", "action": "3n-k3a", "step": "KORAK 3a",
     "title": "Dovrši nacrt (_postp → _postp_resolved)", "kind": "postp",
     "options": {"--force": True}, "layout": True},
    {"id": "k3b", "action": "3n-k3b", "step": "KORAK 3b",
     "title": "Ispiši tlocrt i profil (cSurvey bez dijaloga)", "kind": "resolved"},
    {"id": "k3c", "cli": True, "step": "KORAK 3c", "title": "Složi Nacrt na sastavnicu",
     "help": "Tlocrt + profil + upisani podaci → <Ime>_nacrt.pdf u mapi projekta. "
             "Ponovi kad promijeniš podatke."},
)
STEPS_BY_ID = {step["id"]: step for step in STEPS}

_UPLOAD_EXT = {".csx", ".csz", ".zip", ".png", ".jpg", ".jpeg", ".json"}
_SAFE_NAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
MAX_UPLOAD = 200 * 1024 * 1024


class GostApiError(Exception):
    pass


def page_json() -> dict:
    """What the page needs once: the root, the form, the steps."""
    return {
        "root": str(core.projects_root()),
        "fields": [{"key": key, "label": addresses.V2[key].label, "hint": hint}
                   for key, hint in core.EDITABLE],
        "steps": [{k: v for k, v in step.items() if k != "options"} for step in STEPS],
        "projects": core.list_projects(),
    }


def _folder(project_id: str) -> Path:
    try:
        return core.project_folder(project_id)
    except core.GostError as exc:
        raise GostApiError(str(exc)) from exc


def create(name: str) -> dict:
    if not (name or "").strip():
        raise GostApiError("Upiši ime objekta.")
    folder = core.create_project(name)
    return view(folder.name)


def view(project_id: str) -> dict:
    folder = _folder(project_id)
    files = []
    for path in sorted(folder.iterdir(), key=lambda p: p.name.lower()):
        if not path.is_file() or path.name.lower() in ("desktop.ini", "thumbs.db"):
            continue
        stat = path.stat()
        kind = classify(path, 0)
        if path.name.endswith("_nacrt.pdf"):
            kind = "nacrt"
        elif path.name == core.DATA_FILE:
            kind = "podaci"
        elif path.name == "tdx-mapping-objekt.json":
            kind = "mapiranje"
        files.append({"name": path.name, "path": str(path), "kind": kind,
                      "modified": stat.st_mtime, "size": stat.st_size})
    return {"id": folder.name, "path": str(folder), "data": core.load_data(folder),
            "measured": _measured(folder), "logo": bool(core.find_logo(folder)),
            "files": files}


# ── the TDX mapping and the theme (gui/mapping.py, per project) ──────

def _tools() -> Path:
    tools = tools_dir()
    if tools is None:
        raise GostApiError("3N alati nisu pronađeni (CSX_TOOLS).")
    return tools


def mapping_api(project_id: str, effective=None, *, reset: bool = False,
                save: bool = False) -> dict:
    """The main page's Mapiranje for a guest project: the same view, the same
    save (only the difference from the shared default goes into the folder's
    tdx-mapping-objekt.json, where KORAK 1 and 2 find it beside the survey)."""
    folder = _folder(project_id)
    tools = _tools()
    try:
        if reset:
            out = mapping.reset_folder(folder, folder.name, tools)
        elif save:
            out = mapping.save_folder(folder, folder.name, tools, effective)
        else:
            out = mapping.view_folder(folder, folder.name, tools)
    except mapping.MappingError as exc:
        raise GostApiError(str(exc)) from exc
    out["label"] = folder.name
    return out


def layout_menu(project_id: str, path: str) -> dict:
    """The sheets KORAK 3a would offer for one of the project's _postp files."""
    if path not in candidates(project_id, "postp"):
        raise GostApiError("Nije _postp datoteka ovog projekta.")
    try:
        return layouts.menu(_tools(), Path(path))
    except layouts.LayoutError as exc:
        raise GostApiError(str(exc)) from exc


def _measured(folder: Path) -> dict:
    """The KORAK 3 numbers the nacrt will print where the form is empty."""
    from cave_dossier.sastavnica import compose, prefill

    try:
        inputs = compose.find_inputs(folder)
        return prefill._dimension_values(compose.read_dimensions(inputs.dimensions), None)
    except Exception:  # noqa: BLE001 — no KORAK 3 yet is the normal case
        return {}


def save(project_id: str, data: dict) -> dict:
    folder = _folder(project_id)
    core.save_data(folder, data if isinstance(data, dict) else {})
    return view(project_id)


def upload(project_id: str, name: str, payload: bytes) -> dict:
    """One file dropped on the page, into the project folder. Never replaces
    an existing file — a second drop of the same export gets a (2) suffix."""
    folder = _folder(project_id)
    clean = _SAFE_NAME.sub("_", Path(str(name)).name).strip().strip(".")
    if not clean or Path(clean).suffix.lower() not in _UPLOAD_EXT:
        raise GostApiError("Prima se .csx/.csz (TopoDroid izvoz), .zip (TopoDroid "
                           "projekt) ili logo.png/.jpg.")
    if len(payload) > MAX_UPLOAD:
        raise GostApiError("Datoteka je prevelika.")
    target, n = folder / clean, 2
    while target.exists():
        target, n = folder / f"{Path(clean).stem} ({n}){Path(clean).suffix}", n + 1
    target.write_bytes(payload)
    return view(project_id)


def candidates(project_id: str, kind: str) -> list[str]:
    kinds = FILE_KINDS.get(kind, set())
    files = [f for f in view(project_id)["files"] if f["kind"] in kinds]
    files.sort(key=lambda f: f["modified"], reverse=True)
    return [f["path"] for f in files]


def step_args(project_id: str, step_id: str, file: str | None,
              layout: str | None = None, dry_run: bool = False,
              ) -> tuple[catalog.Action | None, list[str], str]:
    """(catalog action or None for the CLI, argv without interpreter, title).

    KORAK 3a: an empty layout accepts the proposal (``--yes``), a number picks
    that menu entry; ``dry_run`` only prints the menu so the guest can choose."""
    step = STEPS_BY_ID.get(step_id)
    if step is None or step.get("manual"):
        raise GostApiError("Nepoznat korak.")
    folder = _folder(project_id)
    if step.get("cli"):
        return None, ["gost", "nacrt", str(folder)], step["title"]
    action = catalog.BY_ID[step["action"]]
    allowed = candidates(project_id, step["kind"])
    if not allowed:
        raise GostApiError(f"{step['title']}: u projektu nema datoteke za taj korak.")
    if file not in allowed:
        file = allowed[0]
    selected = dict(step.get("options") or {})
    if step.get("layout"):
        text = str(layout or "").strip()
        if text:
            selected["--layout"] = text
        else:
            selected["--yes"] = True
        if dry_run:
            selected["--dry-run"] = True
    try:
        args = catalog.build_args(action, file=file, selected=selected)
    except catalog.ActionError as exc:
        raise GostApiError(str(exc)) from exc
    return action, args, step["title"]


def owned_path(project_id: str, path: str) -> Path:
    """A file (or the folder itself) of this project — the guard for "open"."""
    folder = _folder(project_id).resolve()
    target = Path(path or folder).resolve()
    if target != folder and folder not in target.parents:
        raise GostApiError("Otvara se samo datoteka iz mape projekta.")
    if not target.exists():
        raise GostApiError(f"Ne postoji: {target}")
    return target
