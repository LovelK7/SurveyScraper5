#!/usr/bin/env python3
"""Wall orientation: find which side of each drawn wall is the cave, then
reverse (and reorder) the sequences of a merged cave-border item that run
against the rest. Run by KORAK 2 (fix_imported_linetypes.py); project 0006.

Why: cSurvey fills a Borders item as ONE polygon, joining the end of each
sequence to the start of the next with a straight line
(cItemFreeHandArea.vb:186-209, cDesign.vb:360-376). Every Merge runs
ReorderSequences (cPoints.vb:1084-1145), which reverses a stroke whenever its
far end happens to be nearer - a coin flip at an entrance mouth. One stroke
running the wrong way makes its join cut across the passage, and the operator
hunts for it and presses "Revert sequence". Orienting the separate strokes
before the merge does not help (the merge re-reverses them; simulated on the
corpus, project 0006 findings/merge_sim.py), so this runs on MERGED items.

The interior protocol - the survey is inside the cave:
  * known interior = points along every in-cave leg, and along every splay up
    to the first drawn wall it crosses (profile left/right splays poke through
    walls); an uncut splay only if its tip lands near a wall (the entrance
    station's fan into the sky lands nowhere and is dropped). In the plan a
    shot's weight shrinks with cos^2(inclination): a deep shaft projects across
    the walls of the chamber below.
  * along each wall, the nearest interior sample the wall point can SEE (the
    sight line crosses no other drawn wall) votes cave-left or cave-right of
    the wall's local direction.

The correction is RELATIVE: inside one merged item the confident,
length-weighted majority is "the right way" and only a confident minority is
reversed (a global "cave on the right" rule broke consistently drawn items).
A change is kept only when the fill's joins get no longer and no more of them
cross a wall. Then, with directions settled, the sequence order with the
shortest joins is taken when it clearly beats the drawn one.

On a FRESH import (no wall merged yet in that design) it also does the merge
the operator used to do by hand: every open cave-pen stroke the survey can see
goes into one border, turned cave-on-right and chained for the shortest joins
(user, 2026-10-03). Closed strokes, decorated lines and strokes with no survey
in sight (a surface line drawn with the wall pen - sp7's profile) stay as drawn.

Only cave-border areas (type 4, cave pens) are touched: pit, overhang and
chimney lines carry one-sided decorations and their direction is meaning.
Stdlib only - the kit runs on operators' machines.
"""

import copy
import math

LAYER_BORDERS = "5"
AREA_TYPE = "4"                       # cItemInvertedFreeHandArea, the cave border
SAFE_PENS = {"1", "8", "25", "26"}    # Cave, PresumedCave, TooNarrowCave, UnderlyingCave (cPen.vb:1164-1167)
NOT_IN_CAVE_FLAGS = ("exclude", "surface", "splay", "cut", "duplicate", "calibration")

# interior samples
SAMPLE_STEP = 0.10      # m between samples along legs and splays
SPLAY_KEEP = 0.85       # an uncut splay is used up to here: its tip lies ON the wall
TIP_TOL = 0.5           # m; an uncut splay counts only if its tip lands this close to a wall
# voting
WALL_STEP = 0.15        # m between voting points along a wall
MAX_SIGHT = 15.0        # m; a wall further than this from any survey has no vote (Sopača's shaft is 15 m wide)
CANDIDATES = 12         # nearest interior samples tried per wall point
REF = 0.3               # m; vote weight = length / (REF + distance)
LEG_WEIGHT = 3.0        # a leg is never outside, a splay can be
GRID = 0.5              # m spatial-hash cell
# decisions (validated on the 20-file csx_entrances corpus, 2026-10-03)
MIN_SCORE = 0.6         # |signed vote share| a sequence needs to be judged
MIN_COVERAGE = 0.3      # share of its length that must have seen the survey
MIN_MAJORITY = 0.6      # length share the item's majority side needs
REORDER_GAIN = 0.8      # a new order is kept only if its joins are < 80 % of the old
CLOSED_TOL = 0.05       # m; a stroke whose ends meet is a closed outline (pillar, island)
HAND_MERGE_MIN = 0.5    # m; a border with two sequences this long was merged by the operator


# ---------------------------------------------------------------------------
# <points data> exactly as cSurvey parses it (cPoints.vb:496-599):
# `X Y [flags]`, flags = [B[P][T<n>]][L][S[guid]]; a bare S = the previous
# point's segment binding.


def parse_points(data):
    """(meta prefix, [point dict]) with segment bindings resolved."""
    meta = ""
    if data.startswith("#"):
        cut = data.index(" ") + 1
        meta, data = data[:cut], data[cut:]
    toks = data.split()
    pts, i, prev_bind = [], 0, ""
    while i + 1 < len(toks):
        x, y = toks[i], toks[i + 1]
        i += 2
        flags = ""
        if i < len(toks) and not (toks[i][0].isdigit() or toks[i][0] == "-"):
            flags = toks[i]
            i += 1
        p = dict(x=x, y=y, B=False, P=False, T=None, L=False, bind=None)
        f = flags
        if f.startswith("B"):
            p["B"], f = True, f[1:]
            if f.startswith("P"):
                p["P"], f = True, f[1:]
            if f.startswith("T"):
                p["T"], f = f[1:2], f[2:]
        if f.startswith("L"):
            p["L"], f = True, f[1:]
        if f.startswith("S"):
            f = f[1:]
            p["bind"] = f if f else prev_bind
            prev_bind = p["bind"]
        else:
            prev_bind = ""
        pts.append(p)
    return meta, pts


def serialize_points(meta, pts):
    out, prev_bind = [], ""
    for p in pts:
        f = ""
        if p["B"]:
            f += "B" + ("P" if p["P"] else "") + ("T" + p["T"] if p["T"] is not None else "")
        if p["L"]:
            f += "L"
        if p["bind"] is not None:
            f += "S" if p["bind"] == prev_bind else "S" + p["bind"]
            prev_bind = p["bind"]
        else:
            prev_bind = ""
        out.append("%s %s %s" % (p["x"], p["y"], f) if f else "%s %s" % (p["x"], p["y"]))
    return meta + " ".join(out) + " "


def sequence_ranges(pts):
    starts = [k for k, p in enumerate(pts) if p["B"] or k == 0]
    return [(s, e - 1) for s, e in zip(starts, starts[1:] + [len(pts)])]


def reverse_range(pts, s, e):
    """cSequence.Reverse (cSequence.vb:229-242) on pts[s..e]: flip the order and
    hand the B/P/T prefix to the new first point."""
    head = {k: pts[s][k] for k in ("B", "P", "T")}
    seg = pts[s:e + 1][::-1]
    seg[-1].update(B=False, P=False, T=None)
    seg[0].update(head)
    pts[s:e + 1] = seg


def _length(poly):
    return sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(poly, poly[1:]))


def _xy(p):
    return float(p["x"]), float(p["y"])


# ---------------------------------------------------------------------------
# geometry


def _cross(ax, ay, bx, by):
    return ax * by - ay * bx


def segments_cross(p, q, a, b):
    d1 = _cross(q[0] - p[0], q[1] - p[1], a[0] - p[0], a[1] - p[1])
    d2 = _cross(q[0] - p[0], q[1] - p[1], b[0] - p[0], b[1] - p[1])
    d3 = _cross(b[0] - a[0], b[1] - a[1], p[0] - a[0], p[1] - a[1])
    d4 = _cross(b[0] - a[0], b[1] - a[1], q[0] - a[0], q[1] - a[1])
    return (d1 > 0) != (d2 > 0) and (d3 > 0) != (d4 > 0)


class _Grid(object):
    def __init__(self):
        self.d = {}

    @staticmethod
    def key(x, y):
        return int(math.floor(x / GRID)), int(math.floor(y / GRID))

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


# ---------------------------------------------------------------------------
# the interior


def survey_lines(root, design):
    """[(kind, a, b, weight)] in design coordinates, kind 'leg' or 'splay'.

    Each <t> lists its OWN position per connection (<tcon n=other><p>): in the
    profile a station has one d per connection, so leg a-b runs from
    t[a].tcon[b] to t[b].tcon[a]. Plan = (x, y), profile = (d, z).
    """
    calc = root.find("calculate/ts")
    segs = root.find("segments")
    if calc is None:
        return []
    skip = set()
    for seg in (segs.findall("segment") if segs is not None else []):
        if seg.get("splay") != "1" and any(seg.get(f) == "1" for f in NOT_IN_CAVE_FLAGS):
            skip.add(frozenset((seg.get("from"), seg.get("to"))))
    pos = {}
    for t in calc.findall("t"):
        n = t.get("n") or ""
        for tc in t.findall("tcons/tcon"):
            p = tc.find("p")
            if p is None:
                continue
            try:
                x, y, z, d = (float(p.get(k) or 0.0) for k in ("x", "y", "z", "d"))
            except ValueError:
                continue
            pos[(n, tc.get("n"))] = ((x, y) if design == "plan" else (d, z), (x, y, z))
    out, seen = [], set()
    for (a, b), (pa, qa) in pos.items():
        key = frozenset((a, b))
        if key in seen or (b, a) not in pos:
            continue
        seen.add(key)
        pb, qb = pos[(b, a)]
        L3 = math.sqrt(sum((u - v) ** 2 for u, v in zip(qa, qb)))
        wf = 1.0 if design != "plan" or L3 < 1e-9 else (math.hypot(qb[0] - qa[0], qb[1] - qa[1]) / L3) ** 2
        if "(" in a or "(" in b:
            st, tip = (pb, pa) if "(" in a else (pa, pb)
            out.append(("splay", st, tip, wf))
        elif key not in skip:
            out.append(("leg", pa, pb, wf))
    return out


def _first_crossing(a, b, wgrid):
    best = None
    L = math.hypot(b[0] - a[0], b[1] - a[1])
    for (_k, p, q) in wgrid.near(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2), L / 2 + GRID):
        den = _cross(b[0] - a[0], b[1] - a[1], q[0] - p[0], q[1] - p[1])
        if abs(den) < 1e-12:
            continue
        t = _cross(p[0] - a[0], p[1] - a[1], q[0] - p[0], q[1] - p[1]) / den
        u = _cross(p[0] - a[0], p[1] - a[1], b[0] - a[0], b[1] - a[1]) / den
        if 1e-6 < t <= 1.0 and 0.0 <= u <= 1.0 and (best is None or t < best):
            best = t
    return best


def _near_wall(p, wgrid, tol):
    for (_k, a, b) in wgrid.near(p, tol):
        ex, ey = b[0] - a[0], b[1] - a[1]
        L2 = ex * ex + ey * ey
        f = 0.0 if L2 == 0 else max(0.0, min(1.0, ((p[0] - a[0]) * ex + (p[1] - a[1]) * ey) / L2))
        if math.hypot(a[0] + f * ex - p[0], a[1] + f * ey - p[1]) <= tol:
            return True
    return False


def _interior_samples(lines, wgrid):
    pts = []
    for kind, a, b, wf in lines:
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        if L < 1e-9:
            continue
        end = L
        if kind == "splay":
            cut = _first_crossing(a, b, wgrid)
            if cut is not None:
                end = max(0.0, cut * L - 0.05)
            elif _near_wall(b, wgrid, TIP_TOL):
                end = L * SPLAY_KEEP
            else:
                continue
        n = max(1, int(end / SAMPLE_STEP))
        for k in range(n + 1):
            f = (k * end / n) / L
            pts.append((a[0] + f * (b[0] - a[0]), a[1] + f * (b[1] - a[1]),
                        wf * (LEG_WEIGHT if kind == "leg" else 1.0)))
    return pts


def _resample(poly, step):
    out = []
    for (x1, y1), (x2, y2) in zip(poly, poly[1:]):
        L = math.hypot(x2 - x1, y2 - y1)
        if L < 1e-9:
            continue
        n = max(1, int(round(L / step)))
        for k in range(n):
            f = (k + 0.5) / n
            out.append(((x1 + f * (x2 - x1), y1 + f * (y2 - y1)), ((x2 - x1) / L, (y2 - y1) / L), L / n))
    return out


def _grids(root, design, items):
    """(walls, interior samples). Only cave-border AREAS are walls here: they
    block sight and cut splays. Lines in the Borders layer (ledges, steps drawn
    across a shaft - Sopača's profile) lie inside the cave; letting them block
    hid a whole shaft wall from the survey."""
    wgrid = _Grid()
    for _ii, item in items:
        pts_el = item.find("points")
        if item.get("type") != AREA_TYPE or pts_el is None:
            continue
        _m, pts = parse_points(pts_el.get("data") or "")
        for a, b in (sequence_ranges(pts) if pts else []):
            poly = [_xy(p) for p in pts[a:b + 1]]
            for k, (p, q) in enumerate(zip(poly, poly[1:])):
                wgrid.add_segment(p, q, (k, p, q))
    sgrid = _Grid()
    for smp in _interior_samples(survey_lines(root, design), wgrid):
        sgrid.add_point(smp[:2], smp)
    return wgrid, sgrid


def wall_side(poly, sgrid, wgrid):
    """(score, coverage): score in [-1, +1], +1 = cave on the LEFT of the drawing
    direction as seen on screen (y grows down), None when no survey was in sight."""
    num = den = 0.0
    seen = total = 0
    for (px, py), (tx, ty), wt in _resample(poly, WALL_STEP):
        total += 1
        r = GRID
        while True:          # widen the search until enough samples, the last step exactly MAX_SIGHT
            cands = [s for s in sgrid.near((px, py), r) if math.hypot(s[0] - px, s[1] - py) <= r]
            if len(cands) >= CANDIDATES or r >= MAX_SIGHT:
                break
            r = min(r * 2, MAX_SIGHT)
        cands.sort(key=lambda s: math.hypot(s[0] - px, s[1] - py))
        for s in cands[:CANDIDATES]:
            dist = math.hypot(s[0] - px, s[1] - py)
            if dist > MAX_SIGHT or dist < 1e-6:
                continue
            e = min(0.01, dist / 2)      # start a hair off the wall so its own segment does not block
            p0 = (px + (s[0] - px) / dist * e, py + (s[1] - py) / dist * e)
            if any(segments_cross(p0, s[:2], a, b)
                   for (_k, a, b) in wgrid.near(((p0[0] + s[0]) / 2, (p0[1] + s[1]) / 2), dist / 2 + GRID)):
                continue
            side = -1.0 if _cross(tx, ty, s[0] - px, s[1] - py) > 0 else 1.0
            w = wt * s[2] / (REF + dist)
            num += side * w
            den += w
            seen += 1
            break
    if den == 0:
        return None, 0.0
    return num / den, (seen / float(total) if total else 0.0)


# ---------------------------------------------------------------------------
# the correction


def borders_items(design_el):
    """[(index in its layer, item)] for the Borders layer - the index <pointsjoins> uses."""
    out = []
    layers = design_el.find("layers")
    for layer in (layers.findall("layer") if layers is not None else []):
        if layer.get("type") != LAYER_BORDERS:
            continue
        items_el = layer.find("items")
        kids = (items_el.findall("item") if items_el is not None else []) + layer.findall("item")
        out.extend(enumerate(kids))
    return out


def remap_joins(design_el, item_index, mapping):
    """Point joins reference `layer,item,point` (cPoint.vb:181-195): follow the moved points."""
    pj = design_el.find("pointsjoins")
    n = 0
    for j in (pj.findall("pointsjoin") if pj is not None else []):
        parts = []
        for ref in (j.get("data") or "").split():
            bits = ref.split(",")
            if (len(bits) == 3 and bits[0] == LAYER_BORDERS and bits[1] == str(item_index)
                    and bits[2].isdigit() and int(bits[2]) in mapping):
                bits[2] = str(mapping[int(bits[2])])
                n += 1
            parts.append(",".join(bits))
        j.set("data", " ".join(parts) + " ")
    return n


def fill_joins(seqs):
    """(total length of the fill's straight joins, how many cross a drawn sequence)."""
    if len(seqs) < 2:
        return 0.0, 0
    joins = [(a[-1], b[0]) for a, b in zip(seqs, seqs[1:] + seqs[:1])]
    crossing = 0
    for p0, q0 in joins:
        if math.hypot(q0[0] - p0[0], q0[1] - p0[1]) < 1e-6:
            continue
        # shrink 2 % at both ends: a join starts ON a sequence end and must not count that touch
        p = (p0[0] + 0.02 * (q0[0] - p0[0]), p0[1] + 0.02 * (q0[1] - p0[1]))
        q = (q0[0] - 0.02 * (q0[0] - p0[0]), q0[1] - 0.02 * (q0[1] - p0[1]))
        if any(segments_cross(p, q, a, b) for s in seqs for a, b in zip(s, s[1:])):
            crossing += 1
    return sum(math.hypot(q[0] - p[0], q[1] - p[1]) for p, q in joins), crossing


def chain_order(seqs):
    """The sequence order with the shortest fill joins, no reversals, sequence 0
    first: relocation search (take each out, reinsert where it adds least)."""
    n = len(seqs)

    def cost(o):
        return sum(math.hypot(seqs[b][0][0] - seqs[a][-1][0], seqs[b][0][1] - seqs[a][-1][1])
                   for a, b in zip(o, o[1:] + o[:1]))
    order, improved = list(range(n)), True
    while improved:
        improved = False
        for k in range(1, n):
            base = [s for s in order if s != k]
            best = min((base[:i] + [k] + base[i:] for i in range(1, len(base) + 1)), key=cost)
            if cost(best) < cost(order) - 1e-9:
                order, improved = best, True
    return order


def fix_design(root, design, reorder=True):
    """Orient (and reorder) the merged cave-border items of one design, in place.

    Returns one dict per multi-sequence wall item: flipped / moved sequences,
    doubtful ones, and the fill joins before and after.
    """
    D = root.find(design)
    if D is None or D.find("layers") is None:
        return []
    work = []
    for ii, item in borders_items(D):
        pts_el = item.find("points")
        if item.get("type") != AREA_TYPE or pts_el is None:
            continue
        meta, pts = parse_points(pts_el.get("data") or "")
        work.append((ii, item, pts_el, meta, pts, sequence_ranges(pts)))
    if not any(len(w[5]) > 1 for w in work):
        return []
    wgrid, sgrid = _grids(root, design, borders_items(D))

    report = []
    for ii, item, pts_el, meta, pts, ranges in work:
        if len(ranges) < 2:
            continue
        pen = item.find("pen")
        own = iter(pts_el.findall("pen"))              # a P-sequence's own pen, in sequence order
        seq_pen = [(next(own, None) if pts[s]["P"] else pen) for s, _e in ranges]
        xy = [[_xy(p) for p in pts[s:e + 1]] for s, e in ranges]
        entry = dict(design=design, item=ii, sequences=len(ranges), flipped=[], moved=False,
                     doubtful=[], majority=None)
        entry["joins_before"] = entry["joins_after"] = fill_joins(xy)
        report.append(entry)
        sides = {}
        for si, poly in enumerate(xy):
            sp = seq_pen[si]
            if sp is None or sp.get("type") not in SAFE_PENS:
                continue                                # a decorated border: its direction is meaning
            length = sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(poly, poly[1:]))
            score, cov = wall_side(poly, sgrid, wgrid)
            if score is None or abs(score) < MIN_SCORE or cov < MIN_COVERAGE:
                entry["doubtful"].append(si)
            else:
                sides[si] = (1 if score > 0 else -1, length)
        left = sum(L for s, L in sides.values() if s > 0)
        right = sum(L for s, L in sides.values() if s < 0)
        if not sides or max(left, right) < MIN_MAJORITY * (left + right):
            continue
        major = 1 if left > right else -1
        entry["majority"] = "left" if major > 0 else "right"
        trial = [dict(p) for p in pts]
        mapping = {}
        minority = sorted(si for si, (s, _L) in sides.items() if s != major)
        for si in minority:
            s, e = ranges[si]
            reverse_range(trial, s, e)
            mapping.update({k: s + e - k for k in range(s, e + 1)})
        before = entry["joins_before"]
        if minority:
            after = fill_joins([[_xy(p) for p in trial[s:e + 1]] for s, e in ranges])
            if after[0] > before[0] + 0.01 or after[1] > before[1]:
                entry["refused"] = minority        # the fill would get worse: the operator decides
                continue
            entry["flipped"] = minority
        else:
            after = before
        pens = pts_el.findall("pen")
        if reorder and len(ranges) > 2:
            txy = [[_xy(p) for p in trial[s:e + 1]] for s, e in ranges]
            order = chain_order(txy)
            if order != list(range(len(ranges))):
                cand = fill_joins([txy[k] for k in order])
                if cand[0] < REORDER_GAIN * after[0] and cand[1] <= after[1]:
                    it = iter(pens)
                    sp_el = [next(it) if trial[s]["P"] else None for s, _e in ranges]
                    new, remap = [], {}
                    for k in order:
                        s, e = ranges[k]
                        for j in range(s, e + 1):
                            remap[j] = len(new)
                            new.append(trial[j])
                    mapping = {old: remap[mapping.get(old, old)] for old in range(len(trial))}
                    trial = new
                    for p in pens:                  # pens ride with their sequence
                        pts_el.remove(p)
                    for k in order:
                        if sp_el[k] is not None:
                            pts_el.append(sp_el[k])
                    after = cand
                    entry["moved"] = True
        if entry["flipped"] or entry["moved"]:
            pts_el.set("data", serialize_points(meta, trial))
            remap_joins(D, ii, mapping)
            entry["joins_after"] = after
    return report


def _best_cycle(ends, free):
    """Order + flips of strokes with the shortest closing joins.

    ends[i] = (first point, last point) in the stroke's settled direction;
    `free` strokes may also run reversed. For every start stroke: a greedy
    end->start walk, then relocation (each stroke out and back in where it adds
    least, flipped if free) until nothing improves; the shortest cycle wins.
    Returns [(index, flipped)].
    """
    n = len(ends)

    def gap(a, b):
        (i, fi), (j, fj) = a, b
        p = ends[i][0] if fi else ends[i][1]
        q = ends[j][1] if fj else ends[j][0]
        return math.hypot(q[0] - p[0], q[1] - p[1])

    def flips(i):
        return (False, True) if i in free else (False,)

    best, best_cost = None, None
    for s0 in range(n):
        o, left = [(s0, False)], set(range(n)) - {s0}
        while left:
            nxt = min(((i, f) for i in left for f in flips(i)), key=lambda c: gap(o[-1], c))
            o.append(nxt)
            left.discard(nxt[0])
        c_o = sum(gap(a, b) for a, b in zip(o, o[1:] + o[:1]))
        improved = True
        while improved and n > 2:
            improved = False
            for k in range(n):
                pos = [x[0] for x in o].index(k)
                cur, prv, nxt = o[pos], o[pos - 1], o[(pos + 1) % n]
                rest = o[:pos] + o[pos + 1:]
                c_rest = c_o - gap(prv, cur) - gap(cur, nxt) + gap(prv, nxt)
                cand = None
                for j in range(len(rest)):
                    a, b = rest[j], rest[(j + 1) % len(rest)]
                    for f in flips(k):
                        c = c_rest - gap(a, b) + gap(a, (k, f)) + gap((k, f), b)
                        if cand is None or c < cand[0]:
                            cand = (c, j, f)
                if cand[0] < c_o - 1e-9:
                    o = rest[:cand[1] + 1] + [(k, cand[2])] + rest[cand[1] + 1:]
                    c_o, improved = cand[0], True
        if best is None or c_o < best_cost - 1e-9:
            best, best_cost = o, c_o
    return best


def _parent_of(design_el, item):
    for layer in design_el.find("layers").findall("layer"):
        for parent in (layer.find("items"), layer):
            if parent is not None and any(c is item for c in parent):
                return parent
    return None


def automerge_design(root, design):
    """Merge a fresh import's loose wall strokes into one cave border.

    Returns a report dict, or None when there was nothing to merge - or when
    the operator already merged walls in this design (their work is not
    redone; fix_design orients and orders it instead).
    """
    D = root.find(design)
    if D is None or D.find("layers") is None:
        return None
    items = borders_items(D)
    loose = []
    for ii, item in items:
        pts_el, pen = item.find("points"), item.find("pen")
        if item.get("type") != AREA_TYPE or pts_el is None or pen is None or pen.get("type") not in SAFE_PENS:
            continue
        meta, pts = parse_points(pts_el.get("data") or "")
        ranges = sequence_ranges(pts)
        if len(ranges) > 1:
            real = [r for r in ranges if _length([_xy(p) for p in pts[r[0]:r[1] + 1]]) >= HAND_MERGE_MIN]
            if len(real) > 1:
                return None                   # merged by hand: the operator owns this design's merge
            continue                          # a stray extra point (Tavnjak's 0.0 m sequence): left as is
        if len(pts) < 2 or pts_el.findall("pen"):
            continue
        poly = [_xy(p) for p in pts]
        if math.hypot(poly[-1][0] - poly[0][0], poly[-1][1] - poly[0][1]) < CLOSED_TOL:
            continue                          # a closed outline is its own border
        loose.append((ii, item, meta, pts, poly))
    if len(loose) < 2:
        return None
    wgrid, sgrid = _grids(root, design, items)

    members, free, left_out = [], set(), []   # member: (item index, item, meta, pts, old point indices)
    for ii, item, meta, pts, poly in loose:
        score, cov = wall_side(poly, sgrid, wgrid)
        if score is None or cov < MIN_COVERAGE:
            left_out.append(ii)               # no survey in sight (sp7's surface line): stays as drawn
            continue
        idx = list(range(len(pts)))
        if abs(score) >= MIN_SCORE:
            if score > 0:                     # cave on the left: turn it cave-on-right
                pts = [dict(p) for p in pts]
                reverse_range(pts, 0, len(pts) - 1)
                idx = idx[::-1]
        else:
            free.add(len(members))            # the survey cannot tell: the chain decides
        members.append((ii, item, meta, pts, idx))
    if len(members) < 2:
        return None
    order = _best_cycle([(_xy(m[3][0]), _xy(m[3][-1])) for m in members], free)

    # The merged item is the first member's element (attributes, pen, brush,
    # datarow); like cItem.Combine (cItem.vb:1002-1053) every appended sequence
    # carries B + P and its own <pen> inside <points>.
    first = members[order[0][0]][1]
    first_ii = members[order[0][0]][0]
    linetypes = {m[1].get("linetype") for m in members}
    new_pts, pens, origin = [], [], []
    for pos, (i, f) in enumerate(order):
        ii, item, _meta, pts, idx = members[i]
        seq = [dict(p) for p in pts]
        if f:
            reverse_range(seq, 0, len(seq) - 1)
            idx = idx[::-1]
        seq[0]["B"] = True
        if len(linetypes) > 1 and seq[0]["T"] is None and item.get("linetype") is not None:
            seq[0]["T"] = item.get("linetype")
        if pos > 0:
            seq[0]["P"] = True
            pens.append(copy.deepcopy(item.find("pen")))
        new_pts.extend(seq)
        origin.extend((ii, k) for k in idx)
    pts_el = first.find("points")
    pts_el.set("data", serialize_points(members[order[0][0]][2], new_pts))
    for pen in pens:
        pts_el.append(pen)
    gone = {m[0] for m in members} - {first_ii}
    for ii, item, _m, _p, _i in members:
        if ii in gone:
            parent = _parent_of(D, item)
            if parent is not None:
                parent.remove(item)
    # point joins: merged points follow their new place, later items shift down
    new_index, k = {}, 0
    for ii, _item in items:
        if ii not in gone:
            new_index[ii] = k
            k += 1
    moved = {o: n for n, o in enumerate(origin)}
    pj = D.find("pointsjoins")
    for j in (pj.findall("pointsjoin") if pj is not None else []):
        parts = []
        for ref in (j.get("data") or "").split():
            bits = ref.split(",")
            if len(bits) == 3 and bits[0] == LAYER_BORDERS and bits[1].isdigit() and bits[2].isdigit():
                key = (int(bits[1]), int(bits[2]))
                if key in moved:
                    bits[1], bits[2] = str(new_index[first_ii]), str(moved[key])
                elif int(bits[1]) in new_index:
                    bits[1] = str(new_index[int(bits[1])])
            parts.append(",".join(bits))
        j.set("data", " ".join(parts) + " ")
    seqs = [[_xy(p) for p in new_pts[a:b + 1]] for a, b in sequence_ranges(new_pts)]
    return dict(design=design, merged=len(members), left_out=left_out, unjudged=len(free),
                joins=fill_joins(seqs))


def fix(root, reorder=True, merge=True):
    """Both designs: merge a fresh import's loose wall strokes (when `merge`),
    then orient/reorder every merged item. Returns the report rows."""
    rows = []
    for design in ("plan", "profile"):
        if merge:
            m = automerge_design(root, design)
            if m is not None:
                rows.append(m)
        rows.extend(fix_design(root, design, reorder))
    return rows


def describe(report):
    """Operator lines (no diacritics: the kit's console is cp852)."""
    lines = []
    name = {"plan": "tlocrt", "profile": "profil"}
    for r in report:
        if "merged" in r:
            lines.append("zidovi (%s): spojeno %d linija u jedan obrub, spojnice %.1f m%s"
                         % (name[r["design"]], r["merged"], r["joins"][0],
                            "; %d bez snimka u blizini ostavljeno kako je nacrtano" % len(r["left_out"])
                            if r["left_out"] else ""))
            continue
        jb, ja = r["joins_before"][0], r["joins_after"][0]
        if r["flipped"] or r["moved"]:
            what = []
            if r["flipped"]:
                what.append("okrenuto %d od %d sekvenci" % (len(r["flipped"]), r["sequences"]))
            if r["moved"]:
                what.append("preslozen redoslijed")
            lines.append("zidovi (%s, objekt %d): %s; spojnice %.1f -> %.1f m"
                         % (name[r["design"]], r["item"], ", ".join(what), jb, ja))
        if r.get("refused"):
            lines.append("zidovi (%s, objekt %d): sekvence %s izgledaju okrenute, ali bi ispuna bila losija "
                         "- provjeri rucno" % (name[r["design"]], r["item"], ", ".join(str(s + 1) for s in r["refused"])))
    return lines
