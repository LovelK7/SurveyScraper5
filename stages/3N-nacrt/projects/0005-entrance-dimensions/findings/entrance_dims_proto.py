"""Prototype: entrance width and height at the decided entrance station.

Rules (user, 2026-10-02 - see brief.md section 3, phase 2):

  1. The surveyor's splays at the entrance station come first: they were
     shot at the entrance on purpose. Per direction (left, right, up, down)
     the splay best aligned with that direction is the measurement, provided
     it is within SPLAY_CONE_DEG of it.
  2. The drawn walls are the fallback, measured at the narrowest point within
     NARROW_WINDOW_M of the station along the passage axis.
  3. A pit's opening is estimated from the splay cloud (plan projection of
     every splay from the station, min/max Feret extents) with the walls as
     fallback; width = the smaller number, visina/duljina = the larger.
  4. Both numbers round to one decimal (0.1 m).

Walls = Borders-layer items split into sequences on the B (BeginSequence)
point flag (cSurvey cPoints.vb:564). cSurvey strokes each sequence on its own
but FILLS the item as one polygon, joining the end of each sequence to the
start of the next with a straight line (cItemFreeHandArea.vb:193-195); those
joins (when short) stand in for an undrawn wall.

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
SPLAY_CONE_DEG = 40.0   # a splay counts for a direction when within this cone of it
NARROW_WINDOW_M = 0.5   # the wall width is the narrowest within this of the station, along the axis
SCAN_STEP = 0.1
MAX_REACH_M = 15.0      # a wall further than this is not this entrance's wall
BRIDGE_MAX_M = 5.0      # a fill bridge longer than this is a drawing-order artifact, not an edge
PIT_RAYS = 24           # directions for the wall-based pit footprint


def load(path):
    if path.lower().endswith(".csz"):
        import zipfile
        with zipfile.ZipFile(path) as z:
            return ET.fromstring(z.read(nf.DATA_ENTRY))
    return ET.parse(path).getroot()


def _p(t):
    # <t> carries a direct <p> whose d is always 0; the profile distance lives
    # in the <tcon><p> copies, so read those first.
    p = t.find("tcons/tcon/p")
    if p is None:
        p = t.find("p")
    return p


def stations(root):
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


def splay_vectors(root, name, E):
    """Every splay from station `name` as a vector from it: dx, dy (plan), dz (depth, + = down)."""
    out = []
    for t in root.find("calculate/ts").findall("t"):
        n = t.get("n") or ""
        if not n.startswith(name + "("):
            continue
        p = _p(t)
        if p is None:
            continue
        dx, dy, dz = float(p.get("x")) - E["x"], float(p.get("y")) - E["y"], float(p.get("z")) - E["z"]
        length = math.sqrt(dx * dx + dy * dy + dz * dz)
        if length < 1e-6:
            continue
        out.append(dict(n=n, dx=dx, dy=dy, dz=dz, length=length,
                        inc=math.degrees(math.atan2(-dz, math.hypot(dx, dy)))))
    return out


def shots(root):
    out = []
    for seg in root.find("segments").findall("segment"):
        if seg.get("splay") == "1":
            continue
        out.append(dict(id=seg.get("id"), a=seg.get("from"), b=seg.get("to"),
                        inc=float(seg.get("inclination") or 0), brg=float(seg.get("bearing") or 0),
                        surface=seg.get("surface") == "1",
                        excluded=any(seg.get(f) == "1" for f in nf.NOT_IN_CAVE_FLAGS)))
    return out


def entrance_station(root):
    tps = root.find("trigpoints")
    if tps is not None:
        for tp in tps.findall("trigpoint"):
            if tp.get("entrance") == nf.ENTRANCE_MAIN:
                return tp.get("name"), "trigpoint entrance=2"
    sts = nf.read_stations(root)
    cave, outside = nf.split_cave_stations(root, sts)
    warns = []
    chosen, witnesses = nf.decide_entrance(root, cave, warns.append, outside)
    return chosen, "decide_entrance: " + witnesses.get("decision", "")


# ---------------------------------------------------------------------------
# walls


def wall_paths(root, design_name):
    """(drawn sequences, fill bridges) of the Borders layer, each a list of (x, y) lists."""
    paths, bridges = [], []
    for item in nf.iter_items(root.find(design_name), (nf.LAYER_BORDERS,)):
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
    return None if side is None else dict(m=round(side[0], 2), at=[round(side[1][0], 2), round(side[1][1], 2)], via=side[2])


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
        if best is None or w < best[0] - 1e-9 or (abs(w - best[0]) <= 1e-9 and abs(s) < abs(best[1])):
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


def measure_side(label, splays, v3, origin2d, dir2d, walls_at, warn):
    """One side of the opening: the best-aligned splay, else the wall hit prepared in `walls_at`.

    v3 is the unit 3-D direction of the side (plan dx, dy; depth dz), used for the splay;
    walls_at is the side_hit tuple for the wall fallback (already at the narrowest point).
    """
    got = best_aligned(splays, v3)
    if got is not None:
        sp, m = got
        return dict(m=round(m, 2), source="splay", splay=sp["n"], inc=round(sp["inc"], 1))
    if walls_at is not None:
        d = describe(walls_at)
        d.update(source=walls_at[2])
        if walls_at[2] == "bridge":
            warn("%s: no splay and no wall drawn - used the area's fill edge" % label)
        return d
    warn("%s: no splay and no wall - side unknown" % label)
    return None


def analyse(path):
    root = load(path)
    st = stations(root)
    sh = shots(root)
    ent, how = entrance_station(root)
    report = dict(file=os.path.basename(path), entrance=ent, entrance_how=how, warnings=[])
    warn = report["warnings"].append
    if ent not in st:
        warn("entrance station %r has no coordinates" % ent)
        return report, None
    E = st[ent]
    sps = splay_vectors(root, ent, E)

    cave_shots = [s for s in sh if not s["excluded"] and ent in (s["a"], s["b"])]
    if not cave_shots:
        warn("no counted shot touches the entrance station")
        return report, None
    if len(cave_shots) > 1:
        warn("entrance station has %d in-cave shots, using the first" % len(cave_shots))
    shot = cave_shots[0]
    other = st[shot["b"] if shot["a"] == ent else shot["a"]]
    report["axis_shot"] = "%s->%s inc=%.1f" % (shot["a"], shot["b"], shot["inc"])
    pit = abs(shot["inc"]) >= STEEP_DEG
    report["kind"] = "pit" if pit else "horizontal"
    report["splays_at_station"] = len(sps)

    plan_walls = wall_paths(root, "plan")
    prof_walls = wall_paths(root, "profile")
    axis = unit(other["x"] - E["x"], other["y"] - E["y"])        # into the cave, plan
    if axis == (0.0, 0.0):
        axis = (1.0, 0.0)
    across = (-axis[1], axis[0])

    if not pit:
        # ---- width, plan: splays first, else the narrowest wall opening near the station
        nw = narrowest((E["x"], E["y"]), axis, across, plan_walls)
        wall_plus, wall_minus, at_s = (nw[1], nw[2], nw[0]) if nw else (None, None, None)
        side_a = measure_side("plan side a", sps, (across[0], across[1], 0.0), (E["x"], E["y"]), across, wall_plus, warn)
        side_b = measure_side("plan side b", sps, (-across[0], -across[1], 0.0), (E["x"], E["y"]), (-across[0], -across[1]), wall_minus, warn)
        width = None if (side_a is None or side_b is None) else round(side_a["m"] + side_b["m"], 2)
        report["plan"] = dict(axis_into_cave=[round(axis[0], 3), round(axis[1], 3)],
                              side_a=side_a, side_b=side_b, width_m=width,
                              wall_narrowest=None if nw is None else dict(
                                  at_s=round(at_s, 2), width_m=round(wall_plus[0] + wall_minus[0], 2),
                                  plus=describe(wall_plus), minus=describe(wall_minus)))

        # ---- height, profile: up/down splays first; no down splay with an up splay = station on the floor
        nh = narrowest((E["d"], E["z"]), (1.0 if other["d"] >= E["d"] else -1.0, 0.0), (0.0, 1.0), prof_walls)
        wall_down, wall_up, at_d = (nh[1], nh[2], nh[0]) if nh else (None, None, None)
        up = measure_side("profile up", sps, (0.0, 0.0, -1.0), (E["d"], E["z"]), (0.0, -1.0), wall_up, warn)
        down_splay = best_aligned(sps, (0.0, 0.0, 1.0))
        if down_splay is not None:
            down = dict(m=round(down_splay[1], 2), source="splay", splay=down_splay[0]["n"], inc=round(down_splay[0]["inc"], 1))
        elif up is not None and up["source"] == "splay":
            down = dict(m=0.0, source="station on the floor (up splay, no down splay)")
        else:
            down = measure_side("profile down", sps, (0.0, 0.0, 1.0), (E["d"], E["z"]), (0.0, 1.0), wall_down, warn)
        height = None if (up is None or down is None) else round(up["m"] + down["m"], 2)
        report["profile"] = dict(station_at=[round(E["d"], 2), round(E["z"], 2)], up=up, down=down, height_m=height,
                                 wall_narrowest=None if nh is None else dict(
                                     at_s=round(at_d, 2), height_m=round(wall_down[0] + wall_up[0], 2),
                                     up=describe(wall_up), down=describe(wall_down)))
        report["osz"] = dict(sirina_ulaza=round_osz(width), visina_duljina_ulaza=round_osz(height),
                             sources=[side_a and side_a["source"], side_b and side_b["source"],
                                      up and up["source"], down and down["source"]])
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
        if len(hits) >= 3:
            wmin, amin, wmax, amax = feret(hits)
            wall_ext = dict(min_m=round(wmin, 2), min_deg=amin, max_m=round(wmax, 2), max_deg=amax, rays_hit=len(hits))
        else:
            warn("pit: the plan walls around the station give only %d ray hits" % len(hits))
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


def draw(report, ctx, out_png):
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
                ax.plot([o[0], o[0] + sp["dx"]], [o[1], o[1] + sp["dy"]], "-", color="lightgray", lw=0.6)
            else:
                along = sp["dx"] * axis[0] + sp["dy"] * axis[1]
                sgn = 1.0 if True else -1.0
                ax.plot([o[0], o[0] + sgn * along], [o[1], o[1] + sp["dz"]], "-", color="lightgray", lw=0.6)
        if report["kind"] == "horizontal":
            sec = report[name]
            sides = (sec["side_a"], sec["side_b"]) if name == "plan" else (sec["up"], sec["down"])
            dirs = (across, (-across[0], -across[1])) if name == "plan" else ((0.0, -1.0), (0.0, 1.0))
            for side, d in zip(sides, dirs):
                if side and side.get("m"):
                    col = {"splay": "green", "wall": "magenta", "bridge": "orange"}.get(side["source"], "black")
                    ax.plot([o[0], o[0] + side["m"] * d[0]], [o[1], o[1] + side["m"] * d[1]], "-", color=col, lw=2.5)
        ax.set_aspect("equal"); ax.grid(True, lw=0.3)
        ax.set_xlim(o[0] - 5, o[0] + 5); ax.set_ylim(o[1] - 4, o[1] + 4)
        if name == "profile":
            ax.invert_yaxis()
        ax.set_title("%s  %s  (blue wall, grey dashed fill bridge, light grey splays; green = splay, magenta = wall, orange = bridge)"
                     % (report["file"], name), fontsize=8)
    plt.tight_layout(); plt.savefig(out_png, dpi=90)


if __name__ == "__main__":
    for path in sys.argv[1:]:
        report, ctx = analyse(path)
        if ctx is not None:
            try:
                draw(report, ctx, os.path.join(HERE, os.path.splitext(os.path.basename(path))[0] + "_entrance.png"))
            except ImportError:
                report["warnings"].append("matplotlib not installed - no plot written")
        print(json.dumps(report, ensure_ascii=False, indent=1))
