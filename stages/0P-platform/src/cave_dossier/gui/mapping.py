"""The 3N mapping page: the shared TDX mapping, a cave's override, the pictures.

The mapping itself belongs to 3N's tools (``tdx-mapping.json`` beside them,
merged with a cave's ``tdx-mapping-objekt.json`` by ``tdx_mapping.py``). 3N is
not part of the package, so this loads that one pure-data helper from the
tools folder by path instead of copying its merge rules — the page and KORAK
1/2 must agree on what a cave's mapping is. Nothing here runs a tool.

Edits are per cave only (user decision 2026-10-03): the page sends the whole
effective mapping back and only its difference from the shared default is
written into the cave's SB_ folder.

The cave's symbol theme (project 0007, T4) is the override's top-level
``"theme"``. The page draws each theme's artwork from the theme's own SVGs:
``theme_view`` builds small preview pictures (a sign tinted, a line as a strip
of its units, an area as a scattered sample or a hatch). They are sketches of
the look, not cSurvey's rendering.
"""

from __future__ import annotations

import importlib.util
import json
import math
import random
import re
import sys
from pathlib import Path
from types import ModuleType

ENTRY_SECTIONS = ("points", "lines", "areas")
# Which KORAK a part of the mapping takes effect in — what the page tells the
# operator to redo after a change.
KORAK_OF = {"points": 1, "lines": 1, "areas": 1, "generic": 1, "postimport": 2, "theme": 2}
SIZES = ["default", "verysmall", "small", "medium", "large", "verylarge"]

_modules: dict[str, ModuleType] = {}
_catalog: dict[str, tuple[float, dict]] = {}
_theme_views: dict[str, tuple[tuple, dict]] = {}


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
        raise MappingError("Nema tdx-mapping-catalog.json uz 3N alate – pokreni "
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
            error = f"{override_path.name} se ne može pročitati ({exc}) – koristi se zadano."
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
        "themes": theme_list(tools),
    }


def _check(effective, tools: Path) -> None:
    if not isinstance(effective, dict):
        raise MappingError("Mapiranje mora biti objekt.")
    theme = effective.get("theme")
    if theme is not None and theme not in {t["id"] for t in theme_list(tools)}:
        raise MappingError(f"Nepoznata tema: {theme}.")
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
    _check(effective, tools)
    leaf = _leaf(ws, broj)
    if leaf is None:
        raise MappingError(f"SB {broj} nema mapu pod !Za digitalizirat – prilagodba "
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


# ── themes (project 0007) ───────────────────────────────────────────

def _themes(tools: Path) -> ModuleType:
    return _module(tools, "themes.py")


def theme_list(tools: Path) -> list[dict]:
    """[{id, name}] of the themes beside the tools; [] when there are none."""
    try:
        th = _themes(tools)
        root = th.default_themes_root()
        out = []
        for tid in th.list_themes(root):
            try:
                raw = json.loads((Path(root) / tid / "theme.json").read_text(encoding="utf-8"))
                name = raw.get("name") or tid
            except (OSError, ValueError):
                name = tid
            out.append({"id": tid, "name": name})
        return out
    except (MappingError, OSError, ImportError):
        return []


def theme_view(tools: Path, theme_id: str) -> dict:
    """One theme's preview pictures per kind and key, cached until its files change."""
    th = _themes(tools)
    root = Path(th.default_themes_root())
    if theme_id not in th.list_themes(str(root)):
        raise MappingError(f"Nepoznata tema: {theme_id}.")
    stamp = tuple(sorted((str(p), p.stat().st_mtime) for p in root.rglob("*")
                         if p.suffix in (".json", ".svg")))
    cached = _theme_views.get(theme_id)
    if cached and cached[0] == stamp:
        return cached[1]
    try:
        theme = th.load_theme(theme_id, str(root))
    except th.ThemeError as exc:
        raise MappingError(f"Tema {theme_id} ima greške: {exc}") from exc
    out = {"id": theme.id, "name": theme.name or theme.id,
           "monochrome": theme.monochrome is not None,
           "signs": {}, "lines": {}, "areas": {}}
    for key, spec in theme.signs.items():
        out["signs"][key] = {"svg": _sign_pic(spec) if spec.get("svg") else None,
                             "color": _hex(spec["color"])}
    ta = _module(tools, "theme_apply.py")
    targets = ta.line_targets()
    for key, spec in theme.lines.items():
        side = lambda k=key: ta.side_for(None, k, targets)   # noqa: E731
        out["lines"][key] = {"svg": _line_pic(spec, side), "color": _hex(spec["color"])}
    for i, (key, spec) in enumerate(sorted(theme.areas.items())):
        out["areas"][key] = {"svg": _area_pic(spec, f"tc-{theme.id}-{i}"),
                             "color": _hex(spec["color"])}
    _theme_views[theme_id] = (stamp, out)
    return out


_VIEWBOX = re.compile(r'viewBox="([^"]+)"')
_BODY = re.compile(r"<svg[^>]*>(.*)</svg>", re.S)
_DASH = {"dash": (3, 1), "dot": (1, 1), "dashdot": (3, 1, 1, 1), "dashdotdot": (3, 1, 1, 1, 1, 1)}


def _hex(argb: int) -> str:
    return "#%06X" % (argb & 0xFFFFFF)


def _art(path: str, color: str) -> tuple[list[float], str]:
    """(viewBox numbers, inner markup) of a theme SVG, its black painted in `color`.

    The split writes every non-white fill as #000000 and white as #FFFFFF
    (theme_svg.py); cSurvey paints the black in the theme colour, and so does this.
    """
    text = Path(path).read_text(encoding="utf-8")
    vb = [float(v) for v in _VIEWBOX.search(text).group(1).replace(",", " ").split()]
    body = _BODY.search(text).group(1)
    body = re.sub(r"<title>.*?</title>", "", body, flags=re.S)
    body = re.sub(r'fill="#000000"', f'fill="{color}"', body, flags=re.I)
    return vb, body


def _svg(vb, inner) -> str:
    x, y, w, h = vb
    return (f'<svg xmlns="http://www.w3.org/2000/svg" class="theme-pic" '
            f'viewBox="{x:g} {y:g} {w:g} {h:g}">{inner}</svg>')


def _sign_pic(spec) -> str:
    vb, body = _art(spec["svg"], _hex(spec["color"]))
    x, y, w, h = vb
    pad = 0.1 * max(w, h)
    rot = spec.get("rotate") or 0
    inner = f'<g transform="rotate({rot:g} {x + w / 2:g} {y + h / 2:g})">{body}</g>' if rot else body
    return _svg((x - pad, y - pad, w + 2 * pad, h + 2 * pad), inner)


def _line_pic(spec, side) -> str:
    """Three units along a straight line, spaced as cSurvey spaces them on a
    spline: pitch = unit width × (1 + spacing/10) / 100 (themes README).

    The side follows theme_apply: `auto` takes the item's built-in pen side
    (``side()`` = theme_apply.side_for). As the mockup prints a left-to-right
    line, `inner` is above it and `outer` below; the unit (drawn pointing away
    from the line, its foot on it) points away for outer and for inner+flip,
    and a centred unit stays as drawn (r3–r11 prints)."""
    color = _hex(spec["color"])
    deco = spec.get("decoration") or {}
    units = []
    if spec.get("svg"):
        vb, body = _art(spec["svg"], _hex(spec.get("decoration_color", spec["color"])))
        bx, by, uw, uh = vb
        pitch = max(uw * (1 + float(deco.get("spacing_pct", 3000)) / 10) / 100, uw)
        length = 2.5 * pitch + uw
        align, flip = deco.get("alignment", "auto"), deco.get("flip")
        if align == "auto":
            align, auto_flip = side()
            flip = auto_flip if flip is None else flip
        flip = bool(flip)
        for i in range(3):
            x0 = 0.25 * pitch + i * pitch - bx
            if align == "center":                   # as drawn: on a down pen (slope) the
                t = f"translate({x0:g},{-uh / 2 - by:g})"   # flip undoes cSurvey's own mirror
            elif align == "outer":                  # below the line
                t = (f"translate({x0:g},{-by:g})" if flip
                     else f"translate({x0:g},{uh + by:g}) scale(1,-1)")
            else:                                   # inner: above the line
                t = (f"translate({x0:g},{-uh - by:g})" if flip
                     else f"translate({x0:g},{by:g}) scale(1,-1)")
            units.append(f'<g transform="{t}">{body}</g>')
        top, height = -uh * 1.2, uh * 2.4
    else:
        length, top, height = 10.0, -1.0, 2.0
    base = ""
    style = spec.get("style", "solid")
    if style != "none":
        sw = max(height * 0.035, 0.02)
        pattern = spec.get("dash") if style == "custom" else _DASH.get(style)
        dash = f' stroke-dasharray="{" ".join(f"{d * sw:g}" for d in pattern)}"' if pattern else ""
        base = (f'<line x1="0" y1="0" x2="{length:g}" y2="0" stroke="{color}" '
                f'stroke-width="{sw:g}"{dash}/>')
    return _svg((0, top, length, height), base + "".join(units))


def _area_pic(spec, clip_id: str) -> str:
    """A 2 × 1.4 m sample (in metres): scattered tiles, a hatch or a plain fill."""
    color = _hex(spec["color"])
    w, h = 2.0, 1.4
    frame = f'<rect x="0" y="0" width="{w}" height="{h}" fill="none" stroke="#000" stroke-width="0.02"/>'
    clip = f'<clipPath id="{clip_id}"><rect x="0" y="0" width="{w}" height="{h}"/></clipPath>'
    bg = spec.get("background_color")
    back = f'<rect x="0" y="0" width="{w}" height="{h}" fill="{_hex(bg)}"/>' if bg is not None else ""
    parts = []
    if spec.get("solid"):
        parts.append(f'<rect x="0" y="0" width="{w}" height="{h}" fill="{color}"/>')
    elif spec.get("pattern"):
        p = spec["pattern"]
        step = max(float(p.get("density", 1)) * float(p.get("zoom", 1)), 0.05)
        angle = float(p.get("angle", 45))
        for a in [angle] + ([angle + 90] if p.get("type") == "crossed" else []):
            dx, dy = math.cos(math.radians(a)), math.sin(math.radians(a))
            k = -3.0
            while k <= 3.0:
                cx, cy = w / 2 - dy * k, h / 2 + dx * k
                parts.append(f'<line x1="{cx - dx * 3:g}" y1="{cy - dy * 3:g}" x2="{cx + dx * 3:g}" '
                             f'y2="{cy + dy * 3:g}" stroke="{color}" stroke-width="0.012"/>')
                k += step
    elif spec.get("svg"):
        vb, body = _art(spec["svg"], color)
        zoom, dens = float(spec.get("zoom", 1)), max(float(spec.get("density", 1)), 0.05)
        cx, cy = vb[0] + vb[2] / 2, vb[1] + vb[3] / 2
        rnd = random.Random(1)                      # the same picture every time
        fixed = spec.get("angle_mode") == "fixed"
        shift = spec.get("position", "random") == "random"
        y = -dens / 2
        while y < h + dens:
            x = -dens / 2
            while x < w + dens:
                px = x + (dens * rnd.uniform(-0.5, 0.5) if shift else 0)
                ang = float(spec.get("angle", 0)) if fixed else rnd.uniform(0, 359)
                parts.append(f'<g transform="translate({px:g},{y:g}) rotate({ang:g}) scale({zoom:g}) '
                             f'translate({-cx:g},{-cy:g})">{body}</g>')
                x += dens
            y += dens
    inner = f'<defs>{clip}</defs>{back}<g clip-path="url(#{clip_id})">{"".join(parts)}</g>{frame}'
    return _svg((-0.05, -0.05, w + 0.1, h + 0.1), inner)
