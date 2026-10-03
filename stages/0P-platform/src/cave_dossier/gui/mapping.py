"""The 3N mapping page: the shared TDX mapping, a cave's override, the pictures.

The mapping itself belongs to 3N's tools (``tdx-mapping.json`` beside them,
merged with a cave's ``tdx-mapping-objekt.json`` by ``tdx_mapping.py``). 3N is
not part of the package, so this loads that one pure-data helper from the
tools folder by path instead of copying its merge rules — the page and KORAK
1/2 must agree on what a cave's mapping is. Nothing here runs a tool.

Edits are per cave only (user decision 2026-10-03): the page sends the whole
effective mapping back and only its difference from the shared default is
written into the cave's SB_ folder.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

ENTRY_SECTIONS = ("points", "lines", "areas")
# Which KORAK a part of the mapping takes effect in — what the page tells the
# operator to redo after a change.
KORAK_OF = {"points": 1, "lines": 1, "areas": 1, "generic": 1, "postimport": 2}
SIZES = ["default", "verysmall", "small", "medium", "large", "verylarge"]

_modules: dict[str, ModuleType] = {}
_catalog: dict[str, tuple[float, dict]] = {}


class MappingError(Exception):
    """A message the page shows as it is."""


def _module(tools: Path, name: str) -> ModuleType:
    key = str(tools / name)
    if key not in _modules:
        if str(tools) not in sys.path:
            sys.path.insert(0, str(tools))
        spec = importlib.util.spec_from_file_location(f"_3n_{Path(name).stem}", tools / name)
        if spec is None or spec.loader is None:
            raise MappingError(f"Nema {tools / name}.")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _modules[key] = module
    return _modules[key]


def catalog(tools: Path) -> dict:
    """tdx-mapping-catalog.json (pictures), cached until the file changes."""
    path = tools / "tdx-mapping-catalog.json"
    if not path.is_file():
        raise MappingError("Nema tdx-mapping-catalog.json uz 3N alate — pokreni "
                           "make_signs_catalog.py.")
    mtime = path.stat().st_mtime
    cached = _catalog.get(str(path))
    if cached is None or cached[0] != mtime:
        cached = (mtime, json.loads(path.read_text(encoding="utf-8")))
        _catalog[str(path)] = cached
    return cached[1]


def _leaf(ws, broj: int) -> Path | None:
    leaves = ws.cave_leaves(broj)
    return leaves[0].path if leaves else None


def view(ws, broj: int, tools: Path) -> dict:
    tm = _module(tools, "tdx_mapping.py")
    fixer = _module(tools, "fix_imported_linetypes.py")
    default_path = tools / "tdx-mapping.json"
    default = tm.load_json(str(default_path)) if default_path.is_file() else {}
    leaf = _leaf(ws, broj)
    override_path = leaf / tm.OVERRIDE_NAME if leaf else None
    override, error = None, None
    if override_path and override_path.is_file():
        try:
            override = tm.load_json(str(override_path))
        except (OSError, ValueError) as exc:
            error = f"{override_path.name} se ne može pročitati ({exc}) — koristi se zadano."
    effective = tm.merge(default, override) if override else default
    return {
        "broj": broj,
        "leaf": str(leaf) if leaf else None,
        "default": default,
        "override": override,
        "override_path": str(override_path) if override and not error else None,
        "override_modified": override_path.stat().st_mtime if override and not error else None,
        "error": error,
        "effective": effective,
        "changed": sorted(tm.diff(default, effective)),
        "korak_of": KORAK_OF,
        "centerline_types": dict(fixer.CENTERLINE_TYPES),
        "design_property_types": sorted(fixer.DESIGN_PROPERTY_TYPES),
        "sign_names": sorted(fixer.SIGN_VALUES),
        "sizes": SIZES,
    }


def _check(effective) -> None:
    if not isinstance(effective, dict):
        raise MappingError("Mapiranje mora biti objekt.")
    for section in ENTRY_SECTIONS:
        entries = effective.get(section, {})
        if not isinstance(entries, dict):
            raise MappingError(f"{section}: mora biti objekt.")
        for name, entry in entries.items():
            if name.startswith("_"):
                continue
            if not isinstance(entry, dict) or not (
                    "to" in entry or "label" in entry or entry.get("leave")):
                raise MappingError(f"{section} › {name}: treba cilj, oznaku ili 'ostavi'.")
    post = effective.get("postimport", {})
    if not isinstance(post, dict):
        raise MappingError("postimport: mora biti objekt.")
    for key, value in post.get("centerline", {}).items():
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise MappingError(f"Poligon › {key}: mora biti broj.")


def save(ws, broj: int, tools: Path, effective) -> dict:
    """Write the cave's override from the page's effective mapping."""
    _check(effective)
    leaf = _leaf(ws, broj)
    if leaf is None:
        raise MappingError(f"SB {broj} nema mapu pod !Za digitalizirat — prilagodba "
                           "se sprema u mapu objekta.")
    tm = _module(tools, "tdx_mapping.py")
    default_path = tools / "tdx-mapping.json"
    default = tm.load_json(str(default_path)) if default_path.is_file() else {}
    tm.write_override(str(leaf), default, effective)
    return view(ws, broj, tools)


def reset(ws, broj: int, tools: Path) -> dict:
    """Back to the shared default: remove the cave's override."""
    leaf = _leaf(ws, broj)
    tm = _module(tools, "tdx_mapping.py")
    if leaf is not None:
        path = leaf / tm.OVERRIDE_NAME
        if path.is_file():
            path.unlink()
    return view(ws, broj, tools)
