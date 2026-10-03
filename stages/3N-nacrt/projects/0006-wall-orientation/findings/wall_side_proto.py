"""Prototype: which side of each drawn wall is the cave? (project 0006)

The interior protocol, in one line: **the survey is inside the cave.** Every
in-cave leg and every splay (up to just short of its tip, which lies on the
wall) was shot through open space, so points sampled along them are known
interior. A wall sequence's interior side is the side those samples are on,
as seen from the wall:

  for every ~SAMPLE_STEP of wall
      take the nearest interior samples, keep the first one the wall point can
      SEE (the sight line crosses no other drawn wall - otherwise a parallel
      passage behind the rock would vote), and vote left or right of the
      wall's local direction, weighted by length / (REF + distance)
  score = signed vote share in [-1, +1]: +1 = cave on the left all along

Left/right is in the drawing's own frame (x right, y DOWN - cSurvey design
coordinates, plan and profile alike), i.e. as the operator sees it on screen.

The orienting rule then follows from how cSurvey fills a Borders item: it
strokes each B-sequence but fills the item as ONE polygon, joining the end of
each sequence to the start of the next (cItemFreeHandArea.vb:193-195). With
every wall running the same way round the cave (cave on the same side), those
joins close mouths and gaps; one wall running the other way makes the join
cross the passage (Golobreška profile, 2026-10-03).

Usage:  python wall_side_proto.py <survey.csx|.csz> [...] [--png]
"""
import json, math, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "production", "tools"))
import xml.etree.ElementTree as ET
import nacrt_finish as nf

LAYER_BORDERS = nf.LAYER_BORDERS
AREA_TYPE = "4"              # cItemFreeHandArea in the Borders layer (the walls)
SAMPLE_STEP = 0.10           # m between interior samples along legs/splays
SPLAY_KEEP = 0.85            # use a splay up to this fraction: its tip lies ON the wall
WALL_STEP = 0.15             # m between voting points along a wall
MAX_SIGHT = 8.0              # m; a wall further than this from any survey has no vote
CANDIDATES = 12              # nearest interior samples tried per wall point
REF = 0.3                    # m; vote weight = length / (REF + distance)
LEG_WEIGHT = 3.0             # a leg sample outvotes a splay sample: legs are never outside
TIP_TOL = 0.5                # m; an uncut splay counts only if its tip lands this close to a wall
GRID = 0.5                   # m spatial-hash cell


def load(path):
    if path.lower().endswith(".csz"):
        import zipfile
        with zipfile.ZipFile(path) as z:
            return ET.fromstring(z.read(nf.DATA_ENTRY))
    return ET.parse(path).getroot()


# ---------------------------------------------------------------------------
# the interior: legs and splays from <calculate>


def _xy(p, design):
    return (float(p.get("x")), float(p.get("y"))) if design == "plan" else (float(p.get("d")), float(p.get("z")))


def survey_lines(root, design):
    """[(kind, a, b)] in design coordinates: kind 'leg' or 'splay'.

    Each <t> lists, per connection, ITS OWN position in that connection's
    context (<tcon n=other><p>) - in the profile a station has one d per
    connection, so a leg a-b runs from t[a].tcon[b] to t[b].tcon[a].
    """
    calc = root.find("calculate/ts")
    if calc is None:
        return []
    skip = set()
    for seg in root.find("segments").findall("segment"):
        if seg.get("splay") == "1":
            continue
        if any(seg.get(f) == "1" for f in nf.NOT_IN_CAVE_FLAGS):
            skip.add(frozenset((seg.get("from"), seg.get("to"))))
    pos = {}
    for t in calc.findall("t"):
        n = t.get("n") or ""
        for tc in t.findall("tcons/tcon"):
            p = tc.find("p")
            if p is not None:
                pos[(n, tc.get("n"))] = (_xy(p, design), (float(p.get("x")), float(p.get("y")), float(p.get("z"))))
    out, seen = [], set()
    for (a, b), pa in pos.items():
        key = frozenset((a, b))
        if key in seen or (b, a) not in pos:
            continue
        seen.add(key)
        (pa, qa), (pb, qb) = pos[(a, b)], pos[(b, a)]
        # plan: a steep shot's projection crosses other levels' walls (Sopača's
        # 50 m shaft over the chamber), so its vote shrinks with cos^2(inclination)
        L3 = math.dist(qa, qb)
        wf = 1.0 if design != "plan" or L3 < 1e-9 else (math.hypot(qb[0] - qa[0], qb[1] - qa[1]) / L3) ** 2
        if "(" in a or "(" in b:
            st, tip = (pb, pa) if "(" in a else (pa, pb)
            out.append(("splay", st, tip, wf))
        elif key not in skip:
            out.append(("leg", pa, pb, wf))
    return out


def first_crossing(a, b, wgrid):
    """Fraction along a->b of the first drawn wall it crosses, or None."""
    best = None
    L = math.hypot(b[0] - a[0], b[1] - a[1])
    for (_ii, _si, _k, p, q) in wgrid.near(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2), L / 2 + GRID):
        den = _cross(b[0] - a[0], b[1] - a[1], q[0] - p[0], q[1] - p[1])
        if abs(den) < 1e-12:
            continue
        t = _cross(p[0] - a[0], p[1] - a[1], q[0] - p[0], q[1] - p[1]) / den
        u = _cross(p[0] - a[0], p[1] - a[1], b[0] - a[0], b[1] - a[1]) / den
        if 1e-6 < t <= 1.0 and 0.0 <= u <= 1.0 and (best is None or t < best):
            best = t
    return best


def near_wall(p, wgrid, tol):
    for (_ii, _si, _k, a, b) in wgrid.near(p, tol):
        ex, ey = b[0] - a[0], b[1] - a[1]
        L2 = ex * ex + ey * ey
        f = 0.0 if L2 == 0 else max(0.0, min(1.0, ((p[0] - a[0]) * ex + (p[1] - a[1]) * ey) / L2))
        if math.hypot(a[0] + f * ex - p[0], a[1] + f * ey - p[1]) <= tol:
            return True
    return False


def interior_samples(lines, wgrid):
    """Points known to be open cave. Legs whole. A splay up to the first wall it
    crosses (profile projections poke through walls), or - uncut - to SPLAY_KEEP
    only when its tip lands on a wall; an uncut splay ending in the open went out
    through the entrance or a gap (the entrance fan into the sky) and says nothing."""
    pts, dropped = [], 0
    for kind, a, b, wf in lines:
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        if L < 1e-9:
            continue
        end = L
        if kind == "splay":
            cut = first_crossing(a, b, wgrid)
            if cut is not None:
                end = max(0.0, cut * L - 0.05)
            elif near_wall(b, wgrid, TIP_TOL):
                end = L * SPLAY_KEEP
            else:
                dropped += 1
                continue
        n = max(1, int(end / SAMPLE_STEP))
        for k in range(n + 1):
            f = (k * end / n) / L if L else 0.0
            pts.append((a[0] + f * (b[0] - a[0]), a[1] + f * (b[1] - a[1]), kind, wf))
    return pts, dropped


# ---------------------------------------------------------------------------
# the walls


def split_sequences(item):
    """[[(x, y, flags), ...], ...] - one list per B-sequence, in file order."""
    seqs, cur = [], None
    for x, y, flags in nf.item_points(item):
        if cur is None or flags.startswith("B"):
            cur = []
            seqs.append(cur)
        cur.append((x, y, flags))
    return [s for s in seqs if s]


def border_items(root, design):
    return list(nf.iter_items(root.find(design), (LAYER_BORDERS,)))


class Grid:
    def __init__(self, cell=GRID):
        self.cell, self.d = cell, {}

    def key(self, x, y):
        return (int(math.floor(x / self.cell)), int(math.floor(y / self.cell)))

    def add_point(self, p, obj):
        self.d.setdefault(self.key(*p), []).append(obj)

    def add_segment(self, a, b, obj):
        x0, y0 = self.key(min(a[0], b[0]), min(a[1], b[1]))
        x1, y1 = self.key(max(a[0], b[0]), max(a[1], b[1]))
        for i in range(x0, x1 + 1):
            for j in range(y0, y1 + 1):
                self.d.setdefault((i, j), []).append(obj)

    def near(self, p, r):
        x0, y0 = self.key(p[0] - r, p[1] - r)
        x1, y1 = self.key(p[0] + r, p[1] + r)
        seen = set()
        for i in range(x0, x1 + 1):
            for j in range(y0, y1 + 1):
                for o in self.d.get((i, j), ()):
                    if id(o) not in seen:
                        seen.add(id(o))
                        yield o


def _cross(ax, ay, bx, by):
    return ax * by - ay * bx


def segments_cross(p, q, a, b):
    """Proper intersection of segments pq and ab."""
    d1 = _cross(q[0] - p[0], q[1] - p[1], a[0] - p[0], a[1] - p[1])
    d2 = _cross(q[0] - p[0], q[1] - p[1], b[0] - p[0], b[1] - p[1])
    d3 = _cross(b[0] - a[0], b[1] - a[1], p[0] - a[0], p[1] - a[1])
    d4 = _cross(b[0] - a[0], b[1] - a[1], q[0] - a[0], q[1] - a[1])
    return (d1 > 0) != (d2 > 0) and (d3 > 0) != (d4 > 0)


def resample(poly, step):
    """[(point, unit tangent, weight)] every `step` along a polyline."""
    out = []
    for (x1, y1), (x2, y2) in zip(poly, poly[1:]):
        L = math.hypot(x2 - x1, y2 - y1)
        if L < 1e-9:
            continue
        tx, ty = (x2 - x1) / L, (y2 - y1) / L
        n = max(1, int(round(L / step)))
        for k in range(n):
            f = (k + 0.5) / n
            out.append(((x1 + f * (x2 - x1), y1 + f * (y2 - y1)), (tx, ty), L / n))
    return out


def analyse_design(root, design):
    lines = survey_lines(root, design)
    # every Borders polyline blocks sight, whatever its pen
    walls, wgrid = [], Grid()
    for ii, item in enumerate(border_items(root, design)):
        for si, seq in enumerate(split_sequences(item)):
            poly = [(x, y) for x, y, _f in seq]
            walls.append(dict(item=ii, seq=si, poly=poly, attrs=dict(item.attrib),
                              pen=(item.find("pen").get("type") if item.find("pen") is not None else None)))
            for k, (a, b) in enumerate(zip(poly, poly[1:])):
                wgrid.add_segment(a, b, (ii, si, k, a, b))
    samples, dropped = interior_samples(lines, wgrid)
    sgrid = Grid()
    for s in samples:
        sgrid.add_point(s[:2], s)

    results = []
    for w in walls:
        votes = []           # (signed weight, distance, kind)
        unseen = 0
        for (px, py), (tx, ty), wt in resample(w["poly"], WALL_STEP):
            cands = []
            r = GRID
            while r <= MAX_SIGHT and len(cands) < CANDIDATES:
                cands = [s for s in sgrid.near((px, py), r) if math.hypot(s[0] - px, s[1] - py) <= r]
                r *= 2
            cands.sort(key=lambda s: math.hypot(s[0] - px, s[1] - py))
            got = None
            for s in cands[:CANDIDATES]:
                dist = math.hypot(s[0] - px, s[1] - py)
                if dist > MAX_SIGHT or dist < 1e-6:
                    continue
                # start a hair off the wall toward the sample, so the own segment does not block
                e = min(0.01, dist / 2)
                p0 = (px + (s[0] - px) / dist * e, py + (s[1] - py) / dist * e)
                blocked = False
                for (ii, si, k, a, b) in wgrid.near(((p0[0] + s[0]) / 2, (p0[1] + s[1]) / 2), dist / 2 + GRID):
                    if segments_cross(p0, s[:2], a, b):
                        blocked = True
                        break
                if not blocked:
                    got = (s, dist)
                    break
            if got is None:
                unseen += 1
                continue
            s, dist = got
            side = _cross(tx, ty, s[0] - px, s[1] - py)
            # y grows DOWN: cross > 0 means the sample is on the RIGHT as seen on screen
            sign = -1.0 if side > 0 else 1.0          # +1 = cave on the LEFT (screen)
            votes.append((sign * wt * s[3] * (LEG_WEIGHT if s[2] == "leg" else 1.0) / (REF + dist), dist, s[2]))
        tot = sum(abs(v[0]) for v in votes)
        score = sum(v[0] for v in votes) / tot if tot else None
        length = sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(w["poly"], w["poly"][1:]))
        npts = len(votes) + unseen
        results.append(dict(item=w["item"], seq=w["seq"], type=w["attrs"].get("type"), pen=w["pen"],
                            n=len(w["poly"]), length=round(length, 2),
                            start=[round(c, 2) for c in w["poly"][0]], end=[round(c, 2) for c in w["poly"][-1]],
                            score=None if score is None else round(score, 3),
                            coverage=round(len(votes) / npts, 2) if npts else 0.0,
                            median_dist=round(sorted(v[1] for v in votes)[len(votes) // 2], 2) if votes else None,
                            cave_side=None if score is None else ("left" if score > 0 else "right")))
    return dict(lines=lines, samples=samples, walls=walls, results=results, dropped=dropped)


def fill_joins(seqs):
    """The straight joins cSurvey adds when it fills an item: end(i) -> start(i+1), last -> first."""
    if len(seqs) < 2:
        return []
    return [(a[-1], b[0]) for a, b in zip(seqs, seqs[1:] + seqs[:1])]


def draw(path, designs, out_png):
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(20, 10))
    for ax, (design, A) in zip(axes, designs.items()):
        for s in A["samples"]:
            ax.plot(s[0], s[1], ".", ms=1, color="gold" if s[2] == "splay" else "red")
        for w, r in zip(A["walls"], A["results"]):
            poly = w["poly"]
            col = "gray" if r["score"] is None else ("tab:blue" if r["score"] > 0 else "tab:orange")
            lw = 2.0 if r["type"] == AREA_TYPE else 0.8
            ax.plot([p[0] for p in poly], [p[1] for p in poly], "-", color=col, lw=lw)
            if len(poly) >= 2:   # an arrow at the middle shows the drawing direction
                m = len(poly) // 2
                a, b = poly[max(0, m - 1)], poly[m]
                ax.annotate("", xy=b, xytext=a, arrowprops=dict(arrowstyle="->", color=col, lw=1.5))
            ax.annotate("%d.%d %s" % (r["item"], r["seq"], "" if r["score"] is None else "%+.2f" % r["score"]),
                        poly[len(poly) // 2], fontsize=7, color=col)
        ax.set_aspect("equal"); ax.invert_yaxis(); ax.grid(True, lw=0.3)
        ax.set_title("%s %s - blue: cave on the LEFT of the drawing direction, orange: on the RIGHT, gray: no vote"
                     % (os.path.basename(path), design), fontsize=8)
    plt.tight_layout(); plt.savefig(out_png, dpi=80); plt.close(fig)


def analyse(path, png=False):
    root = load(path)
    designs, report = {}, dict(file=os.path.basename(path), designs={})
    if root.find("plan/layers") is None:
        report["error"] = "not imported into cSurvey (no layers)"
        return report
    for design in ("plan", "profile"):
        A = analyse_design(root, design)
        designs[design] = A
        report["designs"][design] = dict(legs=sum(1 for l in A["lines"] if l[0] == "leg"),
                                         splays=sum(1 for l in A["lines"] if l[0] == "splay"),
                                         splays_dropped=A["dropped"],
                                         walls=A["results"])
    if png:
        draw(path, designs, os.path.join(HERE, "_out", os.path.splitext(os.path.basename(path))[0] + "_sides.png"))
    return report


if __name__ == "__main__":
    args = sys.argv[1:]
    png = "--png" in args
    args = [a for a in args if a != "--png"]
    os.makedirs(os.path.join(HERE, "_out"), exist_ok=True)
    for p in args:
        rep = analyse(p, png)
        print("==", rep["file"], rep.get("error", ""))
        for d, D in rep.get("designs", {}).items():
            print("  %s: %d legs, %d splays (%d ended in the open, unused)" % (d, D["legs"], D["splays"], D["splays_dropped"]))
            for r in D["walls"]:
                print("    %2d.%-2d t%s p%s n=%-4d L=%6.2f score=%-7s cov=%.2f med=%s side=%s"
                      % (r["item"], r["seq"], r["type"], r["pen"], r["n"], r["length"], r["score"],
                         r["coverage"], r["median_dist"], r["cave_side"]))
