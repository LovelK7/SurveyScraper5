#!/usr/bin/env python3
"""Split and normalise symbol-theme artwork for cSurvey (project 0007, task T1).

cSurvey's SVG parser (`cSurvey/cSurveyPC/cDrawPaths.vb`) reads a narrow subset:
path commands M L H V C S Q T Z (no arcs), g/path/polyline/polygon/line/circle/
rect (no ellipse, use, image, clip, mask), transforms only in a fragile form,
fill from `fill`/`style`/a CSS class, and nothing else of the styling. Every
non-`none` fill paints in the item's brush colour (pure white stays white) and
every shape is outlined with the item's pen (brief section 2.3/2.4).

  python theme_svg.py split <export.svg> <out_dir>
      Cut an Illustrator "Export As SVG" (Object IDs = Layer Names) into one
      normalised SVG per piece: layer `Znakovi` -> signs/, `Linije` -> lines/,
      `Plohe`/`Povrsine` -> areas/. Layers starting with `_` are skipped. Each
      direct child of a layer that carries an id is one piece. Writes
      <kind>/index.json (key -> filename) and report.json.
  python theme_svg.py normalize <in.svg> <out.svg> [--sign KEY]
      Normalise one whole file as one piece.
  python theme_svg.py check <file_or_dir>
      Report-only: what cSurvey would misread in each SVG. Exit 1 if any
      file has an error-level finding.

Normalisation: styles resolved (presentation attributes, `<style>` class/id/tag
rules, inline style, inheritance); transforms baked into coordinates; arcs ->
cubic Beziers; circle/ellipse/rect/line/polyline/polygon -> path; shapes with
neither fill nor stroke dropped; fills flattened to #FFFFFF (pure white) /
#000000 (anything else, gradients included) / none; strokes kept as geometry
with stroke="#000000" (widths reported, never outlined); image/use/text and
the like dropped; clip/mask/opacity ignored and reported. Output paths use
absolute M L C Q Z only, 3 decimals, geometry moved to the origin, viewBox =
the bounding box. Signs also get csurvey:sign (cSurvey SignEnum number, when
the key resolves) and csurvey:scale (size relative to the median sign).

Line units and area tiles also get their STROKES OUTLINED into filled geometry
(stroke width as drawn, butt caps, round joins): cSurvey paints a brush tile's
and a pen decoration's paths only by their fill (cBrush.vb:1821-1840,1982-2001;
cPen.vb:1096-1098), so a stroke-only path there would never print. Signs keep
their strokes - cSurvey draws those with the item pen (theme_apply.py turns the
pen on for a stroke-only glyph).

cSurvey fills every path even-odd (a GraphicsPath's default FillMode; nothing in
cDrawPaths.vb sets Winding), so the split warns about a path whose nested
contours wind the same way: the SVG (nonzero) fills such a hole, cSurvey does not.

Stdlib only.
"""

import argparse
import json
import math
import os
import re
import statistics
import sys
import xml.etree.ElementTree as ET

sys.dont_write_bytecode = True

SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"
CSURVEY_NS = "http://www.csurvey.it"

HERE = os.path.dirname(os.path.abspath(__file__))
CATALOG = os.path.join(HERE, "tdx-mapping-catalog.json")
MAPPING = os.path.join(HERE, "tdx-mapping.json")

LAYER_KINDS = {"znakovi": "signs", "linije": "lines",
               "plohe": "areas", "povrsine": "areas", "površine": "areas"}
KIND_SINGULAR = {"signs": "point", "lines": "line", "areas": "area"}

SHAPES = {"path", "rect", "circle", "ellipse", "line", "polyline", "polygon"}
CONTAINERS = {"g", "a", "switch"}
# Not rendered: definitions and metadata. Skipped silently.
NON_RENDERED = {"defs", "title", "desc", "metadata", "style", "linearGradient",
                "radialGradient", "clipPath", "mask", "pattern", "symbol",
                "marker", "filter", "script"}
# Rendered, but cSurvey cannot take them: dropped and reported.
REJECTED = {"image", "use", "text", "foreignObject", "video", "audio", "canvas",
            "iframe"}

INHERITED = ("fill", "stroke", "stroke-width", "fill-rule", "fill-opacity",
             "stroke-opacity", "visibility", "color")
STYLE_PROPS = INHERITED + ("opacity", "display", "clip-path", "mask", "filter")

EPS = 1e-9


# --------------------------------------------------------------------------
# small helpers

def local(tag):
    """Tag or attribute name without its namespace; None for comments/PIs."""
    if not isinstance(tag, str):
        return None
    return tag.rsplit("}", 1)[-1]


def in_svg_ns(tag):
    return isinstance(tag, str) and (tag.startswith("{%s}" % SVG_NS) or "}" not in tag)


_NUM = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")


def length(value, default=0.0):
    """Leading number of an SVG length ('3.5', '3.5px'); default if absent."""
    if value is None:
        return default
    m = _NUM.match(value.strip())
    return float(m.group(0)) if m else default


def fmt(v):
    s = "%.3f" % v
    s = s.rstrip("0").rstrip(".")
    return "0" if s in ("-0", "", "-") else s


def safe_filename(key):
    """Windows-safe file stem for a theme key (':' -> '@')."""
    s = key.replace(":", "@")
    s = re.sub(r'[<>"/\\|?*\x00-\x1f]', "_", s)
    s = s.rstrip(" .") or "_"
    if re.fullmatch(r"(?i)(con|prn|aux|nul|com\d|lpt\d)(\..*)?", s):
        s = "_" + s
    return s


def element_label(el):
    eid = el.get("id")
    return local(el.tag) + ("#" + eid if eid else "")


# --------------------------------------------------------------------------
# Illustrator ids

_HEX_ESC = re.compile(r"_x([0-9A-Fa-f]{2,6})_")
_SUFFIX = re.compile(r"^(.+?)-(\d+)$")


def decode_ai_id(raw):
    """Undo Illustrator's id escapes: `_x3A_` -> ':', `_x31_` -> '1' ..."""
    return _HEX_ESC.sub(lambda m: chr(int(m.group(1), 16)), raw)


def split_suffix(name):
    """('debris-2') -> ('debris', '2'); no suffix -> (name, None)."""
    m = _SUFFIX.match(name)
    if m:
        return m.group(1), m.group(2)
    return name, None


def is_unnamed(name):
    return not name or (name.startswith("<") and name.endswith(">"))


# --------------------------------------------------------------------------
# colours

_WHITE = {"#fff", "#ffffff", "#ffff", "#ffffffff", "white"}


def is_white(v):
    v = v.strip().lower().replace(" ", "")
    return v in _WHITE or v in ("rgb(255,255,255)", "rgb(100%,100%,100%)")


def is_black(v):
    v = v.strip().lower().replace(" ", "")
    return v in ("#000", "#000000", "black", "rgb(0,0,0)", "rgb(0%,0%,0%)")


def is_none(v):
    return v is None or v.strip().lower() in ("none", "transparent")


# --------------------------------------------------------------------------
# CSS and style resolution

def parse_decls(text):
    out = {}
    for part in (text or "").split(";"):
        if ":" in part:
            k, v = part.split(":", 1)
            k = k.strip().lower()
            v = v.strip()
            if v.endswith("!important"):
                v = v[:-10].strip()
            if k and v:
                out[k] = v
    return out


def parse_css(text):
    """[(selector, specificity, order, decls)] for simple selectors; plus a
    list of selectors the resolver does not understand."""
    text = re.sub(r"/\*.*?\*/", "", text or "", flags=re.S)
    text = text.replace("<![CDATA[", "").replace("]]>", "")
    rules, unsupported = [], []
    order = 0
    for m in re.finditer(r"([^{}]+)\{([^}]*)\}", text):
        decls = parse_decls(m.group(2))
        for sel in m.group(1).split(","):
            sel = sel.strip()
            if not sel:
                continue
            if re.fullmatch(r"\.[-\w]+", sel):
                spec = 2
            elif re.fullmatch(r"#[-\w]+", sel):
                spec = 3
            elif re.fullmatch(r"[a-zA-Z][-\w]*|\*", sel):
                spec = 1
            elif re.fullmatch(r"[a-zA-Z][-\w]*\.[-\w]+", sel):
                spec = 2
            else:
                unsupported.append(sel)
                continue
            rules.append((sel, spec, order, decls))
            order += 1
    return rules, unsupported


class StyleSheet:
    def __init__(self, root):
        self.rules = []
        self.unsupported = []
        self.style_elems = []
        for el in root.iter():
            if local(el.tag) == "style":
                self.style_elems.append(el)
                r, u = parse_css("".join(el.itertext()))
                base = len(self.rules)
                self.rules += [(s, sp, o + base, d) for s, sp, o, d in r]
                self.unsupported += u

    def matching(self, el):
        tag = local(el.tag)
        classes = set((el.get("class") or "").split())
        eid = el.get("id")
        hits = []
        for sel, spec, order, decls in self.rules:
            if sel == "*" or sel == tag:
                ok = True
            elif sel.startswith("."):
                ok = sel[1:] in classes
            elif sel.startswith("#"):
                ok = sel[1:] == eid
            elif "." in sel:
                t, c = sel.split(".", 1)
                ok = t == tag and c in classes
            else:
                ok = False
            if ok:
                hits.append((spec, order, decls))
        hits.sort(key=lambda h: (h[0], h[1]))
        return hits

    def specified(self, el):
        """Own declared properties: attributes < CSS rules < inline style."""
        out = {}
        for k in STYLE_PROPS:
            if el.get(k) is not None:
                out[k] = el.get(k).strip()
        for _, _, decls in self.matching(el):
            for k, v in decls.items():
                if k in STYLE_PROPS:
                    out[k] = v
        for k, v in parse_decls(el.get("style")).items():
            if k in STYLE_PROPS:
                out[k] = v
        return out


ROOT_STYLE = {"fill": "black", "stroke": "none", "stroke-width": "1",
              "fill-rule": "nonzero", "fill-opacity": "1",
              "stroke-opacity": "1", "visibility": "visible", "color": "black"}


def compute_style(parent_computed, specified):
    """Inherit the inheritable properties, then apply this element's own."""
    out = {k: parent_computed[k] for k in INHERITED}
    for k, v in specified.items():
        if v == "inherit":
            if k in INHERITED:
                continue
            v = parent_computed.get(k)
        if k in INHERITED:
            out[k] = v
        else:
            out[k] = v
    for k in ("opacity", "display", "clip-path", "mask", "filter"):
        out.setdefault(k, None)
    return out


# --------------------------------------------------------------------------
# transforms (a, b, c, d, e, f): x' = a x + c y + e, y' = b x + d y + f

IDENT = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


def mat_mul(m, n):
    """m . n (n applied first)."""
    a, b, c, d, e, f = m
    A, B, C, D, E, F = n
    return (a * A + c * B, b * A + d * B,
            a * C + c * D, b * C + d * D,
            a * E + c * F + e, b * E + d * F + f)


def apply(m, p):
    a, b, c, d, e, f = m
    x, y = p
    return (a * x + c * y + e, b * x + d * y + f)


_TF = re.compile(r"(matrix|translate|scale|rotate|skewX|skewY)\s*\(([^)]*)\)")


def parse_transform(text):
    """-> (matrix, [function names], skew_flag)."""
    m = IDENT
    names = []
    skew = False
    for name, args in _TF.findall(text or ""):
        v = [float(x) for x in _NUM.findall(args)]
        names.append(name)
        if name == "matrix" and len(v) == 6:
            t = tuple(v)
        elif name == "translate":
            t = (1, 0, 0, 1, v[0] if v else 0, v[1] if len(v) > 1 else 0)
        elif name == "scale":
            sx = v[0] if v else 1
            sy = v[1] if len(v) > 1 else sx
            t = (sx, 0, 0, sy, 0, 0)
        elif name == "rotate":
            r = math.radians(v[0] if v else 0)
            cs, sn = math.cos(r), math.sin(r)
            t = (cs, sn, -sn, cs, 0, 0)
            if len(v) >= 3:
                cx, cy = v[1], v[2]
                t = mat_mul(mat_mul((1, 0, 0, 1, cx, cy), t), (1, 0, 0, 1, -cx, -cy))
        elif name == "skewX":
            t = (1, 0, math.tan(math.radians(v[0] if v else 0)), 1, 0, 0)
            skew = True
        elif name == "skewY":
            t = (1, math.tan(math.radians(v[0] if v else 0)), 0, 1, 0, 0)
            skew = True
        else:
            continue
        m = mat_mul(m, t)
    return m, names, skew


def is_sheared(m):
    a, b, c, d, _, _ = m
    n1 = math.hypot(a, b)
    n2 = math.hypot(c, d)
    if n1 < EPS or n2 < EPS:
        return False
    return abs(a * c + b * d) / (n1 * n2) > 1e-6


def mat_scale(m):
    a, b, c, d, _, _ = m
    return math.sqrt(abs(a * d - b * c))


# --------------------------------------------------------------------------
# paths: internal segments ('M', p) ('L', p) ('C', p1, p2, p) ('Q', p1, p) ('Z',)

class PathError(ValueError):
    pass


class _Scan:
    def __init__(self, d):
        self.d = d or ""
        self.i = 0
        self.n = len(self.d)

    def skip(self):
        while self.i < self.n and self.d[self.i] in " \t\r\n,":
            self.i += 1

    def at_end(self):
        self.skip()
        return self.i >= self.n

    def at_number(self):
        self.skip()
        return self.i < self.n and self.d[self.i] in "+-.0123456789"

    def number(self):
        self.skip()
        m = _NUM.match(self.d, self.i)
        if not m:
            raise PathError("number expected at %d in %r" % (self.i, self.d[:60]))
        self.i = m.end()
        return float(m.group(0))

    def flag(self):
        self.skip()
        if self.i < self.n and self.d[self.i] in "01":
            self.i += 1
            return self.d[self.i - 1] == "1"
        raise PathError("arc flag expected at %d" % self.i)


def arc_to_cubics(p0, rx, ry, phi_deg, large, sweep, p1):
    """SVG endpoint arc -> list of ('C', c1, c2, end) (SVG 1.1 F.6.5/F.6.6)."""
    x1, y1 = p0
    x2, y2 = p1
    if abs(x1 - x2) < EPS and abs(y1 - y2) < EPS:
        return []
    rx, ry = abs(rx), abs(ry)
    if rx < EPS or ry < EPS:
        return [("L", p1)]
    phi = math.radians(phi_deg % 360.0)
    cp, sp = math.cos(phi), math.sin(phi)
    dx2, dy2 = (x1 - x2) / 2.0, (y1 - y2) / 2.0
    x1p = cp * dx2 + sp * dy2
    y1p = -sp * dx2 + cp * dy2
    lam = (x1p * x1p) / (rx * rx) + (y1p * y1p) / (ry * ry)
    if lam > 1:
        s = math.sqrt(lam)
        rx *= s
        ry *= s
    num = rx * rx * ry * ry - rx * rx * y1p * y1p - ry * ry * x1p * x1p
    den = rx * rx * y1p * y1p + ry * ry * x1p * x1p
    coef = math.sqrt(max(0.0, num / den)) if den > EPS else 0.0
    if large == sweep:
        coef = -coef
    cxp = coef * rx * y1p / ry
    cyp = -coef * ry * x1p / rx
    cx = cp * cxp - sp * cyp + (x1 + x2) / 2.0
    cy = sp * cxp + cp * cyp + (y1 + y2) / 2.0

    def ang(ux, uy, vx, vy):
        return math.atan2(ux * vy - uy * vx, ux * vx + uy * vy)

    ux, uy = (x1p - cxp) / rx, (y1p - cyp) / ry
    vx, vy = (-x1p - cxp) / rx, (-y1p - cyp) / ry
    th1 = ang(1, 0, ux, uy)
    dth = ang(ux, uy, vx, vy)
    if not sweep and dth > 0:
        dth -= 2 * math.pi
    elif sweep and dth < 0:
        dth += 2 * math.pi
    nseg = max(1, int(math.ceil(abs(dth) / (math.pi / 2) - 1e-9)))
    step = dth / nseg
    k = 4.0 / 3.0 * math.tan(step / 4.0)

    def pt(x, y):
        return (cx + rx * cp * x - ry * sp * y, cy + rx * sp * x + ry * cp * y)

    out = []
    t = th1
    for i in range(nseg):
        t2 = t + step
        c1, s1 = math.cos(t), math.sin(t)
        c2, s2 = math.cos(t2), math.sin(t2)
        q1 = pt(c1 - k * s1, s1 + k * c1)
        q2 = pt(c2 + k * s2, s2 - k * c2)
        end = p1 if i == nseg - 1 else pt(c2, s2)
        out.append(("C", q1, q2, end))
        t = t2
    return out


def parse_path(d, stats=None):
    """Path data -> absolute segments (M L C Q Z). Arcs become cubics;
    stats['arcs'] counts converted arc commands."""
    sc = _Scan(d)
    segs = []
    cur = (0.0, 0.0)
    start = (0.0, 0.0)
    last_c2 = None   # reflection point for S
    last_q = None    # reflection point for T
    cmd = None
    while not sc.at_end():
        ch = sc.d[sc.i]
        if ch.isalpha():
            cmd = ch
            sc.i += 1
            if cmd not in "MmZzLlHhVvCcSsQqTtAa":
                raise PathError("unknown path command %r" % cmd)
        elif cmd is None:
            raise PathError("path data must start with a command")
        elif cmd in "Zz":
            raise PathError("numbers after Z")
        elif cmd == "M":
            cmd = "L"
        elif cmd == "m":
            cmd = "l"
        rel = cmd.islower()
        C = cmd.upper()
        ox, oy = cur if rel else (0.0, 0.0)
        new_c2 = new_q = None
        if C == "Z":
            segs.append(("Z",))
            cur = start
        elif C == "M":
            p = (sc.number() + ox, sc.number() + oy)
            segs.append(("M", p))
            cur = start = p
        elif C == "L":
            p = (sc.number() + ox, sc.number() + oy)
            segs.append(("L", p))
            cur = p
        elif C == "H":
            p = (sc.number() + ox, cur[1])
            segs.append(("L", p))
            cur = p
        elif C == "V":
            p = (cur[0], sc.number() + oy)
            segs.append(("L", p))
            cur = p
        elif C == "C":
            c1 = (sc.number() + ox, sc.number() + oy)
            c2 = (sc.number() + ox, sc.number() + oy)
            p = (sc.number() + ox, sc.number() + oy)
            segs.append(("C", c1, c2, p))
            cur, new_c2 = p, c2
        elif C == "S":
            c1 = (2 * cur[0] - last_c2[0], 2 * cur[1] - last_c2[1]) if last_c2 else cur
            c2 = (sc.number() + ox, sc.number() + oy)
            p = (sc.number() + ox, sc.number() + oy)
            segs.append(("C", c1, c2, p))
            cur, new_c2 = p, c2
        elif C == "Q":
            q = (sc.number() + ox, sc.number() + oy)
            p = (sc.number() + ox, sc.number() + oy)
            segs.append(("Q", q, p))
            cur, new_q = p, q
        elif C == "T":
            q = (2 * cur[0] - last_q[0], 2 * cur[1] - last_q[1]) if last_q else cur
            p = (sc.number() + ox, sc.number() + oy)
            segs.append(("Q", q, p))
            cur, new_q = p, q
        elif C == "A":
            rx, ry, rot = sc.number(), sc.number(), sc.number()
            large, sweep = sc.flag(), sc.flag()
            p = (sc.number() + ox, sc.number() + oy)
            segs.extend(arc_to_cubics(cur, rx, ry, rot, large, sweep, p))
            if stats is not None:
                stats["arcs"] = stats.get("arcs", 0) + 1
            cur = p
        last_c2, last_q = new_c2, new_q
    return segs


def transform_segs(segs, m):
    out = []
    for s in segs:
        if s[0] == "Z":
            out.append(s)
        else:
            out.append((s[0],) + tuple(apply(m, p) for p in s[1:]))
    return out


def _cubic_extrema(a, b, c, d):
    """Parameter values in (0,1) where a 1-D cubic Bezier has extrema."""
    A = -a + 3 * b - 3 * c + d
    B = 2 * (a - 2 * b + c)
    C = b - a
    ts = []
    if abs(A) < 1e-12:
        if abs(B) > 1e-12:
            ts.append(-C / B)
    else:
        disc = B * B - 4 * A * C
        if disc >= 0:
            r = math.sqrt(disc)
            ts += [(-B + r) / (2 * A), (-B - r) / (2 * A)]
    return [t for t in ts if 0 < t < 1]


def _cubic_at(a, b, c, d, t):
    u = 1 - t
    return u * u * u * a + 3 * u * u * t * b + 3 * u * t * t * c + t * t * t * d


def bbox(segs):
    """Exact geometric bbox (x0, y0, x1, y1) or None."""
    xs, ys = [], []
    cur = None
    for s in segs:
        if s[0] in ("M", "L"):
            cur = s[1]
            xs.append(cur[0])
            ys.append(cur[1])
        elif s[0] == "C":
            p0, (c1, c2, p) = cur, s[1:]
            for i, arr in ((0, xs), (1, ys)):
                arr.append(p[i])
                for t in _cubic_extrema(p0[i], c1[i], c2[i], p[i]):
                    arr.append(_cubic_at(p0[i], c1[i], c2[i], p[i], t))
            cur = p
        elif s[0] == "Q":
            p0, (q, p) = cur, s[1:]
            for i, arr in ((0, xs), (1, ys)):
                arr.append(p[i])
                den = p0[i] - 2 * q[i] + p[i]
                if abs(den) > 1e-12:
                    t = (p0[i] - q[i]) / den
                    if 0 < t < 1:
                        arr.append((1 - t) ** 2 * p0[i] + 2 * (1 - t) * t * q[i] + t * t * p[i])
            cur = p
    if not xs:
        return None
    return (min(xs), min(ys), max(xs), max(ys))


def union(b1, b2):
    if b1 is None:
        return b2
    if b2 is None:
        return b1
    return (min(b1[0], b2[0]), min(b1[1], b2[1]), max(b1[2], b2[2]), max(b1[3], b2[3]))


def segs_to_d(segs):
    parts = []
    for s in segs:
        if s[0] == "Z":
            parts.append("Z")
        else:
            parts.append(s[0] + " " + " ".join(fmt(p[0]) + " " + fmt(p[1]) for p in s[1:]))
    return " ".join(parts)


def point_count(segs):
    return sum(len(s) - 1 for s in segs)


# --------------------------------------------------------------------------
# basic shapes -> segments

def _ellipse_segs(cx, cy, rx, ry):
    k = 4.0 / 3.0 * (math.sqrt(2) - 1)
    return [("M", (cx + rx, cy)),
            ("C", (cx + rx, cy + k * ry), (cx + k * rx, cy + ry), (cx, cy + ry)),
            ("C", (cx - k * rx, cy + ry), (cx - rx, cy + k * ry), (cx - rx, cy)),
            ("C", (cx - rx, cy - k * ry), (cx - k * rx, cy - ry), (cx, cy - ry)),
            ("C", (cx + k * rx, cy - ry), (cx + rx, cy - k * ry), (cx + rx, cy)),
            ("Z",)]


def _points(text):
    v = [float(x) for x in _NUM.findall(text or "")]
    return [(v[i], v[i + 1]) for i in range(0, len(v) - 1, 2)]


def shape_segs(el, stats):
    tag = local(el.tag)
    g = el.get
    if tag == "path":
        return parse_path(g("d"), stats)
    if tag == "rect":
        x, y = length(g("x")), length(g("y"))
        w, h = length(g("width")), length(g("height"))
        if w <= 0 or h <= 0:
            return []
        rx, ry = g("rx"), g("ry")
        rx = length(rx) if rx is not None else None
        ry = length(ry) if ry is not None else None
        if rx is None and ry is None:
            rx = ry = 0.0
        elif rx is None:
            rx = ry
        elif ry is None:
            ry = rx
        rx, ry = min(rx, w / 2), min(ry, h / 2)
        if rx <= 0 or ry <= 0:
            return [("M", (x, y)), ("L", (x + w, y)), ("L", (x + w, y + h)),
                    ("L", (x, y + h)), ("Z",)]
        k = 4.0 / 3.0 * (math.sqrt(2) - 1)
        kx, ky = k * rx, k * ry
        return [("M", (x + rx, y)), ("L", (x + w - rx, y)),
                ("C", (x + w - rx + kx, y), (x + w, y + ry - ky), (x + w, y + ry)),
                ("L", (x + w, y + h - ry)),
                ("C", (x + w, y + h - ry + ky), (x + w - rx + kx, y + h), (x + w - rx, y + h)),
                ("L", (x + rx, y + h)),
                ("C", (x + rx - kx, y + h), (x, y + h - ry + ky), (x, y + h - ry)),
                ("L", (x, y + ry)),
                ("C", (x, y + ry - ky), (x + rx - kx, y), (x + rx, y)), ("Z",)]
    if tag == "circle":
        r = length(g("r"))
        if r <= 0:
            return []
        return _ellipse_segs(length(g("cx")), length(g("cy")), r, r)
    if tag == "ellipse":
        rx, ry = g("rx"), g("ry")
        rx = length(rx) if rx is not None else None
        ry = length(ry) if ry is not None else None
        rx = ry if rx is None else rx
        ry = rx if ry is None else ry
        if not rx or not ry or rx <= 0 or ry <= 0:
            return []
        return _ellipse_segs(length(g("cx")), length(g("cy")), rx, ry)
    if tag == "line":
        return [("M", (length(g("x1")), length(g("y1")))),
                ("L", (length(g("x2")), length(g("y2"))))]
    if tag in ("polyline", "polygon"):
        pts = _points(g("points"))
        if not pts:
            return []
        segs = [("M", pts[0])] + [("L", p) for p in pts[1:]]
        if tag == "polygon":
            segs.append(("Z",))
        return segs
    return []


# --------------------------------------------------------------------------
# normalisation of one piece

class Piece:
    """Result of normalising one subtree."""

    def __init__(self, outline_strokes=False):
        self.outline_strokes = outline_strokes   # lines/areas: strokes -> fills
        self.paths = []          # (segs, fill, stroke_bool, fill_rule)
        self.fixed = {}          # counter name -> int
        self.rejected = []       # strings
        self.warnings = []       # strings
        self.strokes = []        # {"element", "stroke_width", "effective_width"}
        self.colours = set()     # non-black/white fill colours flattened
        self.gradients = 0
        self.src_points = 0

    def count(self, name, n=1):
        self.fixed[name] = self.fixed.get(name, 0) + n

    def bbox(self):
        b = None
        for segs, _, _, _ in self.paths:
            b = union(b, bbox(segs))
        return b

    def strays(self):
        """Indices of paths lying far outside the rest of the piece (a gap
        larger than the rest's own size) - usually a forgotten stray shape."""
        out = []
        boxes = [bbox(segs) for segs, _, _, _ in self.paths]
        if len(boxes) < 2:
            return out
        for i, bi in enumerate(boxes):
            rest = None
            for j, bj in enumerate(boxes):
                if j != i:
                    rest = union(rest, bj)
            size = max(rest[2] - rest[0], rest[3] - rest[1], bi[2] - bi[0], bi[3] - bi[1])
            gap = max(bi[0] - rest[2], rest[0] - bi[2], bi[1] - rest[3], rest[1] - bi[3])
            if size > 0 and gap > size:
                out.append(i)
        return out


def _walk(el, sheet, parent_style, ctm, opacity, piece, nested):
    tag = local(el.tag)
    if tag is None or not in_svg_ns(el.tag):
        return                      # comments, inkscape:/sodipodi: elements
    if tag in NON_RENDERED:
        return
    if tag in REJECTED:
        piece.rejected.append("%s dropped (cSurvey cannot use it)" % element_label(el))
        return
    spec = sheet.specified(el)
    style = compute_style(parent_style, spec)
    if (style.get("display") or "").strip() == "none":
        piece.warnings.append("%s has display:none - dropped" % element_label(el))
        return
    tf_text = el.get("transform")
    if tf_text:
        m, names, skew = parse_transform(tf_text)
        piece.count("transforms baked")
        if skew:
            piece.warnings.append("%s has a skew transform (baked)" % element_label(el))
        ctm = mat_mul(ctm, m)
    op = style.get("opacity")
    if op is not None:
        try:
            opacity *= float(op)
        except ValueError:
            pass
    for k in ("clip-path", "mask", "filter"):
        v = style.get(k)
        if v and not is_none(v):
            piece.rejected.append("%s %s ignored (geometry kept unclipped/unfiltered)"
                                  % (element_label(el), k))
    if tag in CONTAINERS or tag == "svg":
        if tag == "svg" and nested:
            piece.warnings.append("nested <svg> treated as a group (its viewport is ignored)")
        for child in el:
            _walk(child, sheet, style, ctm, opacity, piece, True)
        return
    if tag not in SHAPES:
        piece.rejected.append("%s dropped (unsupported element)" % element_label(el))
        return

    # --- a shape
    if style.get("visibility") in ("hidden", "collapse"):
        piece.count("hidden shapes dropped")
        return
    if opacity <= 0:
        piece.count("fully transparent shapes dropped")
        return
    fill = style["fill"]
    stroke = style["stroke"]
    try:
        if float(style.get("fill-opacity") or 1) <= 0:
            fill = "none"
    except ValueError:
        pass
    try:
        sw = length(style.get("stroke-width"), 1.0)
        if float(style.get("stroke-opacity") or 1) <= 0 or sw <= 0:
            stroke = "none"
    except ValueError:
        sw = 1.0
    if tag == "line":
        fill = "none"           # a line has no interior
    has_fill = not is_none(fill)
    has_stroke = not is_none(stroke)
    if not has_fill and not has_stroke:
        piece.count("invisible shapes dropped")
        return
    if opacity < 1:
        piece.rejected.append("%s opacity %s ignored (painted opaque)"
                              % (element_label(el), fmt(opacity)))

    stats = {}
    try:
        segs = shape_segs(el, stats)
    except PathError as e:
        piece.rejected.append("%s unreadable path data: %s" % (element_label(el), e))
        return
    if not any(s[0] in ("L", "C", "Q") for s in segs):
        piece.count("empty shapes dropped")
        return
    if stats.get("arcs"):
        piece.count("arcs converted", stats["arcs"])
    if tag != "path":
        piece.count("%s converted to path" % tag)
    if is_sheared(ctm):
        piece.warnings.append("%s: skewed/sheared transform baked" % element_label(el))
    piece.src_points += point_count(segs)
    segs = transform_segs(segs, ctm)

    if has_fill:
        if is_white(fill):
            out_fill = "#FFFFFF"
        else:
            out_fill = "#000000"
            if fill.strip().lower().startswith("url("):
                piece.gradients += 1
                piece.count("fills flattened")
            elif not is_black(fill):
                piece.colours.add(fill.strip().lower())
                piece.count("fills flattened")
    else:
        out_fill = "none"
    if has_stroke:
        piece.strokes.append({"element": element_label(el),
                              "stroke_width": sw,
                              "effective_width": round(sw * mat_scale(ctm), 4)})
    rule = (style.get("fill-rule") or "nonzero").strip()
    if has_stroke and piece.outline_strokes:
        ink = "#FFFFFF" if is_white(stroke) else "#000000"
        if ink == "#000000" and not is_black(stroke):
            piece.colours.add(stroke.strip().lower())
        if has_fill:
            piece.paths.append((segs, out_fill, False, rule))
        outl = outline_stroke(segs, sw * mat_scale(ctm))
        piece.paths += [(o, ink, False, "nonzero") for o in outl]
        piece.count("strokes outlined")
        return
    piece.paths.append((segs, out_fill, has_stroke, rule))


# --------------------------------------------------------------------------
# stroke outlining (line units, area tiles) and the even-odd check

def flatten(segs, steps=8):
    """segs -> [(points, closed)], curves sampled `steps` times."""
    out, pts, start, cur = [], [], None, None
    for s in segs:
        if s[0] == "M":
            if len(pts) > 1:
                out.append((pts, False))
            pts, start, cur = [s[1]], s[1], s[1]
        elif s[0] == "L":
            pts.append(s[1])
            cur = s[1]
        elif s[0] == "C":
            p0, (c1, c2, p) = cur, s[1:]
            for i in range(1, steps + 1):
                t = i / float(steps)
                pts.append((_cubic_at(p0[0], c1[0], c2[0], p[0], t),
                            _cubic_at(p0[1], c1[1], c2[1], p[1], t)))
            cur = p
        elif s[0] == "Q":
            p0, (q, p) = cur, s[1:]
            for i in range(1, steps + 1):
                t = i / float(steps)
                u = 1 - t
                pts.append((u * u * p0[0] + 2 * u * t * q[0] + t * t * p[0],
                            u * u * p0[1] + 2 * u * t * q[1] + t * t * p[1]))
            cur = p
        elif s[0] == "Z":
            if pts and start is not None:
                if math.hypot(pts[-1][0] - start[0], pts[-1][1] - start[1]) > EPS:
                    pts.append(start)
                if len(pts) > 2:
                    out.append((pts, True))
            pts, cur = [], start
    if len(pts) > 1:
        out.append((pts, False))
    return out


def outline_stroke(segs, width):
    """A stroke as filled polygons: one quad per segment (butt caps) plus a
    small octagon at every bend (round join). Each is its own path, so the
    overlaps never cancel under cSurvey's even-odd fill."""
    h = width / 2.0
    out = []
    for pts, closed in flatten(segs):
        clean = [pts[0]]
        for p in pts[1:]:
            if math.hypot(p[0] - clean[-1][0], p[1] - clean[-1][1]) > EPS:
                clean.append(p)
        if len(clean) < 2:
            continue
        dirs = []
        for a, b in zip(clean, clean[1:]):
            dx, dy = b[0] - a[0], b[1] - a[1]
            n = math.hypot(dx, dy)
            nx, ny = -dy / n * h, dx / n * h
            out.append([("M", (a[0] + nx, a[1] + ny)), ("L", (b[0] + nx, b[1] + ny)),
                        ("L", (b[0] - nx, b[1] - ny)), ("L", (a[0] - nx, a[1] - ny)), ("Z",)])
            dirs.append((dx / n, dy / n))
        joins = [(j, dirs[j - 1], dirs[j]) for j in range(1, len(clean) - 1)]
        if closed and len(dirs) > 1:
            joins.append((0, dirs[-1], dirs[0]))
        for j, d0, d1 in joins:
            if d0[0] * d1[0] + d0[1] * d1[1] > 0.9994:        # < 2 degrees: no gap to fill
                continue
            c = clean[j]
            ring = [(c[0] + h * math.cos(k * math.pi / 4), c[1] + h * math.sin(k * math.pi / 4))
                    for k in range(8)]
            out.append([("M", ring[0])] + [("L", q) for q in ring[1:]] + [("Z",)])
    return out


def _signed_area(pts):
    return sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(pts, pts[1:] + pts[:1])) / 2.0


def _poly_box(pts):
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return (min(xs), min(ys), max(xs), max(ys))


def evenodd_conflicts(piece):
    """Indices of filled nonzero paths with a contour nested in another that
    winds the same way: the SVG fills it, cSurvey (even-odd) leaves a hole."""
    bad = []
    for i, (segs, fill, _stroke, rule) in enumerate(piece.paths):
        if is_none(fill) or rule == "evenodd":
            continue
        rings = [(_poly_box(p), _signed_area(p)) for p, _c in flatten(segs, 4) if len(p) > 2]
        hit = False
        for a, (ba, sa) in enumerate(rings):
            for b, (bb, sb) in enumerate(rings):
                if a != b and abs(sa) > EPS and abs(sb) > EPS and (sa > 0) == (sb > 0) \
                        and ba[0] <= bb[0] and ba[1] <= bb[1] and ba[2] >= bb[2] \
                        and ba[3] >= bb[3]:
                    hit = True
        if hit:
            bad.append(i)
    return bad


def normalize_element(el, sheet, ancestors=(), outline_strokes=False):
    """Normalise el (with its ancestors' inherited style and transforms)."""
    piece = Piece(outline_strokes)
    style = dict(ROOT_STYLE)
    ctm = IDENT
    opacity = 1.0
    for anc in ancestors:
        spec = sheet.specified(anc)
        style = compute_style(style, spec)
        if anc.get("transform"):
            m, _, skew = parse_transform(anc.get("transform"))
            ctm = mat_mul(ctm, m)
            piece.count("transforms baked")
        op = style.get("opacity")
        if op is not None:
            try:
                opacity *= float(op)
            except ValueError:
                pass
        if (style.get("display") or "").strip() == "none":
            piece.warnings.append("an ancestor has display:none")
    _walk(el, sheet, style, ctm, opacity, piece, bool(ancestors))
    return piece


def render_svg(piece, sign=None, scale=None, title=None):
    """Minimal cSurvey-ready SVG text; geometry moved to the origin."""
    b = piece.bbox()
    if b is None:
        b = (0, 0, 0, 0)
    x0, y0 = b[0], b[1]
    shift = (1, 0, 0, 1, -x0, -y0)
    w, h = b[2] - b[0], b[3] - b[1]
    attrs = ['xmlns="%s"' % SVG_NS, 'xmlns:csurvey="%s"' % CSURVEY_NS,
             'viewBox="0 0 %s %s"' % (fmt(w), fmt(h))]
    if sign is not None:
        attrs.append('csurvey:sign="%d"' % sign)
    if scale is not None:
        attrs.append('csurvey:scale="%s"' % ("%.3f" % scale))
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             "<svg %s>" % " ".join(attrs)]
    if title:
        lines.append("  <title>%s</title>" % (title.replace("&", "&amp;").replace("<", "&lt;")))
    for segs, fill, stroke, rule in piece.paths:
        a = 'd="%s" fill="%s"' % (segs_to_d(transform_segs(segs, shift)), fill)
        if rule == "evenodd":
            a += ' fill-rule="evenodd"'
        if stroke:
            a += ' stroke="#000000"'
        lines.append("  <path %s/>" % a)
    lines.append("</svg>")
    return "\n".join(lines) + "\n"


_D_ATTR = re.compile(rb'(<path\b[^>]*?\sd=")([^"]*)(")')
_VIEWBOX = re.compile(rb'viewBox="[^"]*"')


def transform_svg(blob, m):
    """Apply matrix m to every <path d> of a normalised SVG (render_svg output),
    move the geometry back to the origin and refit the viewBox; everything else
    stays byte for byte."""
    found = [(mt, parse_path(mt.group(2).decode("ascii"))) for mt in _D_ATTR.finditer(blob)]
    if not found:
        raise ValueError("no <path d=...> in the glyph")
    turned = [transform_segs(segs, m) for _m, segs in found]
    box = None
    for segs in turned:
        box = union(box, bbox(segs))
    shift = (1, 0, 0, 1, -box[0], -box[1])
    out, pos = [], 0
    for (mt, _segs), segs in zip(found, turned):
        out += [blob[pos:mt.start(2)], segs_to_d(transform_segs(segs, shift)).encode("ascii")]
        pos = mt.end(2)
    out.append(blob[pos:])
    blob = b"".join(out)
    vb = ('viewBox="0 0 %s %s"' % (fmt(box[2] - box[0]), fmt(box[3] - box[1]))).encode("ascii")
    return _VIEWBOX.sub(lambda _m: vb, blob, count=1)


def flip_svg(blob):
    """Mirror a normalised unit top to bottom (across a horizontal line)."""
    return transform_svg(blob, (1, 0, 0, -1, 0, 0))


_DECL = re.compile(rb"<\?xml[^>]*\?>")
_TITLE = re.compile(rb"<title>.*?</title>", re.S)


def compact_svg(blob):
    """One-line SVG text for an inline <clipart data="..."/> (pen decoration,
    brush tile): no XML declaration, no title, no whitespace between tags -
    what cDrawClipArt keeps of a loaded file (XmlDocument.OuterXml without
    whitespace nodes, cDrawPaths.vb:153-161) and writes back verbatim
    (SaveTo, :191-196)."""
    blob = _TITLE.sub(b"", _DECL.sub(b"", blob))
    return re.sub(rb">\s+<", b"><", blob).strip().decode("utf-8")


def rotate_svg(blob, degrees):
    """Rotate a normalised glyph (render_svg output) by `degrees`, clockwise as
    drawn (SVG rotate(), y down), baked into the path coordinates; geometry
    moved back to the origin and the viewBox refitted. Everything else in the
    file is left byte for byte.

    cSurvey centres a sign glyph's bounding box on the item's point
    (cItemSign.vb:310-318) and only then turns it by the item's angle, so a
    rotation here is a pure change of direction. It cannot be done with
    csurvey:rotationangledelta: cSurvey keeps that attribute as clipart
    metadata (cItemSign.vb:73-80) but no render path reads it."""
    if not degrees or abs(degrees % 360.0) < 1e-9:
        return blob
    rot, _names, _skew = parse_transform("rotate(%r)" % float(degrees))
    return transform_svg(blob, rot)


# --------------------------------------------------------------------------
# sign number resolution

def load_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


class SignResolver:
    def __init__(self, catalog=None, mapping=None):
        catalog = catalog if catalog is not None else load_json(CATALOG)
        mapping = mapping if mapping is not None else load_json(MAPPING)
        # The catalog's point targets carry both the menu number ("num",
        # 1..N, what tdx-mapping.json and "natural" use) and cSurvey's
        # SignEnum value ("sign", cIItemSign.vb, what csurvey:sign must hold;
        # written by make_signs_catalog.py from its static SIGN_NAMES table).
        self.targets = {t["to"]: t["sign"] for t in catalog["targets"]["point"]}
        self.num_to_sign = {t["num"]: t["sign"] for t in catalog["targets"]["point"]}
        self.kind_names = {}
        for t in catalog.get("tdx", []):
            self.kind_names.setdefault(t["kind"], {})[t["name"]] = t
        for kind in ("line", "area"):
            for t in catalog["targets"].get(kind, []):
                self.kind_names.setdefault("target-" + kind, {})[t["to"]] = t
        self.points = mapping.get("points", {})

    def resolve(self, key):
        """-> (SignEnum value or None, how)."""
        if key in self.targets:
            return self.targets[key], "cSurvey sign name"
        tdx = self.kind_names.get("point", {}).get(key)
        if tdx is not None:
            entry = self.points.get(key) or {}
            to = entry.get("to")
            if to:
                if to in self.targets:
                    return self.targets[to], "TopoDroid %s -> %s (tdx-mapping.json)" % (key, to)
                return None, "TopoDroid %s maps to %s, which is no cSurvey sign" % (key, to)
            num = (tdx.get("natural") or {}).get("num")
            if num in self.num_to_sign:
                return self.num_to_sign[num], "TopoDroid %s, natural import" % key
            return None, "TopoDroid %s has no cSurvey sign (X-box)" % key
        return None, "not a cSurvey sign or TopoDroid point name"

    def known(self, kind, key):
        """Is key a TopoDroid or cSurvey name of that kind (lines/areas)?"""
        k = KIND_SINGULAR[kind]
        return key in self.kind_names.get(k, {}) or key in self.kind_names.get("target-" + k, {})


# --------------------------------------------------------------------------
# split

def parent_map(root):
    return {c: p for p in root.iter() for c in p}


def ancestors_of(el, parents):
    chain = []
    p = parents.get(el)
    while p is not None:
        chain.append(p)
        p = parents.get(p)
    return list(reversed(chain))


def _layer_kind(name):
    n = name.strip().lower()
    if n in LAYER_KINDS:
        return LAYER_KINDS[n]
    n2 = n.replace("š", "s")
    return LAYER_KINDS.get(n2)


def split(src, out_dir, resolver=None, quiet=False):
    tree = ET.parse(src)
    root = tree.getroot()
    sheet = StyleSheet(root)
    parents = parent_map(root)
    resolver = resolver or SignResolver()
    report = {"source": os.path.basename(src), "layers": [], "skipped_layers": [],
              "unnamed": [], "duplicates": [], "pieces": []}

    found = []   # (kind, key, raw_id, suffix, element)
    for layer in root:
        if local(layer.tag) != "g":
            continue
        lid = decode_ai_id(layer.get("data-name") or layer.get("id") or "")
        if lid.startswith("_"):
            report["skipped_layers"].append(lid)
            continue
        kind = _layer_kind(lid)
        if kind is None:
            report["skipped_layers"].append(lid or "<unnamed layer>")
            continue
        report["layers"].append({"layer": lid, "kind": kind})
        for child in layer:
            t = local(child.tag)
            if t is None or not in_svg_ns(child.tag) or t in NON_RENDERED:
                continue
            raw = child.get("id")
            name = decode_ai_id(child.get("data-name") or raw or "")
            idname = decode_ai_id(raw or "")
            base, suffix = split_suffix(idname)
            if child.get("data-name") is None:
                name = base
            elif idname == name:
                suffix = None      # Illustrator kept the name as the id
            if is_unnamed(name):
                report["unnamed"].append({"layer": lid, "element": t, "id": raw})
                continue
            found.append((kind, name, raw, suffix, child))

    seen = {}
    pieces = []
    for kind, key, raw, suffix, el in found:
        if (kind, key) in seen:
            report["duplicates"].append({"kind": kind, "key": key, "id": raw,
                                         "kept": seen[(kind, key)]})
            continue
        seen[(kind, key)] = raw
        piece = normalize_element(el, sheet, ancestors_of(el, parents),
                                  outline_strokes=kind in ("lines", "areas"))
        pieces.append((kind, key, raw, suffix, piece))

    # relative sign scale
    sizes = {}
    for kind, key, _, _, piece in pieces:
        b = piece.bbox()
        if b is not None:
            sizes[(kind, key)] = max(b[2] - b[0], b[3] - b[1])
    sign_sizes = [s for (k, _), s in sizes.items() if k == "signs" and s > 0]
    median = statistics.median(sign_sizes) if sign_sizes else None

    index = {}
    unresolved = []
    glyph_nums = set()
    for kind, key, raw, suffix, piece in pieces:
        entry = {"kind": kind, "key": key, "id": raw}
        sign = scale = None
        warnings = list(piece.warnings)
        if suffix:
            warnings.append("id %r: uniqueness suffix -%s stripped (layer fixes the kind)"
                            % (raw, suffix))
        if kind == "signs":
            sign, how = resolver.resolve(key)
            entry["sign"] = sign
            entry["sign_via"] = how
            if sign is None:
                unresolved.append(key)
                warnings.append("no csurvey:sign: %s (waits for T8)" % how)
            else:
                glyph_nums.add(sign)
            if median and sizes.get((kind, key)):
                scale = sizes[(kind, key)] / median
                entry["scale"] = round(scale, 3)
                if scale > 3 or scale < 1 / 3.0:
                    warnings.append("size %.1fx the median sign - check the group for stray shapes"
                                    % scale)
            if sign is not None:
                clash = [k for k2, k, _, _, _ in pieces
                         if k2 == "signs" and k != key and resolver.resolve(k)[0] == sign]
                if clash:
                    warnings.append("csurvey:sign %d is also claimed by %s (one glyph per cSurvey sign)"
                                    % (sign, ", ".join(clash)))
        elif not resolver.known(kind, key):
            warnings.append("key %r is not a known TopoDroid/cSurvey %s name"
                            % (key, KIND_SINGULAR[kind]))
        for i in piece.strays():
            warnings.append("path %d of %d lies far from the rest of the piece (stray shape?)"
                            % (i + 1, len(piece.paths)))
        for i in evenodd_conflicts(piece):
            warnings.append("path %d: nested contours wind the same way - the SVG fills the"
                            " inner one (nonzero), cSurvey leaves it a hole (even-odd)" % (i + 1))
        if kind == "signs" and piece.strokes and not any(
                not is_none(f) for _s, f, _st, _r in piece.paths):
            warnings.append("stroke-only glyph (no fills): theme_apply turns the outline pen on"
                            " for it; outline the strokes in Illustrator for the drawn width")
        b = piece.bbox()
        if not piece.paths:
            piece.rejected.append("nothing drawable left - no file written")
        else:
            fname = safe_filename(key) + ".svg"
            os.makedirs(os.path.join(out_dir, kind), exist_ok=True)
            with open(os.path.join(out_dir, kind, fname), "w", encoding="utf-8",
                      newline="\n") as fh:
                fh.write(render_svg(piece, sign, scale, title=key))
            index.setdefault(kind, {})[key] = fname
            entry["file"] = "%s/%s" % (kind, fname)
            entry["bbox"] = [round(b[2] - b[0], 3), round(b[3] - b[1], 3)]
        entry["paths_out"] = len(piece.paths)
        entry["points_in"] = piece.src_points
        entry["fixed"] = piece.fixed
        if piece.gradients:
            entry["gradients_flattened"] = piece.gradients
        if piece.colours:
            entry["colours_flattened"] = sorted(piece.colours)
        if piece.strokes:
            entry["strokes"] = piece.strokes
        entry["rejected"] = piece.rejected
        entry["warnings"] = warnings
        report["pieces"].append(entry)

    for kind, mapping in index.items():
        with open(os.path.join(out_dir, kind, "index.json"), "w", encoding="utf-8",
                  newline="\n") as fh:
            json.dump(mapping, fh, ensure_ascii=False, indent=2, sort_keys=True)
            fh.write("\n")
    report["sign_median_size"] = round(median, 3) if median else None
    report["unresolved_signs"] = unresolved
    report["targets_without_glyph"] = sorted(
        (n for n in resolver.targets if resolver.targets[n] not in glyph_nums),
        key=lambda n: resolver.targets[n])
    report["counts"] = {k: len(index.get(k, {})) for k in ("signs", "lines", "areas")}
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "report.json"), "w", encoding="utf-8",
              newline="\n") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    if not quiet:
        print_split_report(report)
    return report


def _stroke_summary(strokes):
    widths = {}
    for s in strokes:
        k = fmt(s["stroke_width"])
        widths[k] = widths.get(k, 0) + 1
    return ", ".join("%s x%d" % (w, n) for w, n in sorted(widths.items(), key=lambda x: float(x[0])))


def print_split_report(report):
    print("source: %s" % report["source"])
    for lay in report["layers"]:
        print("layer %-10s -> %s" % (lay["layer"], lay["kind"]))
    for s in report["skipped_layers"]:
        print("layer %-10s skipped" % s)
    for e in report["pieces"]:
        head = "%s/%s" % (e["kind"], e["key"])
        if "file" not in e:
            head += "  [NOT WRITTEN]"
        extra = []
        if e["kind"] == "signs":
            extra.append("sign=%s" % (e.get("sign") if e.get("sign") is not None else "-"))
            if "scale" in e:
                extra.append("scale=%.3f" % e["scale"])
        extra.append("%d paths" % e["paths_out"])
        print("\n%s  (%s)" % (head, ", ".join(extra)))
        if e["fixed"]:
            print("  fixed:    " + ", ".join("%s %d" % (k, v) for k, v in sorted(e["fixed"].items())))
        if e.get("gradients_flattened"):
            print("  flattened: %d gradient fill(s) -> #000000" % e["gradients_flattened"])
        if e.get("colours_flattened"):
            cols = e["colours_flattened"]
            print("  flattened: %d colour(s) -> #000000: %s%s"
                  % (len(cols), ", ".join(cols[:8]), " ..." if len(cols) > 8 else ""))
        if e.get("strokes"):
            how = ("outlined into fills" if e["kind"] in ("lines", "areas")
                   else "cSurvey uses its own pen")
            print("  strokes:  %d stroked shape(s), stroke-width %s (%s)"
                  % (len(e["strokes"]), _stroke_summary(e["strokes"]), how))
        for r in _collapse(e["rejected"]):
            print("  REJECTED: " + r)
        for w in _collapse(e["warnings"]):
            print("  warning:  " + w)
    print()
    for u in report["unnamed"]:
        print("UNNAMED %s on layer %s (id=%s) - not exported; name it in Illustrator"
              % (u["element"], u["layer"], u["id"]))
    for d in report["duplicates"]:
        print("DUPLICATE %s/%s (id=%s) - kept the first (id=%s)"
              % (d["kind"], d["key"], d["id"], d["kept"]))
    c = report["counts"]
    print("written: %d signs, %d lines, %d areas" % (c["signs"], c["lines"], c["areas"]))
    if report["unresolved_signs"]:
        print("signs without csurvey:sign (T8): " + ", ".join(report["unresolved_signs"]))
    print("cSurvey signs with no glyph in this export: %d" % len(report["targets_without_glyph"]))


def _collapse(msgs, limit=6):
    """Group repeated messages that differ only in the element label."""
    groups = {}
    order = []
    for m in msgs:
        k = re.sub(r"^\S+ ", "", m) if re.match(r"^[a-zA-Z]+(#\S*)? ", m) else m
        if k not in groups:
            groups[k] = []
            order.append(k)
        groups[k].append(m)
    out = []
    for k in order:
        g = groups[k]
        if len(g) == 1:
            out.append(g[0])
        else:
            out.append("%d x %s" % (len(g), k))
    return out[:limit] + (["... %d more" % (len(out) - limit)] if len(out) > limit else [])


# --------------------------------------------------------------------------
# normalize (one file)

def normalize_file(src, dst, key=None, resolver=None):
    root = ET.parse(src).getroot()
    sheet = StyleSheet(root)
    piece = normalize_element(root, sheet)
    sign = None
    if key:
        sign, how = (resolver or SignResolver()).resolve(key)
        if sign is None:
            piece.warnings.append("no csurvey:sign for %r: %s" % (key, how))
    d = os.path.dirname(os.path.abspath(dst))
    os.makedirs(d, exist_ok=True)
    with open(dst, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(render_svg(piece, sign, None, title=key))
    return piece


# --------------------------------------------------------------------------
# check (report-only)

def _cs_transform_problem(text):
    """What cSurvey's pSVGGetTransform would get wrong, or None."""
    t = text.strip()
    funcs = _TF.findall(t)
    if not funcs:
        return "unparsed transform %r" % t
    if any(n in ("skewX", "skewY") for n, _ in funcs):
        return "skew transform (cSurvey ignores skew)"
    if t.startswith("matrix("):
        if len(funcs) > 1:
            return "matrix() followed by more functions (cSurvey reads only the matrix)"
        if len(re.findall(r",", funcs[0][1])) != 5:
            return "matrix() arguments not comma-separated (cSurvey splits on ',')"
        return None
    for n, args in funcs:
        if re.search(r"\d\s+[-+.\d]", args.strip()):
            return "%s() arguments separated by spaces (cSurvey splits on ' ', loses it)" % n
    if len(funcs) > 1 and not all(n == "translate" for n, _ in funcs):
        return "transform list %r (cSurvey composes it in reverse order)" % t
    return None


def _translate_only(text):
    return all(n == "translate" for n, _ in _TF.findall(text or ""))


def check_file(path):
    """-> list of (level, message); level in error/warn/info."""
    issues = []
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as e:
        return [("error", "not well-formed XML: %s" % e)]
    if local(root.tag) != "svg":
        return [("error", "root element is <%s>, not <svg>" % local(root.tag))]
    sheet = StyleSheet(root)
    parents = parent_map(root)
    tally = {}

    def add(level, msg):
        tally.setdefault((level, msg), 0)
        tally[(level, msg)] += 1

    for sel in sheet.unsupported:
        add("warn", "CSS selector %r not understood (cSurvey reads '.class' rules only)" % sel)
    for st in sheet.style_elems:
        p = parents.get(st)
        if p is None or local(p.tag) != "defs" or parents.get(p) is not root:
            add("warn", "<style> outside the root <defs> (cSurvey reads only svg>defs>style)")
    if len(sheet.style_elems) > 1:
        add("warn", "%d <style> blocks (cSurvey reads the first)" % len(sheet.style_elems))
    clip_ids = set()
    for el in root.iter():
        t = local(el.tag)
        if t in ("clipPath", "mask") and el.get("id"):
            clip_ids.add(el.get("id"))
    referenced = set()

    shape_cache = {}

    def n_shapes(e):
        if e not in shape_cache:
            shape_cache[e] = sum(1 for x in e.iter() if local(x.tag) in SHAPES)
        return shape_cache[e]

    total_shapes = n_shapes(root)

    def walk(el, style, depth_tfs):
        t = local(el.tag)
        if t is None or not in_svg_ns(el.tag) or t in NON_RENDERED:
            return
        if t in REJECTED:
            add("warn" if t == "text" else "error",
                "<%s> %s" % (t, "drawn with a system font by cSurvey - convert to outlines"
                             if t == "text" else "is not drawn by cSurvey"))
            return
        spec = sheet.specified(el)
        st = compute_style(style, spec)
        tf = el.get("transform")
        if tf:
            prob = _cs_transform_problem(tf)
            if prob:
                add("error", prob)
            else:
                add("info", "transform (cSurvey reads this form)")
        for k in ("clip-path", "mask"):
            v = st.get(k)
            if v and not is_none(v):
                m = re.search(r"#([^)'\"]+)", v)
                if m:
                    referenced.add(m.group(1))
                add("error", "%s applied (cSurvey ignores it: unclipped geometry prints)" % k)
        op = st.get("opacity")
        if op is not None and length(op, 1) < 1:
            add("warn", "opacity < 1 (cSurvey paints opaque)")
        if (st.get("display") or "").strip() == "none":
            add("warn", "display:none element (cSurvey still draws it)")
        tfs = depth_tfs + [(el, tf) if tf else None]
        if t in CONTAINERS or t == "svg":
            for c in el:
                walk(c, st, tfs if t != "svg" or el is not root else [])
            return
        if t not in SHAPES:
            add("error", "<%s> is not drawn by cSurvey" % t)
            return
        # transforms cSurvey applies: own + direct parent group only, own after parent
        for anc_el, anc_tf in [x for x in depth_tfs[:-1] if x]:
            # lost by cSurvey; harmless only when it is a translate over the
            # whole drawing (cSurvey moves the drawing to its bbox anyway)
            if _translate_only(anc_tf) and n_shapes(anc_el) == total_shapes:
                add("info", "translate on an outer group, lost by cSurvey but harmless (whole drawing)")
            else:
                add("error", "transform on a grand-parent group (cSurvey applies only the direct parent's)")
        if depth_tfs and depth_tfs[-1] and tf and not (
                _translate_only(tf) and _translate_only(depth_tfs[-1][1])):
            add("error", "transform on both shape and its group (cSurvey applies them in the wrong order)")
        if t == "ellipse":
            add("error", "<ellipse> is not drawn by cSurvey")
        if t == "path":
            d = el.get("d") or ""
            if re.search(r"[Aa]", d):
                add("error", "path with arc commands (cSurvey has no arc case)")
            try:
                parse_path(d)
            except PathError as e:
                add("error", "unreadable path data: %s" % e)
        if t == "rect" and (el.get("rx") or el.get("ry")):
            add("warn", "rounded <rect> (cSurvey draws square corners)")
        fill, stroke = st["fill"], st["stroke"]
        sw = length(st.get("stroke-width"), 1.0)
        no_fill = is_none(fill) or t == "line"
        no_stroke = is_none(stroke) or sw <= 0
        if no_fill and no_stroke:
            add("warn", "invisible shape (no fill, no stroke) - cSurvey outlines it with the pen")
        if not no_fill:
            if fill.strip().lower().startswith("url("):
                add("warn", "gradient/pattern fill (cSurvey paints it solid in the item colour)")
            elif not (is_white(fill) or is_black(fill)):
                colours.add(fill.strip().lower())
            # cSurvey's own fill lookup: own class/fill/style, else direct parent's, else none
            if _cs_fill(el, parents.get(el), sheet) is None:
                add("warn", "fill only inherited/defaulted (browsers fill it; cSurvey leaves it unfilled)")
        if not no_stroke:
            widths[fmt(sw)] = widths.get(fmt(sw), 0) + 1

    colours = set()
    widths = {}
    walk(root, dict(ROOT_STYLE), [])
    if colours:
        add("info", "%d fill colour(s) other than black/white, painted in the item colour: %s"
            % (len(colours), ", ".join(sorted(colours))))
    if widths:
        add("info", "%d stroked shape(s), stroke-width %s (cSurvey uses its own pen)"
            % (sum(widths.values()), ", ".join("%s x%d" % kv for kv in
                                               sorted(widths.items(), key=lambda x: float(x[0])))))
    for cid in sorted(clip_ids - referenced):
        add("info", "unreferenced clipPath/mask definition (harmless)")
    for (level, msg), n in sorted(tally.items(), key=lambda x: ("error", "warn", "info").index(x[0][0])):
        issues.append((level, msg if n == 1 else "%s  [x%d]" % (msg, n)))
    return issues


def _own_fill(el, sheet):
    """Fill as cSurvey's pProcessStyle sees it on one element (None = unset)."""
    if el is None:
        return None
    if el.get("class"):
        fill = None
        for _, _, decls in sheet.matching(el):
            fill = decls.get("fill", fill)
        return fill
    st = parse_decls(el.get("style"))
    if "fill" in st:
        return st["fill"]
    return el.get("fill")


def _cs_fill(el, parent, sheet):
    own = _own_fill(el, sheet)
    if own is not None:
        return own
    if el.get("class") or el.get("style") or el.get("fill") is not None:
        return None
    return _own_fill(parent, sheet)


def check(target):
    files = []
    if os.path.isdir(target):
        for dp, _, fns in os.walk(target):
            files += [os.path.join(dp, f) for f in sorted(fns) if f.lower().endswith(".svg")]
    else:
        files = [target]
    n_err = n_warn = 0
    for f in sorted(files):
        issues = check_file(f)
        errs = [m for lv, m in issues if lv == "error"]
        warns = [m for lv, m in issues if lv == "warn"]
        n_err += bool(errs)
        n_warn += bool(warns) and not errs
        status = "ERROR" if errs else ("warn" if warns else "ok")
        print("%-5s %s" % (status, os.path.relpath(f, target) if os.path.isdir(target) else f))
        for lv, m in issues:
            print("      %-5s %s" % (lv, m))
    print("\n%d file(s): %d with errors, %d with warnings only"
          % (len(files), n_err, n_warn))
    return 1 if n_err else 0


# --------------------------------------------------------------------------

def main(argv=None):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("split", help="cut an Illustrator export into normalised pieces")
    p.add_argument("export")
    p.add_argument("out_dir")
    p = sub.add_parser("normalize", help="normalise one SVG")
    p.add_argument("src")
    p.add_argument("dst")
    p.add_argument("--sign", metavar="KEY", help="theme key to resolve csurvey:sign for")
    p = sub.add_parser("check", help="report what cSurvey would misread (no writes)")
    p.add_argument("target")
    a = ap.parse_args(argv)
    if a.cmd == "split":
        rep = split(a.export, a.out_dir)
        return 0 if rep["pieces"] else 1
    if a.cmd == "normalize":
        piece = normalize_file(a.src, a.dst, a.sign)
        print("%s: %d paths; fixed %s" % (a.dst, len(piece.paths), piece.fixed))
        for r in _collapse(piece.rejected):
            print("  REJECTED: " + r)
        for w in _collapse(piece.warnings):
            print("  warning:  " + w)
        if piece.strokes:
            print("  strokes: %d (%s)" % (len(piece.strokes), _stroke_summary(piece.strokes)))
        return 0
    return check(a.target)


if __name__ == "__main__":
    sys.exit(main())
