"""Prototype: entrance width and height at the decided entrance station.

Rules (user, 2026-10-02/03 - see brief.md section 3, phase 2):

  1. The surveyor's splays at the entrance station come first: they were
     shot at the entrance on purpose. Per direction (left, right, up, down)
     the splay best aligned with that direction is the measurement, provided
     it is within SPLAY_CONE_DEG of it. Both sides of one opening come from
     the same source: splays for both, else the drawn walls for both.
  2. The drawn walls are the fallback, measured at the narrowest point within
     NARROW_WINDOW_M of the station along the passage axis, cave side only.
  3. A pit's opening is estimated from the splay cloud (plan projection of
     every splay from the station, min/max Feret extents) with the walls as
     fallback; width = the smaller number, visina/duljina = the larger.
  4. Both numbers round to one decimal (0.1 m).

Walls = Borders-layer items split into sequences on the B (BeginSequence)
point flag (cSurvey cPoints.vb:564). cSurvey strokes each sequence on its own
but FILLS the item as one polygon, joining the end of each sequence to the
start of the next with a straight line (cItemFreeHandArea.vb:193-195); those
joins (when short) stand in for an undrawn wall. A raw TopoDroid export
(no <calculate>, flat items) is handled too: stations are traversed from the
shots and the walls are its `name="wall"` lines.

Usage:  python entrance_dims_proto.py <survey.csx|.csz> [...]
        prints one JSON report per file and writes <name>_entrance.png beside
        this script.
"""
import json, math, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "production", "tools"))   # the stage's toolkit
import xml.etree.ElementTree as ET
import nacrt_finish as nf

STEEP_DEG = 60.0        # in-cave shot steeper than this = pit-like entrance
PIT_SPLAY_SHARE = 1 / 3.0   # ...or this share of the station's splays dive steeper than UD_INC_DEG
SPLAY_CONE_DEG = 40.0   # a splay counts for a direction when within this cone of it
UD_INC_DEG = 45.0       # a splay steeper than this is a down/up shot (pit test)
NARROW_WINDOW_M = 0.5   # the wall width is the narrowest within this of the station, along the axis
SCAN_STEP = 0.1
MAX_REACH_M = 15.0      # a wall further than this is not this entrance's wall
BRIDGE_MAX_M = 5.0      # a fill bridge longer than this is a drawing-order artifact, not an edge
PIT_RAYS = 24           # directions for the wall-based pit footprint
RAW_WALL_NAMES = ("wall", "wall:presumed")


def load(path):
    if path.lower().endswith(".csz"):
        import zipfile
        with zipfile.ZipFile(path) as z:
            return ET.fromstring(z.read(nf.DATA_ENTRY))
    return ET.parse(path).getroot()


def is_raw(root):
    """A TopoDroid export cSurvey has not calculated yet."""
    return root.find("calculate/ts") is None


def _p(t):
    # <t> carries a direct <p> whose d is always 0; the profile distance lives
    # in the <tcon><p> copies, so read those first.
    p = t.find("tcons/tcon/p")
    if p is None:
        p = t.find("p")
    return p


def shots(root):
    out = []
    for seg in root.find("segments").findall("segment"):
        if seg.get("splay") == "1":
            continue
        out.append(dict(id=seg.get("id"), a=seg.get("from"), b=seg.get("to"),
                        dist=float(seg.get("distance") or 0),
                        inc=float(seg.get("inclination") or 0), brg=float(seg.get("bearing") or 0),
                        extend=-1.0 if seg.get("direction") == "1" else 1.0,   # TopoDroid: direction="1" = extend left
                        surface=seg.get("surface") == "1",
                        excluded=any(seg.get(f) == "1" for f in nf.NOT_IN_CAVE_FLAGS)))
    return out


def shot_vector(dist, inc, brg):
    """(dx, dy, dz) in design metres: y grows south, z grows down (cSurvey's frame)."""
    h = dist * math.cos(math.radians(inc))
    return (h * math.sin(math.radians(brg)), -h * math.cos(math.radians(brg)), -dist * math.sin(math.radians(inc)))


def stations(root):
    """{name: {x, y, z, d}} from <calculate>, or traversed from the shots for a raw export."""
    if not is_raw(root):
        out = {}
        for t in root.find("calculate/ts").findall("t"):
            n = t.get("n") or ""
            if not n or "(" in n:
                continue
            p = _p(t)
            if p is None:
                continue
            out[n] = dict(x=float(p.get("x")), y=float(p.get("y")), z=float(p.get("z")), d=float(p.get("d") or 0.0))
        return out
    sh = [s for s in shots(root) if s["a"] and s["b"]]
    props = root.find("properties")
    origin = (props.get("origin") if props is not None else None) or (sh[0]["a"] if sh else None)
    out = {origin: dict(x=0.0, y=0.0, z=0.0, d=0.0)} if origin else {}
    pending = True
    while pending:
        pending = False
        for s in sh:
            dx, dy, dz = shot_vector(s["dist"], s["inc"], s["brg"])
            dd = s["extend"] * s["dist"] * math.cos(math.radians(s["inc"]))
            if s["a"] in out and s["b"] not in out:
                A = out[s["a"]]
                out[s["b"]] = dict(x=A["x"] + dx, y=A["y"] + dy, z=A["z"] + dz, d=A["d"] + dd)
                pending = True
            elif s["b"] in out and s["a"] not in out:
                B = out[s["b"]]
                out[s["a"]] = dict(x=B["x"] - dx, y=B["y"] - dy, z=B["z"] - dz, d=B["d"] - dd)
                pending = True
    return out


def splay_vectors(root, name, E):
    """Every splay from station `name` as a vector from it: dx, dy (plan), dz (depth, + = down)."""
    out = []
    if is_raw(root):
        for seg in root.find("segments").findall("segment"):
            if seg.get("splay") == "1" and seg.get("from") == name:
                dx, dy, dz = shot_vector(float(seg.get("distance") or 0), float(seg.get("inclination") or 0),
                                         float(seg.get("bearing") or 0))
                out.append(dict(n=seg.get("to") or "%s(?)" % name, dx=dx, dy=dy, dz=dz))
    else:
        for t in root.find("calculate/ts").findall("t"):
            n = t.get("n") or ""
            if not n.startswith(name + "("):
                continue
            p = _p(t)
            if p is None:
                continue
            out.append(dict(n=n, dx=float(p.get("x")) - E["x"], dy=float(p.get("y")) - E["y"], dz=float(p.get("z")) - E["z"]))
    for sp in out:
        sp["length"] = math.sqrt(sp["dx"] ** 2 + sp["dy"] ** 2 + sp["dz"] ** 2)
        sp["inc"] = math.degrees(math.atan2(-sp["dz"], math.hypot(sp["dx"], sp["dy"])))
    return [sp for sp in out if sp["length"] > 1e-6]


def entrance_station(root, st, warn):
    """(station name, how). The finisher's flag, else nacrt_finish's witnesses."""
    tps = root.find("trigpoints")
    if tps is not None:
        for tp in tps.findall("trigpoint"):
            if tp.get("entrance") == nf.ENTRANCE_MAIN:
                return tp.get("name"), "trigpoint entrance=2"
    objs = [nf.Station(n, s["x"], s["y"], s["z"], s["d"]) for n, s in st.items()]
    cave, outside = nf.split_cave_stations(root, objs)
    outer = [s for s in objs if s.name in outside]
    chosen, witnesses = nf.decide_entrance(root, cave, warn, outer)
    how = "decide_entrance: " + witnesses.get("decision", "")
    # Tavnjak (Mune): the plan's entrance sign sat on a ledge 20 m down the
    # shaft, the profile's sign and the highest station agreed on the rim.
    # nacrt_finish takes the plan when the two signs disagree; here the sign
    # that agrees with the highest station wins instead (proposed rule change).
    if not witnesses.get("surface_leg") and chosen != witnesses.get("highest"):
        surface = (outer, nf.surface_links(root, {s.name for s in cave}))
        for design in ("plan", "profile"):
            w = nf.witness_sign(root, cave, design, surface)
            if w is not None and w["station"] == witnesses.get("highest"):
                warn("znak ulaza u %su pokazuje na najvisu stanicu %s, drugi znak na %s - uzimam %s"
                     % ("tlocrt" if design == "plan" else "profil", w["station"], chosen, w["station"]))
                return w["station"], "%s sign agrees with the highest station (other sign overruled)" % design
    return chosen, how


# ---------------------------------------------------------------------------
# walls


def wall_paths(root, design_name):
    """(drawn sequences, fill bridges) of the walls, each a list of (x, y) lists.

    cSurvey file: the Borders layer. Raw TopoDroid: the `wall` lines (no
    sequences, no fill, so no bridges).
    """
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
        bridges.extend(j for j in joins if math.hypot(j[1][0] - j[0][0], j[1][1] - j[0][1]) <= BRIDGE_MAX_M)
        paths.extend(s for s in seqs if len(s) >= 2)
    return paths, bridges


def ray_hit(origin, direction, paths, reach=MAX_REACH_M):
    """Nearest t > 0 where origin + t*direction crosses a segment of `paths`."""
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
    """(distance, point, 'wall'|'bridge') or None: drawn wall first, fill bridge as fallback."""
    paths, bridges = walls
    hit = ray_hit(origin, direction, paths)
    if hit is not None:
        return hit[0], hit[1], "wall"
    hit = ray_hit(origin, direction, bridges)
    if hit is not None:
        return hit[0], hit[1], "bridge"
    return None


def describe(side):
    return None if side is None else dict(m=round(side[0], 2), at=[round(side[1][0], 2), round(side[1][1], 2)], source=side[2])


def unit(vx, vy):
    n = math.hypot(vx, vy)
    return (vx / n, vy / n) if n else (0.0, 0.0)


def narrowest(origin, axis, across, walls, window=NARROW_WINDOW_M, step=SCAN_STEP):
    """The smallest opening across `across` within `window` of `origin` along `axis`.

    Only the cave side of the station is scanned: outward, the drawn walls
    converge toward the surface (SB 1220's porch narrows to 0.3 m in the
    profile half a metre outside the entrance) and would fake a narrower opening.
    Returns (s, plus, minus) for the narrowest sample, or None when no sample
    has both sides; plus/minus are side_hit tuples.
    """
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
    """The splay best aligned with unit direction v=(x, y, z); (splay, its length along v) or None."""
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


def round_osz(m):
    """One decimal (user, 2026-10-03: a tenth of a metre, not whole metres)."""
    return None if m is None else math.floor(m * 10 + 0.5) / 10.0


# ---------------------------------------------------------------------------


def opening_pair(label, splay_a, splay_b, wall_pair, warn):
    """Two sides of one opening from ONE source: both splays, else both walls, else what there is."""
    if splay_a is not None and splay_b is not None:
        return splay_a, splay_b, "splays"
    if wall_pair is not None:
        a, b = describe(wall_pair[0]), describe(wall_pair[1])
        if a["source"] == "bridge" or b["source"] == "bridge":
            warn("%s: no wall drawn on one side - used the area's fill edge" % label)
        if splay_a is not None or splay_b is not None:
            warn("%s: only one side has a splay - took the drawn walls for both" % label)
        return a, b, "walls"
    if splay_a is None and splay_b is None:
        warn("%s: no splays and no walls - unknown" % label)
    else:
        warn("%s: one side from a splay, the other unknown" % label)
    return splay_a, splay_b, "partial"


def analyse(path, kind=None):
    """`kind` = "pit" | "horizontal" when the registry knows the cave's type (SB / OSZ
    *Vrsta objekta*: jama vs špilja); the geometric test is only the fallback -
    kilavčeva pljeskavica is a pit whose rim station has flat splays and a 35° first
    shot, indistinguishable from SB 1220's entrance slope by geometry alone."""
    root = load(path)
    st = stations(root)
    sh = shots(root)
    report = dict(file=os.path.basename(path), raw=is_raw(root), warnings=[])
    warn = report["warnings"].append
    ent, how = entrance_station(root, st, warn)
    report.update(entrance=ent, entrance_how=how)
    if ent not in st:
        warn("entrance station %r has no coordinates" % ent)
        return report, None
    E = st[ent]
    sps = splay_vectors(root, ent, E)
    report["splays_at_station"] = len(sps)
    top = min(st.items(), key=lambda kv: kv[1]["z"])
    if top[0] != ent and E["z"] - top[1]["z"] > 2.0:
        warn("entrance %s lies %.1f m below the highest station %s - check the entrance" % (ent, E["z"] - top[1]["z"], top[0]))

    cave_shots = [s for s in sh if not s["excluded"] and ent in (s["a"], s["b"])]
    if not cave_shots:
        warn("no counted shot touches the entrance station")
        return report, None
    if len(cave_shots) > 1:
        warn("entrance station has %d in-cave shots, using the first" % len(cave_shots))
    shot = cave_shots[0]
    other = st[shot["b"] if shot["a"] == ent else shot["a"]]
    report["axis_shot"] = "%s->%s inc=%.1f" % (shot["a"], shot["b"], shot["inc"])
    steep_down = sum(1 for sp in sps if sp["inc"] <= -UD_INC_DEG)
    steep_up = sum(1 for sp in sps if sp["inc"] >= UD_INC_DEG)
    pit_by_shot = abs(shot["inc"]) >= STEEP_DEG
    pit_by_splays = len(sps) >= 4 and steep_down >= PIT_SPLAY_SHARE * len(sps) and steep_up == 0
    geo_kind = "pit" if (pit_by_shot or pit_by_splays) else "horizontal"
    geo_why = ("shot %.0f deg" % abs(shot["inc"]) if pit_by_shot else
               "%d of %d splays dive >%.0f deg" % (steep_down, len(sps), UD_INC_DEG) if pit_by_splays else
               "shot %.0f deg, %d of %d splays dive" % (abs(shot["inc"]), steep_down, len(sps)))
    if kind in ("pit", "horizontal"):
        pit = kind == "pit"
        report["kind_why"] = "registry says %s (geometry: %s, %s)" % (kind, geo_kind, geo_why)
        if kind != geo_kind:
            warn("registry type %s, geometry suggests %s - following the registry" % (kind, geo_kind))
    else:
        pit = geo_kind == "pit"
        report["kind_why"] = geo_why
    report["kind"] = "pit" if pit else "horizontal"

    plan_walls = wall_paths(root, "plan")
    prof_walls = wall_paths(root, "profile")
    axis = unit(other["x"] - E["x"], other["y"] - E["y"])        # into the cave, plan
    if axis == (0.0, 0.0):
        axis = (1.0, 0.0)
    across = (-axis[1], axis[0])

    if not pit:
        # ---- width, plan
        nw = narrowest((E["x"], E["y"]), axis, across, plan_walls)
        side_a, side_b, wsrc = opening_pair("plan width", splay_side(sps, (across[0], across[1], 0.0)),
                                            splay_side(sps, (-across[0], -across[1], 0.0)),
                                            None if nw is None else (nw[1], nw[2]), warn)
        width = None if (side_a is None or side_b is None) else round(side_a["m"] + side_b["m"], 2)
        report["plan"] = dict(axis_into_cave=[round(axis[0], 3), round(axis[1], 3)],
                              side_a=side_a, side_b=side_b, width_m=width, width_source=wsrc,
                              wall_narrowest=None if nw is None else dict(
                                  at_s=round(nw[0], 2), width_m=round(nw[1][0] + nw[2][0], 2),
                                  plus=describe(nw[1]), minus=describe(nw[2])))

        # ---- height, profile: an up splay with no down splay = the station stands on the floor
        nh = narrowest((E["d"], E["z"]), (1.0 if other["d"] >= E["d"] else -1.0, 0.0), (0.0, 1.0), prof_walls)
        up_sp = splay_side(sps, (0.0, 0.0, -1.0))
        down_sp = splay_side(sps, (0.0, 0.0, 1.0))
        if up_sp is not None and down_sp is None:
            down_sp = dict(m=0.0, source="floor", note="up splay, no down splay: station on the floor")
        up, down, hsrc = opening_pair("profile height", up_sp, down_sp,
                                      None if nh is None else (nh[2], nh[1]), warn)
        height = None if (up is None or down is None) else round(up["m"] + down["m"], 2)
        report["profile"] = dict(station_at=[round(E["d"], 2), round(E["z"], 2)], up=up, down=down,
                                 height_m=height, height_source=hsrc,
                                 wall_narrowest=None if nh is None else dict(
                                     at_s=round(nh[0], 2), height_m=round(nh[1][0] + nh[2][0], 2),
                                     up=describe(nh[2]), down=describe(nh[1])))
        report["osz"] = dict(sirina_ulaza=round_osz(width), visina_duljina_ulaza=round_osz(height),
                             sources=[wsrc, hsrc])
    else:
        # ---- pit: the opening is a hole in the plan - splay cloud first, wall footprint as fallback
        cloud = [(sp["dx"], sp["dy"]) for sp in sps] + [(0.0, 0.0)]
        splay_ext = None
        if len(sps) >= 3:
            wmin, amin, wmax, amax = feret(cloud)
            splay_ext = dict(min_m=round(wmin, 2), min_deg=amin, max_m=round(wmax, 2), max_deg=amax, splays=len(sps))
        else:
            warn("pit: only %d splays at the entrance station - splay cloud too thin" % len(sps))
        hits = []
        for k in range(PIT_RAYS):
            a = 2 * math.pi * k / PIT_RAYS
            h = side_hit((E["x"], E["y"]), (math.cos(a), math.sin(a)), plan_walls)
            if h is not None:
                hits.append(h[1])
        wall_ext = None
        if len(hits) >= PIT_RAYS // 2:
            wmin, amin, wmax, amax = feret(hits)
            wall_ext = dict(min_m=round(wmin, 2), min_deg=amin, max_m=round(wmax, 2), max_deg=amax, rays_hit=len(hits))
        else:
            warn("pit: the plan walls around the station give only %d of %d ray hits - station outside the drawing?"
                 % (len(hits), PIT_RAYS))
        chosen = splay_ext or wall_ext
        report["plan"] = dict(axis_into_cave=[round(axis[0], 3), round(axis[1], 3)],
                              splay_cloud=splay_ext, wall_footprint=wall_ext,
                              chosen="splays" if splay_ext else ("walls" if wall_ext else None))
        depth = best_aligned(sps, (0.0, 0.0, 1.0))
        report["profile"] = dict(station_at=[round(E["d"], 2), round(E["z"], 2)],
                                 first_drop_m=None if depth is None else round(depth[1], 2),
                                 note="a pit has no entrance height; the drop below the rim is informative only")
        report["osz"] = dict(sirina_ulaza=round_osz(chosen and chosen["min_m"]),
                             visina_duljina_ulaza=round_osz(chosen and chosen["max_m"]),
                             sources=[report["plan"]["chosen"]] * 2)
    return report, (root, st, E, axis, across, plan_walls, prof_walls, sps)


def draw(report, ctx, out_png, half_width=5.0):
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    root, st, E, axis, across, plan_walls, prof_walls, sps = ctx
    fig, axes = plt.subplots(1, 2, figsize=(18, 9))
    for ax, name, walls, o in ((axes[0], "plan", plan_walls, (E["x"], E["y"])),
                               (axes[1], "profile", prof_walls, (E["d"], E["z"]))):
        for p in walls[0]:
            ax.plot([q[0] for q in p], [q[1] for q in p], "-", lw=1.2, color="C0")
        for p in walls[1]:
            ax.plot([q[0] for q in p], [q[1] for q in p], "--", lw=0.7, color="gray")
        for n, s in st.items():
            px, py = (s["x"], s["y"]) if name == "plan" else (s["d"], s["z"])
            ax.plot(px, py, "r^"); ax.annotate(n, (px, py), color="red", fontsize=12)
        for sp in sps:
            if name == "plan":
                ax.plot([o[0], o[0] + sp["dx"]], [o[1], o[1] + sp["dy"]], "-", color="silver", lw=0.6)
            else:
                ax.plot([o[0], o[0] + math.hypot(sp["dx"], sp["dy"])], [o[1], o[1] + sp["dz"]], "-", color="silver", lw=0.6)
        if report["kind"] == "horizontal":
            sec = report[name]
            sides = (sec["side_a"], sec["side_b"]) if name == "plan" else (sec["up"], sec["down"])
            dirs = (across, (-across[0], -across[1])) if name == "plan" else ((0.0, -1.0), (0.0, 1.0))
            for side, d in zip(sides, dirs):
                if side and side.get("m"):
                    col = {"splay": "green", "wall": "magenta", "bridge": "orange"}.get(side["source"], "black")
                    ax.plot([o[0], o[0] + side["m"] * d[0]], [o[1], o[1] + side["m"] * d[1]], "-", color=col, lw=2.5)
        ax.set_aspect("equal"); ax.grid(True, lw=0.3)
        ax.set_xlim(o[0] - half_width, o[0] + half_width); ax.set_ylim(o[1] - 0.8 * half_width, o[1] + 0.8 * half_width)
        if name == "profile":
            ax.invert_yaxis()
        ax.set_title("%s  %s  %s | OSZ %s x %s | blue wall, grey dashed fill bridge, silver splays; green = splay, magenta = wall, orange = bridge"
                     % (report["file"], name, report["kind"], report["osz"]["sirina_ulaza"], report["osz"]["visina_duljina_ulaza"]), fontsize=7)
    plt.tight_layout(); plt.savefig(out_png, dpi=90)


if __name__ == "__main__":
    args = sys.argv[1:]
    kind = None
    if "--kind" in args:                      # --kind pit|horizontal : the registry's type
        i = args.index("--kind")
        kind = args[i + 1]
        del args[i:i + 2]
    for path in args:
        report, ctx = analyse(path, kind)
        if ctx is not None:
            try:
                draw(report, ctx, os.path.join(HERE, os.path.splitext(os.path.basename(path))[0] + "_entrance.png"))
            except ImportError:
                report["warnings"].append("matplotlib not installed - no plot written")
        print(json.dumps(report, ensure_ascii=False, indent=1))
