#!/usr/bin/env python3
"""Entrance size at the entrance station - the OSZ's Sirina / Visina ulaza.

Called by nacrt_finish.py once the entrance station is decided; the result
lands in the `_lt_fin.layout.json` sidecar as `entrance_size`, travels into
`<name>_dimenzije.json` (csurvey_driver.py) and `cavedossier osz prefill`
writes the cells. Project 0005 (stages/3N-nacrt/projects/0005-entrance-dimensions)
settled the rules with the user, 2026-10-02/03:

  1. The surveyor's splays at the entrance station come first - they were shot
     at the entrance on purpose. Per direction (left, right across the passage
     in the plan; up, down in the profile) the splay best aligned with that
     direction, within SPLAY_CONE_DEG, is the measurement. An up splay with no
     down splay means the station stands on the floor. Both sides of one
     opening come from the same source: splays for both, else walls for both.
  2. The drawn walls (Borders) are the fallback, at the narrowest opening
     within NARROW_WINDOW_M of the station on the cave side of it. A Borders
     item is several `B` sequences (cPoints.vb:564); cSurvey strokes each one
     alone but fills the item as one polygon with straight joins between
     sequences (cItemFreeHandArea.vb:193-195), so an undrawn wall shows on the
     map as such a join - used only when shorter than BRIDGE_MAX_M.
  3. A pit's opening is a hole in the plan: the min and max extents of the
     splay cloud from the rim station, the wall footprint as fallback; Sirina
     is the smaller number, Visina/duljina the larger.
  4. One decimal - done by the OSZ prefill, this module keeps two.
  5. No size without a witnessed entrance (the drawn sign, a surface leg, the
     finisher's flag): a station chosen only because it is the highest is a
     guess and gets a warning, never a number.

Whether the entrance is a pit or a horizontal opening cannot be read from the
geometry alone (kilavceva pljeskavica: a pit rim with flat splays and a 35
degree first shot, like SB 1220's entrance slope), so BOTH candidates are
measured here and the OSZ prefill picks by the zapisnik's *Vrsta objekta*,
falling back to the geometric guess (`kind_geo`).

Pure stdlib; imports nacrt_finish lazily (it imports this module).
"""
import math

STEEP_DEG = 60.0          # in-cave shot steeper than this = pit-like entrance (geometric guess)
PIT_SPLAY_SHARE = 1 / 3.0  # ...or this share of the station's splays dive steeper than UD_INC_DEG
SPLAY_CONE_DEG = 40.0     # a splay counts for a direction when within this cone of it
UD_INC_DEG = 45.0         # a splay steeper than this is an up/down shot (pit test)
NARROW_WINDOW_M = 0.5     # the wall opening is the narrowest within this of the station, along the axis
SCAN_STEP = 0.1
MAX_REACH_M = 15.0        # a wall further than this is not this entrance's wall
BRIDGE_MAX_M = 5.0        # a fill join longer than this is a drawing-order artifact (SB 1220: 15 m)
PIT_RAYS = 24             # directions for the wall-based pit footprint
RAW_WALL_NAMES = ("wall", "wall:presumed")   # a raw TopoDroid export's walls


def _nf():
    import nacrt_finish
    return nacrt_finish


# ---------------------------------------------------------------------------
# survey data


def _p(t):
    """A station's <p>: the <tcon><p> copies carry the profile distance `d`,
    the direct <p> always says d="0"."""
    p = t.find("tcons/tcon/p")
    if p is None:
        p = t.find("p")
    return p


def splay_vectors(root, station, E):
    """Every splay from `station` as a vector from it: dx, dy (plan, y south),
    dz (depth, + = down), its length and inclination (+ = up)."""
    out = []
    ts = root.find("calculate/ts")
    if ts is None:
        return out
    for t in ts.findall("t"):
        n = t.get("n") or ""
        if not n.startswith(station + "("):
            continue
        p = _p(t)
        if p is None:
            continue
        try:
            dx = float(p.get("x")) - E.x
            dy = float(p.get("y")) - E.y
            dz = float(p.get("z")) - E.z
        except (TypeError, ValueError):
            continue
        length = math.sqrt(dx * dx + dy * dy + dz * dz)
        if length < 1e-6:
            continue
        out.append(dict(n=n, dx=dx, dy=dy, dz=dz, length=length,
                        inc=math.degrees(math.atan2(-dz, math.hypot(dx, dy)))))
    return out


def shots(root):
    """Non-splay shots: from, to, inclination, and whether cSurvey counts them."""
    out = []
    segs = root.find("segments")
    if segs is None:
        return out
    flags = _nf().NOT_IN_CAVE_FLAGS
    for seg in segs.findall("segment"):
        if seg.get("splay") == "1":
            continue
        try:
            inc = float(seg.get("inclination") or 0.0)
        except ValueError:
            inc = 0.0
        out.append(dict(a=seg.get("from"), b=seg.get("to"), inc=inc,
                        excluded=any(seg.get(f) == "1" for f in flags)))
    return out


# ---------------------------------------------------------------------------
# walls


def wall_paths(root, design_name):
    """(drawn sequences, fill joins) of the walls, each a list of (x, y) lists.

    cSurvey file: the Borders layer, split on the `B` point flag, plus the
    straight joins the fill draws between consecutive sequences (and from the
    last back to the first) when they are short. Raw TopoDroid export: the
    `wall` lines (no sequences, no fill).
    """
    nf = _nf()
    design = root.find(design_name)
    paths, bridges = [], []
    if design is None:
        return paths, bridges
    if design.find("layers") is None:
        for item in design.findall("item"):
            if item.get("type") == "line" and (item.get("name") or "") in RAW_WALL_NAMES:
                pts = [(x, y) for x, y, _f in nf.item_points(item)]
                if len(pts) >= 2:
                    paths.append(pts)
        return paths, bridges
    for item in nf.iter_items(design, (nf.LAYER_BORDERS,)):
        seqs, cur = [], None
        for x, y, flags in nf.item_points(item):
            if cur is None or flags.startswith("B"):
                cur = []
                seqs.append(cur)
            cur.append((x, y))
        seqs = [s for s in seqs if s]
        joins = [[a[-1], b[0]] for a, b in zip(seqs, seqs[1:])]
        if seqs and (len(seqs) > 1 or len(seqs[0]) > 2):
            joins.append([seqs[-1][-1], seqs[0][0]])
        bridges.extend(j for j in joins
                       if math.hypot(j[1][0] - j[0][0], j[1][1] - j[0][1]) <= BRIDGE_MAX_M)
        paths.extend(s for s in seqs if len(s) >= 2)
    return paths, bridges


def ray_hit(origin, direction, paths, reach=MAX_REACH_M):
    """Nearest t > 0 where origin + t*direction crosses a segment of `paths`:
    (t, (x, y)) or None."""
    ox, oy = origin
    dx, dy = direction
    best = None
    for path in paths:
        for (x1, y1), (x2, y2) in zip(path, path[1:]):
            ex, ey = x2 - x1, y2 - y1
            den = dx * ey - dy * ex
            if abs(den) < 1e-12:
                continue
            wx, wy = x1 - ox, y1 - oy
            t = (wx * ey - wy * ex) / den
            u = (wx * dy - wy * dx) / den
            if t > 1e-9 and 0.0 <= u <= 1.0 and t <= reach:
                if best is None or t < best[0]:
                    best = (t, (ox + t * dx, oy + t * dy))
    return best


def side_hit(origin, direction, walls):
    """(distance, point, 'wall'|'bridge') or None: a drawn wall first, a fill join as fallback."""
    paths, bridges = walls
    hit = ray_hit(origin, direction, paths)
    if hit is not None:
        return hit[0], hit[1], "wall"
    hit = ray_hit(origin, direction, bridges)
    if hit is not None:
        return hit[0], hit[1], "bridge"
    return None


def _describe(side):
    return None if side is None else dict(m=round(side[0], 2),
                                          at=[round(side[1][0], 2), round(side[1][1], 2)],
                                          source=side[2])


def unit(vx, vy):
    n = math.hypot(vx, vy)
    return (vx / n, vy / n) if n else (0.0, 0.0)


def narrowest(origin, axis, across, walls, window=NARROW_WINDOW_M, step=SCAN_STEP):
    """The smallest opening across `across` within `window` of `origin` along
    `axis`, on the cave side only (outward, the drawn porch converges toward
    the surface - SB 1220's narrows to 0.3 m half a metre outside).
    Returns (s, plus, minus) with side_hit tuples, or None."""
    best = None
    n = int(round(window / step))
    for k in range(0, n + 1):
        s = k * step
        o = (origin[0] + s * axis[0], origin[1] + s * axis[1])
        plus = side_hit(o, across, walls)
        minus = side_hit(o, (-across[0], -across[1]), walls)
        if plus is None or minus is None:
            continue
        w = plus[0] + minus[0]
        if best is None or w < best[0] - 1e-9:
            best = (w, s, plus, minus)
    return None if best is None else best[1:]


# ---------------------------------------------------------------------------
# splays


def best_aligned(splays, v, cone_deg=SPLAY_CONE_DEG):
    """The splay best aligned with unit direction v=(x, y, z): (splay, its
    length along v) or None."""
    best, cos_min = None, math.cos(math.radians(cone_deg))
    for sp in splays:
        c = (sp["dx"] * v[0] + sp["dy"] * v[1] + sp["dz"] * v[2]) / sp["length"]
        if c >= cos_min and (best is None or c > best[0]):
            best = (c, sp)
    if best is None:
        return None
    c, sp = best
    return sp, sp["length"] * c


def splay_side(splays, v3):
    got = best_aligned(splays, v3)
    if got is None:
        return None
    sp, m = got
    return dict(m=round(m, 2), source="splay", splay=sp["n"], inc=round(sp["inc"], 1))


def feret(points, step_deg=5):
    """(min extent, its angle, max extent, its angle) of a point set over all directions."""
    best_min = best_max = None
    for k in range(0, 180, step_deg):
        a = math.radians(k)
        c, s = math.cos(a), math.sin(a)
        pr = [x * c + y * s for x, y in points]
        w = max(pr) - min(pr)
        if best_min is None or w < best_min[0]:
            best_min = (w, k)
        if best_max is None or w > best_max[0]:
            best_max = (w, k)
    return best_min + best_max


def opening_pair(label, splay_a, splay_b, wall_pair, warn):
    """Two sides of one opening from ONE source: both splays, else both walls,
    else what there is. Returns (a, b, source)."""
    if splay_a is not None and splay_b is not None:
        return splay_a, splay_b, "splays"
    if wall_pair is not None:
        a, b = _describe(wall_pair[0]), _describe(wall_pair[1])
        if a["source"] == "bridge" or b["source"] == "bridge":
            warn("%s: s jedne strane nema nacrtanog zida - uzet rub ispune (spoj sekvenci)" % label)
        if splay_a is not None or splay_b is not None:
            warn("%s: splay samo s jedne strane - uzeti zidovi za obje" % label)
        return a, b, "walls"
    if splay_a is None and splay_b is None:
        warn("%s: nema ni splayeva ni zidova - nepoznato" % label)
    else:
        warn("%s: jedna strana iz splaya, druga nepoznata" % label)
    return splay_a, splay_b, "partial"


# ---------------------------------------------------------------------------


def measure(root, stations, entrance, witnessed, count, warn=None):
    """The `entrance_size` block for the sidecar, or None when there is no
    entrance station.

    `stations` are nacrt_finish.Station objects (the cave's), `entrance` the
    decided station name, `witnessed` whether a sign / surface leg / flag named
    it (rule 5), `count` the Broj ulaza nacrt_finish counted. `warn` receives
    the finisher's warnings; the block carries its own copy.
    """
    block_warnings = []

    def say(msg):
        """Worth the operator's eye: into the finisher's warnings and the block."""
        block_warnings.append(msg)
        if warn is not None:
            warn(msg)

    def note(msg):
        """How a reading was obtained: into the block only - the pit reading of
        a horizontal entrance (and the reverse) is always a little lame, and
        only the OSZ prefill knows which of the two is the real one."""
        block_warnings.append(msg)

    by_name = {s.name: s for s in stations}
    E = by_name.get(entrance)
    if E is None:
        return None
    block = dict(station=entrance, witnessed=bool(witnessed), count=count,
                 kind_geo=None, kind_why=None, axis_shot=None, splays=0,
                 horizontal=None, pit=None, warnings=block_warnings)
    if not witnessed:
        say("ulaz nije oznacen (nema znaka ulaza ni povrsinskog vlaka) - dimenzije ulaza "
            "nisu izracunate; nacrtaj znak ulaza na ulaznoj stanici")
        return block

    sps = splay_vectors(root, entrance, E)
    block["splays"] = len(sps)
    cave_shots = [s for s in shots(root) if not s["excluded"] and entrance in (s["a"], s["b"])]
    cave_shots = [s for s in cave_shots if (s["b"] if s["a"] == entrance else s["a"]) in by_name]
    if not cave_shots:
        say("dimenzije ulaza: nijedan vlak ne dodiruje ulaznu stanicu %s" % entrance)
        return block
    if len(cave_shots) > 1:
        note("ulazna stanica %s ima %d vlakova u spilju - os po prvom" % (entrance, len(cave_shots)))
    shot = cave_shots[0]
    other = by_name[shot["b"] if shot["a"] == entrance else shot["a"]]
    block["axis_shot"] = "%s->%s inc=%.1f" % (shot["a"], shot["b"], shot["inc"])

    steep_down = sum(1 for sp in sps if sp["inc"] <= -UD_INC_DEG)
    steep_up = sum(1 for sp in sps if sp["inc"] >= UD_INC_DEG)
    pit_by_shot = abs(shot["inc"]) >= STEEP_DEG
    pit_by_splays = len(sps) >= 4 and steep_down >= PIT_SPLAY_SHARE * len(sps) and steep_up == 0
    block["kind_geo"] = "pit" if (pit_by_shot or pit_by_splays) else "horizontal"
    block["kind_why"] = ("vlak %.0f stupnjeva" % abs(shot["inc"]) if pit_by_shot else
                         "%d od %d splayeva strmo dolje" % (steep_down, len(sps)) if pit_by_splays else
                         "vlak %.0f stupnjeva, %d od %d splayeva strmo dolje"
                         % (abs(shot["inc"]), steep_down, len(sps)))

    plan_walls = wall_paths(root, "plan")
    prof_walls = wall_paths(root, "profile")
    axis = unit(other.x - E.x, other.y - E.y)                 # into the cave, plan
    if axis == (0.0, 0.0):
        axis = (1.0, 0.0)
    across = (-axis[1], axis[0])

    # ---- horizontal candidate: width across the passage (plan) x height (profile)
    nw = narrowest((E.x, E.y), axis, across, plan_walls)
    side_a, side_b, wsrc = opening_pair(
        "sirina ulaza (tlocrt)",
        splay_side(sps, (across[0], across[1], 0.0)),
        splay_side(sps, (-across[0], -across[1], 0.0)),
        None if nw is None else (nw[1], nw[2]), note)
    width = None if (side_a is None or side_b is None) else round(side_a["m"] + side_b["m"], 2)
    nh = narrowest((E.d, E.z), (1.0 if other.d >= E.d else -1.0, 0.0), (0.0, 1.0), prof_walls)
    up_sp = splay_side(sps, (0.0, 0.0, -1.0))
    down_sp = splay_side(sps, (0.0, 0.0, 1.0))
    if up_sp is not None and down_sp is None:
        down_sp = dict(m=0.0, source="floor", note="splay gore bez splaya dolje: stanica je na podu")
    up, down, hsrc = opening_pair("visina ulaza (profil)", up_sp, down_sp,
                                  None if nh is None else (nh[2], nh[1]), note)
    height = None if (up is None or down is None) else round(up["m"] + down["m"], 2)
    block["horizontal"] = dict(
        width_m=width, height_m=height, width_source=wsrc, height_source=hsrc,
        side_a=side_a, side_b=side_b, up=up, down=down,
        axis_into_cave=[round(axis[0], 3), round(axis[1], 3)],
        wall_width_m=None if nw is None else round(nw[1][0] + nw[2][0], 2),
        wall_height_m=None if nh is None else round(nh[1][0] + nh[2][0], 2))

    # ---- pit candidate: the hole in the plan, small x large
    cloud = [(sp["dx"], sp["dy"]) for sp in sps] + [(0.0, 0.0)]
    splay_ext = None
    if len(sps) >= 3:
        wmin, amin, wmax, amax = feret(cloud)
        splay_ext = dict(min_m=round(wmin, 2), min_deg=amin, max_m=round(wmax, 2), max_deg=amax,
                         splays=len(sps))
    hits = []
    for k in range(PIT_RAYS):
        a = 2 * math.pi * k / PIT_RAYS
        h = side_hit((E.x, E.y), (math.cos(a), math.sin(a)), plan_walls)
        if h is not None:
            hits.append(h[1])
    wall_ext = None
    if len(hits) >= PIT_RAYS // 2:
        wmin, amin, wmax, amax = feret(hits)
        wall_ext = dict(min_m=round(wmin, 2), min_deg=amin, max_m=round(wmax, 2), max_deg=amax,
                        rays_hit=len(hits))
    chosen = splay_ext or wall_ext
    if block["kind_geo"] == "pit":
        if splay_ext is None:
            note("jama: samo %d splayeva na ulaznoj stanici - otvor iz zidova" % len(sps))
        if wall_ext is None and len(hits) < PIT_RAYS // 2:
            note("jama: zidovi tlocrta oko stanice %s pogodeni u %d od %d smjerova - stanica izvan crteza?"
                 % (entrance, len(hits), PIT_RAYS))
    block["pit"] = dict(
        width_m=None if chosen is None else chosen["min_m"],
        length_m=None if chosen is None else chosen["max_m"],
        source="splays" if splay_ext else ("walls" if wall_ext else None),
        splay_cloud=splay_ext, wall_footprint=wall_ext)
    return block


def describe(block):
    """One line for the finisher's report."""
    if block is None:
        return "-"
    if not block.get("witnessed"):
        return "nisu izracunate (ulaz nije oznacen)"
    h, p = block.get("horizontal") or {}, block.get("pit") or {}
    return ("horizontalno %s x %s m (%s/%s) | jama %s x %s m (%s) | geometrija kaze: %s (%s)"
            % (h.get("width_m"), h.get("height_m"), h.get("width_source"), h.get("height_source"),
               p.get("width_m"), p.get("length_m"), p.get("source"),
               block.get("kind_geo"), block.get("kind_why")))
