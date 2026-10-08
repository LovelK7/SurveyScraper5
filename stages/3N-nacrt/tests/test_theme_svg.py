"""theme_svg — split / normalise / check symbol-theme SVGs (project 0007, T1)."""

import json
import math
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1] / "production" / "tools"
sys.path.insert(0, str(TOOLS))

import theme_svg as ts  # noqa: E402

SVG = 'xmlns="http://www.w3.org/2000/svg"'


def _cubic_points(p0, c1, c2, p, n=9):
    for i in range(n + 1):
        t = i / n
        u = 1 - t
        yield tuple(u ** 3 * p0[k] + 3 * u * u * t * c1[k] + 3 * u * t * t * c2[k] + t ** 3 * p[k]
                    for k in (0, 1))


def _piece(body, defs=""):
    root = ET.fromstring('<svg %s>%s%s</svg>' % (SVG, defs, body))
    return ts.normalize_element(root, ts.StyleSheet(root))


# --- arcs ----------------------------------------------------------------

@pytest.mark.parametrize("d", [
    "M 15 10 A 5 5 0 1 1 5 10",            # half circle
    "M 15 10 A 5 5 0 1 1 10 5",            # three quarters (large, sweep)
    "M15,10a5,5,0,0,1-5,5",                # relative, compact
    "M15 10a5 5 0 105 0",                  # packed flags: 15,10 -> 20,10 on r 5
])
def test_arc_to_cubic_stays_on_circle(d):
    segs = ts.parse_path(d)
    assert segs[0][0] == "M"
    assert all(s[0] in ("M", "C") for s in segs)
    cur = segs[0][1]
    # centre of the circle the arc lies on: first case 10,10, r 5;
    # the packed case has its own centre, derive it from the endpoints.
    if d.endswith("105 0"):
        # chord 5 on r 5, large arc, sweep 0: centre below the chord
        centre, r = (17.5, 10.0 + math.sqrt(25 - 6.25)), 5.0
    else:
        centre, r = (10.0, 10.0), 5.0
    for s in segs[1:]:
        for x, y in _cubic_points(cur, s[1], s[2], s[3]):
            # 90-degree cubic segments: radial error <= 2.7e-4 r (standard kappa)
            assert abs(math.hypot(x - centre[0], y - centre[1]) - r) < 1e-3 * r
        cur = s[3]


def test_arc_endpoint_exact():
    segs = ts.parse_path("M 0 0 A 10 4 30 0 1 7 3")
    assert segs[-1][3] == (7.0, 3.0)


def test_circle_and_ellipse_become_cubic_paths():
    p = _piece('<circle cx="10" cy="10" r="5"/><ellipse cx="0" cy="0" rx="4" ry="2" fill="#fff"/>')
    out = ts.render_svg(p)
    assert "<circle" not in out and "<ellipse" not in out
    assert p.fixed["circle converted to path"] == 1
    assert p.fixed["ellipse converted to path"] == 1
    for segs, _, _, _ in p.paths:
        assert {s[0] for s in segs} <= {"M", "C", "Z"}
    assert [f for _, f, _, _ in p.paths] == ["#000000", "#FFFFFF"]


# --- transforms ----------------------------------------------------------

def test_nested_translate_rotate_baked():
    p = _piece('<g transform="translate(10 0)"><g transform="rotate(90)">'
               '<path d="M 0 0 L 1 0"/></g></g>')
    segs = p.paths[0][0]
    assert segs[0][1] == pytest.approx((10, 0))
    assert segs[1][1] == pytest.approx((10, 1))
    out = ts.render_svg(p)
    assert "transform" not in out


def test_rotate_about_point_and_matrix():
    m, names, skew = ts.parse_transform("rotate(180, 5, 5) matrix(1,0,0,1,1,0)")
    assert ts.apply(m, (0, 0)) == pytest.approx((9, 10))
    assert not skew
    _, _, skew = ts.parse_transform("skewX(10)")
    assert skew


# --- ids ----------------------------------------------------------------

def test_decode_ids():
    assert ts.decode_ai_id("slope_x3A_steep") == "slope:steep"
    assert ts.decode_ai_id("_x31_23") == "123"
    assert ts.decode_ai_id("a_x20_b") == "a b"
    assert ts.split_suffix("debris-2") == ("debris", "2")
    assert ts.split_suffix("plus-minus") == ("plus-minus", None)
    assert ts.is_unnamed(ts.decode_ai_id("_x3C_Group_x3E_"))


def test_safe_filename():
    assert ts.safe_filename("slope:steep") == "slope@steep"
    assert ts.safe_filename("water-flow:intermittent") == "water-flow@intermittent"
    assert ts.safe_filename('a<b>?*|"') == "a_b_____"
    assert ts.safe_filename("con") == "_con"


# --- fills / invisible / strokes ---------------------------------------

def test_invisible_rect_dropped():
    p = _piece('<rect x="0.5" y="0" width="30" height="30" fill="none"/>'
               '<rect x="40" y="0" width="2" height="2"/>')
    assert len(p.paths) == 1
    assert p.fixed["invisible shapes dropped"] == 1
    assert p.bbox() == pytest.approx((40, 0, 42, 2))


def test_fill_flattening_and_gradients():
    defs = '<defs><linearGradient id="g"><stop offset="0" stop-color="red"/></linearGradient></defs>'
    p = _piece('<path d="M0 0L1 0L1 1Z" fill="#ff0000"/>'
               '<path d="M0 0L1 0L1 1Z" fill="url(#g)"/>'
               '<path d="M0 0L1 0L1 1Z" fill="#FFF"/>'
               '<path d="M0 0L1 0L1 1Z" style="fill:white"/>'
               '<path d="M0 0L1 0L1 1Z" fill="black"/>', defs)
    assert [f for _, f, _, _ in p.paths] == ["#000000", "#000000", "#FFFFFF", "#FFFFFF", "#000000"]
    assert p.gradients == 1
    assert p.colours == {"#ff0000"}
    assert p.fixed["fills flattened"] == 2


def test_css_class_and_strokes_reported():
    defs = '<defs><style>.fil0 {fill:none} .str0 {stroke:#1F1A17;stroke-width:0.2}</style></defs>'
    p = _piece('<g transform="scale(2)"><polyline class="fil0 str0" points="0 0 1 1 2 0"/></g>', defs)
    assert len(p.paths) == 1
    segs, fill, stroke, _ = p.paths[0]
    assert fill == "none" and stroke
    assert p.strokes[0]["stroke_width"] == 0.2
    assert p.strokes[0]["effective_width"] == pytest.approx(0.4)
    assert 'stroke="#000000"' in ts.render_svg(p)


def test_rejected_elements_and_opacity():
    p = _piece('<text>x</text><image href="a.png"/><use href="#a"/>'
               '<path d="M0 0L1 1L0 1Z" opacity="0.5" clip-path="url(#c)"/>')
    assert len(p.paths) == 1
    joined = " ".join(p.rejected)
    for word in ("text", "image", "use", "opacity", "clip-path"):
        assert word in joined


def test_output_only_allowed_commands():
    p = _piece('<path d="M0 0 h5 v5 s1 1 2 2 q1 1 2 0 t 2 0 a2 2 0 0 1 4 0 z"/>')
    d = re.findall(r'd="([^"]*)"', ts.render_svg(p))[0]
    assert set(re.findall(r"[A-Za-z]", d)) <= set("MLCQZ")


import re  # noqa: E402


# --- signs ---------------------------------------------------------------

@pytest.fixture(scope="module")
def resolver():
    return ts.SignResolver()


def test_sign_resolution(resolver):
    # csurvey:sign is cSurvey's SignEnum value (cIItemSign.vb), never the
    # catalog's menu number (stalagmite 10, blocks 53, breakdownchoke 5).
    assert resolver.resolve("stalagmite")[0] == 517
    assert resolver.resolve("blocks")[0] == 1290
    num, how = resolver.resolve("debris")         # TopoDroid -> breakdownchoke
    assert num == 261 and "breakdownchoke" in how
    assert resolver.resolve("air-draught")[0] == 774  # TopoDroid natural import
    assert resolver.resolve("no-such-symbol")[0] is None
    assert resolver.resolve("bones")[0] is None


def test_sign_values_match_gallery_svgs(resolver):
    """Every catalog "sign" equals the csurvey:sign of that target's gallery SVG."""
    import re
    cat = json.loads((TOOLS / "tdx-mapping-catalog.json").read_text(encoding="utf-8"))
    for t in cat["targets"]["point"]:
        m = re.search(r'csurvey:sign="(\d+)"', t["svg"])
        assert m and int(m.group(1)) == t["sign"] == resolver.targets[t["to"]], t["to"]


# --- split end-to-end ------------------------------------------------------

EXPORT = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200">
  <g id="Znakovi">
    <g id="stalagmite"><path d="M0 0 L10 0 L5 10 Z" transform="translate(10 10)"/></g>
    <g id="debris"><ellipse cx="50" cy="50" rx="10" ry="5" fill="#c00"/></g>
    <g id="no-such-symbol"><rect x="0" y="0" width="40" height="40" fill="none" stroke="#000"/></g>
    <g><path d="M0 0L1 1Z"/></g>
  </g>
  <g id="Linije"><polygon id="slope_x3A_steep" points="0 0 2 0 1 3"/></g>
  <g id="Površine"><g id="debris-2" data-name="debris"><circle cx="5" cy="5" r="2"/>
    <rect x="0.5" y="0.5" width="99" height="99" fill="none"/></g></g>
  <g id="_notes"><path d="M0 0L5 5Z"/></g>
</svg>"""


def test_split(tmp_path):
    src = tmp_path / "symbols.svg"
    src.write_text(EXPORT, encoding="utf-8")
    out = tmp_path / "out"
    rep = ts.split(str(src), str(out), quiet=True)
    assert rep["counts"] == {"signs": 3, "lines": 1, "areas": 1}
    assert rep["skipped_layers"] == ["_notes"]
    assert len(rep["unnamed"]) == 1
    assert json.loads((out / "lines" / "index.json").read_text())["slope:steep"] == "slope@steep.svg"
    assert (out / "areas" / "debris.svg").exists()
    stal = (out / "signs" / "stalagmite.svg").read_text()
    assert 'csurvey:sign="517"' in stal and 'xmlns:csurvey="http://www.csurvey.it"' in stal
    assert "csurvey:scale=" in stal
    unknown = (out / "signs" / "no-such-symbol.svg").read_text()
    assert "csurvey:sign" not in unknown
    assert rep["unresolved_signs"] == ["no-such-symbol"]
    area = [p for p in rep["pieces"] if p["kind"] == "areas"][0]
    assert area["key"] == "debris" and area["fixed"]["invisible shapes dropped"] == 1
    assert any("-2" in w for w in area["warnings"])
    # scale: max dims 10, 20 (ellipse), 40 -> median 20
    scales = {p["key"]: p.get("scale") for p in rep["pieces"] if p["kind"] == "signs"}
    assert scales == {"stalagmite": 0.5, "debris": 1.0, "no-such-symbol": 2.0}
    for f in (out / "signs").glob("*.svg"):
        text = f.read_text()
        assert "<ellipse" not in text and "transform" not in text
        assert ts.check_file(str(f)) == [] or all(lv == "info" for lv, _ in ts.check_file(str(f)))


def test_check_flags_cs_problems(tmp_path):
    f = tmp_path / "bad.svg"
    f.write_text('<svg %s><g transform="translate(1 2)"><path d="M0 0 a1 1 0 0 1 2 0"/>'
                 '<ellipse cx="0" cy="0" rx="1" ry="2"/></g>'
                 '<rect width="5" height="5" fill="none"/></svg>' % SVG)
    issues = ts.check_file(str(f))
    errs = " ".join(m for lv, m in issues if lv == "error")
    warns = " ".join(m for lv, m in issues if lv == "warn")
    assert "arc" in errs and "ellipse" in errs and "spaces" in errs
    assert "invisible" in warns
    assert ts.check(str(f)) == 1


def test_rotate_svg_bakes_rotation_and_refits_viewbox():
    blob = (b'<?xml version="1.0" encoding="UTF-8"?>\n<svg xmlns="http://www.w3.org/2000/svg" '
            b'xmlns:csurvey="http://www.csurvey.it" viewBox="0 0 4 1" csurvey:sign="774" '
            b'csurvey:scale="1.2">\n  <title>t</title>\n'
            b'  <path d="M 0 0 L 4 0 L 4 1 Z" fill="#000000"/>\n</svg>\n')
    r90 = ts.rotate_svg(blob, 90)                       # clockwise as drawn (y down)
    assert b'viewBox="0 0 1 4"' in r90
    assert b'd="M 1 0 L 1 4 L 0 4 Z"' in r90
    assert b'csurvey:sign="774" csurvey:scale="1.2"' in r90 and b"<title>t</title>" in r90
    assert ts.rotate_svg(ts.rotate_svg(blob, 180), 180) == blob
    assert ts.rotate_svg(blob, 0) is blob and ts.rotate_svg(blob, 360) is blob


# --- phase 2: strokes outlined for lines/areas, even-odd, flip, compact ----

def test_area_and_line_strokes_outlined_into_fills():
    root = ET.fromstring('<svg %s><polyline points="0 0 10 0 10 10" fill="none" '
                         'stroke="#616262" stroke-width="2"/></svg>' % SVG)
    sign = ts.normalize_element(root, ts.StyleSheet(root))
    assert len(sign.paths) == 1 and sign.paths[0][1] == "none"        # signs keep the stroke
    area = ts.normalize_element(root, ts.StyleSheet(root), outline_strokes=True)
    assert area.fixed["strokes outlined"] == 1
    assert len(area.paths) == 3                       # two segment quads + one round join
    assert all(f == "#000000" and not st for _s, f, st, _r in area.paths)
    b = area.bbox()
    assert b == pytest.approx((0, -1, 11, 10))        # butt caps, width 2


def test_evenodd_conflict_reported():
    same = "M 0 0 L 10 0 L 10 10 L 0 10 Z M 2 2 L 8 2 L 8 8 L 2 8 Z"     # both clockwise
    opp = "M 0 0 L 10 0 L 10 10 L 0 10 Z M 2 2 L 2 8 L 8 8 L 8 2 Z"      # a proper hole
    assert ts.evenodd_conflicts(_piece('<path d="%s"/>' % same)) == [0]
    assert ts.evenodd_conflicts(_piece('<path d="%s"/>' % opp)) == []
    assert ts.evenodd_conflicts(_piece('<path d="%s" fill-rule="evenodd"/>' % same)) == []


def test_flip_and_compact_svg():
    blob = (b'<?xml version="1.0" encoding="UTF-8"?>\n<svg xmlns="http://www.w3.org/2000/svg" '
            b'viewBox="0 0 2 3">\n  <title>t</title>\n  <path d="M 0 3 L 1 0 L 2 3 Z" '
            b'fill="#000000"/>\n</svg>\n')
    flipped = ts.flip_svg(blob)
    assert b'd="M 0 0 L 1 3 L 2 0 Z"' in flipped and b'viewBox="0 0 2 3"' in flipped
    c = ts.compact_svg(flipped)
    assert c.startswith("<svg ") and "\n" not in c and "<title>" not in c and "<?xml" not in c


def test_filled_polyline_is_closed():
    # r10: open filled polylines (blocks tile) printed hollow in cSurvey
    segs = [("M", (0, 0)), ("L", (1, 0)), ("L", (1, 1)), ("M", (5, 5)), ("L", (6, 5)), ("Z",)]
    out = ts.close_subpaths(segs)
    assert out == [("M", (0, 0)), ("L", (1, 0)), ("L", (1, 1)), ("Z",),
                   ("M", (5, 5)), ("L", (6, 5)), ("Z",)]
