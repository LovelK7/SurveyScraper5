#!/usr/bin/env python3
"""Apply a symbol theme to a post-import cSurvey file (project 0007, task T3, phase 1).

Phase 1 themes the SIGNS and the centerline. Lines and areas are phase 2: they
are only counted here (how many items a theme entry would reach).

Per sign item (type="6"), the theme entry is looked up the T8 way
(themes.resolve): the TopoDroid name recovered from the pre-import file by
tdx_name_recover.py first, then the cSurvey target of the item's `sign=`
(SignEnum -> catalog target), else the item is left alone.

  glyph   the theme SVG goes into the `<signs><cliparts>` pool under cSurvey's
          own id (nacrt_finish.clipart_hash: SHA-1, bytes as unpadded hex) -
          base64 in a .csx, a `_data/cliparts/<id>.svg` zip entry in a .csz,
          the KORAK 3 compass route (nacrt_finish.splice_sign_clipart), named
          tema-<theme>_<file>.svg (pool_name). The
          item's `data` is repointed to it (dataformat 2); `sign=` is kept, so
          cSurvey still knows what the item is. A theme `size` is baked into
          the glyph's csurvey:scale (cCliparts.vb:80-91 normalises every glyph
          to scale x 1 design unit); `signsize` stays the operator's. A theme
          `rotate` is baked into the glyph's coordinates
          (theme_svg.rotate_svg).
  colour  a fill sign gets an inline custom solid brush in the colour
          (`<brush type="99" ... hatchtype="1"/>`, the shape cSurvey wrote in
          the T0 oracle); black keeps the built-in `<brush type="7"/>`
          (SignSolid, black).
  pen     cSurvey traces the item's pen round every path of the glyph
          (cDrawPaths.vb:1238-1245), which makes club glyphs look heavy. So by
          default (`outline_pen: false`, user 2026-10-06) the pen is an inline
          custom pen with style None (98): cCustomPen.pRender makes no GDI pen
          for it (cPen.vb:865-867) and Render adds the path with no pen
          (cPen.vb:1011-1104), so only the fills paint - for black glyphs too.
          `outline_pen: true` keeps the old look: black keeps the built-in
          `<pen type="10"/>` (TightPen), a colour gets an inline custom pen in
          that colour with TightPen's look (style 0, width 0 = the TightPen
          default width, cOptions.vb:1404-1425). `render: outline` (which
          implies the pen) makes the brush white and the pen the colour.
          A stroke-only path in a glyph (fill none) paints with the pen only,
          so it vanishes with the pen off - reported as a note.

The pen and brush we write are named "tema:<id>" (cSurvey keeps the name), and
the file records the theme in two string design properties, which cSurvey
keeps through a load + save (cPropertiesCollection.SaveTo writes every item):
CaveDossierTheme = <id> and CaveDossierThemeState = JSON of what to undo
(glyph ids we added, each sign's original glyph id, the centerline values we
overwrote). A re-run first undoes the previous theme, so themes replace each
other and never stack.

Usage:
  python theme_apply.py apply IN.csx|IN.csz --theme ID --pre PRE.csx [-o OUT]
                        [--dry-run] [--json REPORT] [--themes-root DIR]

  --pre is the pre-import file (raw TopoDroid export or the KORAK 1 _pp/_prep
  output). Without it every item falls back to its cSurvey target.
  Default OUT is <in>_<theme>.<ext> (a previous _<theme> suffix replaced).

Stdlib only. Never modifies the input.
"""

import argparse
import json
import os
import re
import sys
import zipfile
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.dont_write_bytecode = True
import fix_imported_linetypes as fixer                           # noqa: E402
import nacrt_finish                                             # noqa: E402
import tdx_name_recover                                         # noqa: E402
import theme_svg                                                # noqa: E402
import themes                                                   # noqa: E402

DESIGNS = ("plan", "profile")
SIGN_ITEM = "6"
PEN_TIGHT = "10"            # cPen.PenTypeEnum.TightPen
BRUSH_SIGN = "7"            # cBrush.BrushTypeEnum.SignSolid
CUSTOM = "99"               # inline per-item pen/brush
HATCH_SOLID = "1"           # cBrush.HatchTypeEnum.Solid
STYLE_SOLID = "0"           # cPen.PenStylesEnum.Solid
STYLE_NONE = "98"           # cPen.PenStylesEnum.None: no GDI pen at all (cPen.vb:865-867)
WHITE = -1                  # 0xFFFFFFFF
MARK = "tema:"              # name prefix of every pen/brush this tool writes
PROP_THEME = "CaveDossierTheme"
PROP_STATE = "CaveDossierThemeState"
_SCALE_RE = re.compile(rb'csurvey:scale="([^"]*)"')


# --------------------------------------------------------------------------
# lookups

def sign_targets(catalog_path=themes.CATALOG):
    """SignEnum (str) -> cSurvey target name, from the catalog's point targets
    (the csurvey:sign of each target's gallery SVG), then SIGN_VALUES."""
    with open(catalog_path, encoding="utf-8") as f:
        cat = json.load(f)
    out = {}
    for t in cat.get("targets", {}).get("point", []):
        m = re.search(r'csurvey:sign="(\d+)"', t.get("svg") or "")
        if m:
            out.setdefault(m.group(1), t["to"])
    for name, value in fixer.SIGN_VALUES.items():
        out.setdefault(str(value), name)
    return out


def iter_items(root):
    """Every item in (design, layer, index) order - the order of
    tdx_name_recover.post_units, so the two can be zipped."""
    for design in DESIGNS:
        layers = root.find(design + "/layers")
        if layers is None:
            continue
        for layer in layers.findall("layer"):
            its = layer.find("items")
            if its is None:
                continue
            for item in its.findall("item"):
                yield design, item


def recovered_names(pre_path, in_path, root):
    """[(design, item, tdx_name|None, kind|None, status)] for every item."""
    items = list(iter_items(root))
    if not pre_path:
        return [(d, it, None, None, "no-pre") for d, it in items]
    res = tdx_name_recover.recover(pre_path, in_path)
    if len(res["items"]) != len(items):
        raise ValueError("name recovery saw %d items, the file has %d"
                         % (len(res["items"]), len(items)))
    out = []
    for (design, item), info in zip(items, res["items"]):
        kinds = {sq["source"]["kind"] for sq in info["sequences"] if sq.get("source")}
        out.append((design, item, info.get("tdx_name"),
                    kinds.pop() if len(kinds) == 1 else None, info["status"]))
    return out


# --------------------------------------------------------------------------
# xml helpers

def reflow(parent):
    """Re-indent parent's children the way cSurvey writes them (2 spaces a
    level), so adding and removing elements leaves byte-identical files
    whatever the order. A parent that is not pretty-printed is left alone."""
    kids = list(parent)
    if not kids:
        if parent.text is not None and not parent.text.strip():
            parent.text = None
        return
    if not (parent.text and "\n" in parent.text):
        return
    child = parent.text.rsplit("\n", 1)[1]
    close = child[:-2] if child.endswith("  ") else ""
    for k in kids:
        k.tail = "\n" + child
    kids[-1].tail = "\n" + close


def _replace(item, old, new):
    new.tail = old.tail
    kids = list(new)
    if kids and item.text and "\n" in item.text:     # indent new's children like cSurvey
        indent = item.text.rsplit("\n", 1)[1]
        new.text = "\n" + indent + "  "
        for k in kids:
            k.tail = "\n" + indent + "  "
        kids[-1].tail = "\n" + indent
    item[list(item).index(old)] = new


def is_ours(el):
    return (el is not None and el.get("type") == CUSTOM
            and (el.get("name") or "").startswith(MARK))


def solid_brush(color, theme_id):
    """Inline custom solid brush, attribute set and order as cBrush.SaveTo
    writes it for hatchtype Solid (cBrush.vb:1561-1575; oracle: the
    `Water (not standard)` brush)."""
    return ET.Element("brush", {"type": CUSTOM, "name": MARK + theme_id,
                                "color": str(color), "backgroundcolor": "0",
                                "hatchtype": HATCH_SOLID})


def tight_pen(color, theme_id, style=STYLE_SOLID):
    """Inline custom pen = TightPen (black, width 0, solid; cPens.vb:292) in
    another colour. Width 0 renders at the same FilettoPenWidth as TightPen
    (cOptions.vb:1404-1425). Attributes and the empty `<clipart data=""/>` as
    cCustomPen.SaveTo writes them (cPen.vb:484-512), so a cSurvey load + save
    leaves the pen byte-identical (checked headless, 2026-10-06; the style-None
    pen too, 2026-10-07)."""
    pen = ET.Element("pen", {"type": CUSTOM, "name": MARK + theme_id,
                             "color": str(color), "style": style, "width": "0.00",
                             "decorationstyle": "0",
                             "decorationspacepercentage": "100.0",
                             "decorationalignment": "0",
                             "decorationscale": "1.00"})
    ET.SubElement(pen, "clipart", {"data": ""})
    return pen


def no_pen(color, theme_id):
    """Inline custom pen with style None: the glyph's paths get no outline."""
    return tight_pen(color, theme_id, STYLE_NONE)


def _design_props(root):
    props = root.find("properties")
    if props is None:
        raise ValueError("no <properties> element - not a cSurvey file")
    dp = props.find("designproperties")
    if dp is None:
        dp = ET.SubElement(props, "designproperties")
    return dp


def _prop(dp, name):
    for it in dp.findall("item"):
        if it.get("name") == name:
            return it
    return None


def read_state(root):
    """(theme_id, state dict) recorded by a previous run, or (None, None)."""
    props = root.find("properties")
    dp = props.find("designproperties") if props is not None else None
    if dp is None:
        return None, None
    tid = _prop(dp, PROP_THEME)
    st = _prop(dp, PROP_STATE)
    state = None
    if st is not None and (st.text or "").strip():
        try:
            state = json.loads(st.text)
        except ValueError:
            state = None
    return (tid.text if tid is not None else None), state


# --------------------------------------------------------------------------
# glyphs

def scale_svg(blob, factor):
    """Multiply the glyph's csurvey:scale (default 1) by factor."""
    m = _SCALE_RE.search(blob)
    if m:
        new = float(m.group(1).decode()) * factor
        return blob[:m.start(1)] + (b"%g" % round(new, 4)) + blob[m.end(1):]
    i = blob.find(b"<svg")
    if i < 0:
        raise ValueError("not an SVG")
    attrs = b' csurvey:scale="%g"' % round(factor, 4)
    if b"xmlns:csurvey" not in blob:
        attrs = b' xmlns:csurvey="http://www.csurvey.it"' + attrs
    return blob[:i + 4] + attrs + blob[i + 4:]


def pool_name(theme_id, svg_path):
    """Pool entry name: tema-<theme>_<file>.svg, so a themed glyph never looks
    like a duplicate of cSurvey's own gallery entry (blocks.svg) in the
    Clipart gallery's Survey list. Display only - the id is the content hash."""
    return "tema-%s_%s" % (theme_id, os.path.basename(svg_path))


_STROKE_ONLY_RE = re.compile(rb'<path\b[^>]*\bfill="none"')


def stroke_only_paths(blob):
    """Paths with no fill: with the pen off (outline_pen false) they do not paint."""
    return len(_STROKE_ONLY_RE.findall(blob))


def glyph_for(spec, theme_id):
    """(id, pool name, bytes) of the spec's glyph, or None (built-in glyph)."""
    if not spec.get("svg"):
        return None
    with open(spec["svg"], "rb") as f:
        blob = f.read()
    size = spec.get("size")
    if size and abs(size - 1.0) > 1e-9:
        blob = scale_svg(blob, size)
    if spec.get("rotate"):
        blob = theme_svg.rotate_svg(blob, spec["rotate"])
    return nacrt_finish.clipart_hash(blob), pool_name(theme_id, spec["svg"]), blob


def _pool(root):
    cl = nacrt_finish._cliparts_element(root)
    return cl, ({c.get("id") for c in cl.findall("clipart")} if cl is not None else set())


def _referenced_ids(root):
    return {it.get("data") for d in DESIGNS for it in (root.find(d).iter("item")
                                                       if root.find(d) is not None else [])
            if it.get("data")}


# --------------------------------------------------------------------------
# undo a previous theme

def undo(root, state):
    """Undo what a previous run wrote. -> (restored items, removed pool ids)."""
    state = state or {}
    glyphs = set(state.get("glyphs") or [])
    orig = state.get("orig") or {}
    cl, pool = _pool(root)
    n = 0
    for _design, item in iter_items(root):
        if item.get("type") != SIGN_ITEM:
            continue
        touched = False
        pen, brush = item.find("pen"), item.find("brush")
        if is_ours(pen):
            _replace(item, pen, ET.Element("pen", {"type": PEN_TIGHT}))
            touched = True
        if is_ours(brush):
            _replace(item, brush, ET.Element("brush", {"type": BRUSH_SIGN}))
            touched = True
        if item.get("data") in glyphs:
            back = orig.get(item.get("sign") or "")
            if back and back in pool:
                item.set("data", back)
                item.set("dataformat", "2")
            else:                       # cSurvey takes the gallery default for sign=
                item.attrib.pop("data", None)
                item.attrib.pop("dataformat", None)
            touched = True
        n += touched
    removed = []
    if cl is not None and glyphs:
        used = _referenced_ids(root)
        for c in list(cl.findall("clipart")):
            if c.get("id") in glyphs and c.get("id") not in used:
                cl.remove(c)
                removed.append(c.get("id"))
        reflow(cl)
    dp = _design_props(root)
    for name, was in (state.get("centerline") or {}).items():
        el = _prop(dp, name)
        if was is None:
            if el is not None:
                dp.remove(el)
        else:
            if el is None:
                el = ET.SubElement(dp, "item", {"name": name})
            el.set("type", was[0])
            el.text = was[1]
    for name in (PROP_THEME, PROP_STATE):
        el = _prop(dp, name)
        if el is not None:
            dp.remove(el)
    reflow(dp)
    return n, removed


# --------------------------------------------------------------------------
# apply

def _count(d, key):
    d[key] = d.get(key, 0) + 1


def apply_theme(root, is_csz, theme, names, targets):
    """Theme the sign items and the centerline of an undone root.

    names: recovered_names() output. -> (report dict, extra zip entries, added ids)
    """
    rep = {"theme": theme.id, "signs": 0, "lookup": {}, "themed": 0, "glyph": 0,
           "colour": 0, "outline": 0, "black_builtin": 0, "pen_off": 0,
           "skipped_custom": 0, "size_ignored": 0, "pool_added": [], "pool_reused": [],
           "phase2": {"lines": {}, "areas": {}}, "notes": []}
    extra, added, orig = {}, [], {}
    _cl, pool_before = _pool(root)
    for design, item, tdx, kind, status in names:
        if item.get("type") != SIGN_ITEM:
            if tdx and kind in ("line", "area"):
                section = "lines" if kind == "line" else "areas"
                if tdx in theme.section(section):
                    _count(rep["phase2"][section], tdx)
            continue
        rep["signs"] += 1
        target = targets.get(item.get("sign") or "")
        spec = themes.resolve(theme, "signs", tdx, target)
        method = ("tdx" if tdx and tdx in theme.signs else
                  "target" if spec is not None else
                  "none")
        _count(rep["lookup"], "%s (%s)" % (method, "recovered" if tdx else status))
        if spec is None:
            continue
        pen, brush = item.find("pen"), item.find("brush")
        if (pen is None or pen.get("type") != PEN_TIGHT
                or brush is None or brush.get("type") != BRUSH_SIGN):
            rep["skipped_custom"] += 1
            rep["notes"].append("%s sign=%s: own pen/brush set in cSurvey - not themed"
                                % (design, item.get("sign")))
            continue
        rep["themed"] += 1
        g = glyph_for(spec, theme.id)
        if g is None:
            if (spec.get("size") and abs(spec["size"] - 1.0) > 1e-9) or spec.get("rotate"):
                rep["size_ignored"] += 1
        else:
            cid, gname, blob = g
            was_added, ex = nacrt_finish.splice_sign_clipart(root, is_csz, cid, gname, blob)
            extra.update(ex)
            if was_added:
                added.append(cid)
                rep["pool_added"].append("%s %s" % (cid, gname))
            elif cid not in added and cid not in rep["pool_reused"]:
                rep["pool_reused"].append(cid)
            old = item.get("data")
            if old and old != cid and old not in added:
                orig.setdefault(item.get("sign") or "", old)
            item.set("data", cid)
            item.set("dataformat", "2")
            rep["glyph"] += 1
            lost = 0 if spec.get("outline_pen", True) else stroke_only_paths(blob)
            if lost:
                note = ("%s: %d stroke-only path(s) in the glyph do not print with the pen off"
                        " (outline_pen false)" % (spec["key"], lost))
                if note not in rep["notes"]:
                    rep["notes"].append(note)
        color = spec["color"]
        if spec.get("render") == "outline":
            _replace(item, brush, solid_brush(WHITE, theme.id))
            _replace(item, pen, tight_pen(color, theme.id))
            rep["outline"] += 1
        else:
            if color != themes.BLACK:
                _replace(item, brush, solid_brush(color, theme.id))
                rep["colour"] += 1
            if not spec.get("outline_pen", True):
                _replace(item, pen, no_pen(color, theme.id))
                rep["pen_off"] += 1
            elif color != themes.BLACK:
                _replace(item, pen, tight_pen(color, theme.id))
            else:
                rep["black_builtin"] += 1

    # centerline: theme overrides over whatever the file has (KORAK 2 wrote
    # postimport.centerline); the overwritten values are kept for undo.
    dp = _design_props(root)
    cl_orig = {}
    for name in theme.centerline:
        el = _prop(dp, name)
        cl_orig[name] = None if el is None else [el.get("type"), el.text]
    rep["centerline"] = fixer.apply_centerline(root, theme.centerline)

    state = {"glyphs": sorted(added), "orig": orig, "centerline": cl_orig}
    fixer._set_design_property(dp, PROP_THEME, "string", theme.id)
    fixer._set_design_property(dp, PROP_STATE, "string",
                               json.dumps(state, sort_keys=True, separators=(",", ":")))
    reflow(dp)
    return rep, extra, added


def theme_file(in_path, theme_id, pre_path=None, out_path=None, dry_run=False,
               themes_root=None):
    """Load, undo any previous theme, apply theme_id, write. -> report dict."""
    theme = themes.load_theme(theme_id, themes_root)
    root, is_csz, style = nacrt_finish.load_root(in_path)
    if nacrt_finish.not_yet_imported(root):
        raise ValueError("%s has not been imported into cSurvey yet" % in_path)
    prev_id, state = read_state(root)
    names = recovered_names(pre_path, in_path, root)
    restored, removed = undo(root, state)
    rep, extra, added = apply_theme(root, is_csz, theme, names, sign_targets())
    rep.update({"input": in_path, "output": None if dry_run else out_path,
                "previous_theme": prev_id, "undone_items": restored,
                "pool_removed": removed,
                "recovery": _recovery_counts(names)})
    if not dry_run:
        drop = {"_data/cliparts/%s.svg" % i for i in removed if i not in added}
        write(root, in_path, out_path, is_csz, style, extra, drop)
    return rep


def _recovery_counts(names):
    out = {}
    for _d, item, tdx, _k, status in names:
        kind = "sign" if item.get("type") == SIGN_ITEM else "other"
        _count(out, "%s %s" % (kind, "recovered" if tdx else status))
    return out


def write(root, src, out, is_csz, style, extra, drop):
    data = style.render(root)
    if is_csz:
        tmp = out + ".tmp"
        with zipfile.ZipFile(src) as zin, \
                zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
            for info in zin.infolist():
                n = info.filename
                if n == nacrt_finish.DATA_ENTRY or n in extra or n in drop \
                        or n.replace("\\", "/") in drop:
                    continue
                zout.writestr(info, zin.read(n))
            zout.writestr(nacrt_finish.DATA_ENTRY, data)
            for name in sorted(extra):
                zout.writestr(name, extra[name])
        os.replace(tmp, out)
    else:
        with open(out, "wb") as f:
            f.write(data)


def default_out(in_path, theme_id, themes_root=None):
    base, ext = os.path.splitext(in_path)
    for tid in sorted(themes.list_themes(themes_root), key=len, reverse=True):
        if base.endswith("_" + tid):
            base = base[:-len(tid) - 1]
            break
    return "%s_%s%s" % (base, theme_id, ext)


def print_report(rep, out=sys.stdout):
    w = out.write
    w("%s  tema %s%s\n" % (rep["output"] or "(dry run)", rep["theme"],
                            "  (bila: %s)" % rep["previous_theme"] if rep["previous_theme"] else ""))
    w("  imena: %s\n" % ", ".join("%s %d" % kv for kv in sorted(rep["recovery"].items())))
    w("  znakovi: %d, trazenje: %s\n" % (rep["signs"], ", ".join(
        "%s %d" % kv for kv in sorted(rep["lookup"].items())) or "-"))
    w("  tematizirano %d: glif %d, boja %d, obrub %d, bez olovke %d, "
      "crno (ugradeno) %d, preskoceno (rucno) %d\n"
      % (rep["themed"], rep["glyph"], rep["colour"], rep["outline"], rep["pen_off"],
         rep["black_builtin"], rep["skipped_custom"]))
    w("  bazen: +%d %s, ponovno %d, uklonjeno %d\n" % (
        len(rep["pool_added"]), "; ".join(rep["pool_added"]),
        len(rep["pool_reused"]), len(rep["pool_removed"])))
    w("  centerline: %d svojstava; ponisteno iz prethodne teme: %d znakova\n"
      % (rep["centerline"], rep["undone_items"]))
    for sec in ("lines", "areas"):
        hits = rep["phase2"][sec]
        w("  faza 2 %s (nije primijenjeno): %d stavki %s\n"
          % (sec, sum(hits.values()), ", ".join("%s %d" % kv for kv in sorted(hits.items()))))
    if rep["size_ignored"]:
        w("  NAPOMENA: size/rotate bez glifa teme zanemaren na %d znakova\n"
          % rep["size_ignored"])
    for n in rep["notes"]:
        w("  NAPOMENA: %s\n" % n)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("apply", help="theme a post-import .csx/.csz")
    a.add_argument("input")
    a.add_argument("--theme", required=True)
    a.add_argument("--pre", help="pre-import file for TopoDroid name recovery")
    a.add_argument("-o", "--out")
    a.add_argument("--dry-run", action="store_true")
    a.add_argument("--json", help="write the report as JSON here")
    a.add_argument("--themes-root")
    args = ap.parse_args(argv)
    out = args.out or default_out(args.input, args.theme, args.themes_root)
    if not args.dry_run and os.path.abspath(out) == os.path.abspath(args.input):
        print("ERROR: output must differ from input", file=sys.stderr)
        return 1
    if not args.pre:
        print("WARNING: no --pre - TopoDroid names not recovered, cSurvey targets only",
              file=sys.stderr)
    try:
        rep = theme_file(args.input, args.theme, args.pre, out, args.dry_run,
                         args.themes_root)
    except themes.ThemeError as e:
        print("ERROR: theme %s: %s" % (args.theme, e), file=sys.stderr)
        return 1
    except (OSError, ValueError, ET.ParseError, zipfile.BadZipFile) as e:
        print("ERROR: %s" % e, file=sys.stderr)
        return 1
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(rep, f, ensure_ascii=False, indent=1)
    print_report(rep)
    return 0


if __name__ == "__main__":
    sys.exit(main())
