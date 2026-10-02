"""Prototype: entrance width (plan) and height (profile) from the drawn Borders.

Walls = Borders-layer items split into sequences on the B (BeginSequence)
point flag (cSurvey cPoints.vb:564). cSurvey strokes each sequence on its own
but FILLS the item as one polygon, joining the end of each sequence to the
start of the next with a straight line (cItemFreeHandArea.vb:193-195); GDI+
closes the last back to the first. Those invisible joins are what the printed
map shows as the area's edge wherever no wall was drawn, so they are the
fallback wall when a ray meets no drawn one.

The entrance station comes from the trigpoint flag or
nacrt_finish.decide_entrance. A ray is cast from the station across the
passage (plan: perpendicular to the first in-cave shot; profile: vertical) and
the nearest wall hit on each side gives the opening.

Usage:  python entrance_dims_proto.py <survey.csx|.csz> [...]
        prints one JSON report per file and writes <name>_entrance.png beside
        this script.
"""
import json, math, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "production", "tools"))   # the stage's toolkit
import xml.etree.ElementTree as ET
import nacrt_finish as nf

STEEP_DEG = 60.0      # in-cave shot steeper than this = pit-like entrance
SCAN_M = (-1.0, 1.5)  # along the axis: negative = outward, positive = into the cave
SCAN_STEP = 0.25
MAX_REACH_M = 15.0    # a wall further than this is not this entrance's wall
BRIDGE_MAX_M = 5.0    # a fill bridge longer than this is a drawing-order artifact, not an edge
                      # (SB 1220 profile: the item's closing edge runs 15 m across the cave
                      # and passes 5 cm above the entrance station)
LRUD_INC_DEG = 30.0   # a splay flatter than this is a left/right shot
LRUD_ALONG_M = 0.5    # ...if it stays within this of the cross-section plane
UD_INC_DEG = 45.0     # a splay steeper than this is an up/down shot
UD_HORIZ_M = 0.75     # ...if its horizontal reach is within this


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


def splays(root, name):
    out = []
    for t in root.find("calculate/ts").findall("t"):
        n = t.get("n") or ""
        if n.startswith(name + "("):
            p = _p(t)
            if p is None:
                continue
            out.append(dict(n=n, x=float(p.get("x")), y=float(p.get("y")), z=float(p.get("z")), d=float(p.get("d") or 0.0)))
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


def opening(origin, direction, walls):
    return side_hit(origin, direction, walls), side_hit(origin, (-direction[0], -direction[1]), walls)


def unit(vx, vy):
    n = math.hypot(vx, vy)
    return (vx / n, vy / n) if n else (0.0, 0.0)


def scan_line(origin, axis, across, walls, lo=SCAN_M[0], hi=SCAN_M[1], step=SCAN_STEP):
    out = []
    s = lo
    while s <= hi + 1e-9:
        o = (origin[0] + s * axis[0], origin[1] + s * axis[1])
        p, m = opening(o, across, walls)
        if p is None or m is None:
            out.append([round(s, 2), None, ""])
        else:
            out.append([round(s, 2), round(p[0] + m[0], 2), "" if p[2] == m[2] == "wall" else "bridge"])
        s += step
    return out


def describe(side):
    return None if side is None else dict(m=round(side[0], 2), at=[round(side[1][0], 2), round(side[1][1], 2)], via=side[2])


def point_in_poly(pt, poly):
    x, y = pt
    inside = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            xi = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if xi > x:
                inside = not inside
    return inside


def poly_area(poly):
    a = 0.0
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
        a += x1 * y2 - x2 * y1
    return abs(a) / 2.0


def feret(poly, step_deg=5):
    """(min width, its angle, max width, its angle) of a point set over all directions."""
    best_min = best_max = None
    for k in range(0, 180, step_deg):
        a = math.radians(k)
        c, s = math.cos(a), math.sin(a)
        pr = [x * c + y * s for x, y in poly]
        w = max(pr) - min(pr)
        if best_min is None or w < best_min[0]:
            best_min = (w, k)
        if best_max is None or w > best_max[0]:
            best_max = (w, k)
    return best_min + best_max


def footprint_around(pt, paths):
    """The smallest drawn sequence that, closed on itself, contains `pt`."""
    best = None
    for p in paths:
        if len(p) >= 3 and point_in_poly(pt, p):
            a = poly_area(p)
            if best is None or a < best[0]:
                best = (a, p)
    return None if best is None else best[1]


def analyse(path):
    root = load(path)
    st = stations(root)
    sh = shots(root)
    ent, how = entrance_station(root)
    report = dict(file=os.path.basename(path), entrance=ent, entrance_how=how, warnings=[])
    if ent not in st:
        report["warnings"].append("entrance station %r has no coordinates" % ent)
        return report, None
    E = st[ent]

    cave_shots = [s for s in sh if not s["excluded"] and ent in (s["a"], s["b"])]
    if not cave_shots:
        report["warnings"].append("no counted shot touches the entrance station")
        return report, None
    if len(cave_shots) > 1:
        report["warnings"].append("entrance station has %d in-cave shots, using the first" % len(cave_shots))
    shot = cave_shots[0]
    other = st[shot["b"] if shot["a"] == ent else shot["a"]]
    report["axis_shot"] = "%s->%s inc=%.1f" % (shot["a"], shot["b"], shot["inc"])
    pit = abs(shot["inc"]) >= STEEP_DEG
    report["kind"] = "pit" if pit else "horizontal"

    # ---- plan
    plan_walls = wall_paths(root, "plan")
    axis = unit(other["x"] - E["x"], other["y"] - E["y"])        # into the cave
    if pit or axis == (0.0, 0.0):
        axis = (1.0, 0.0)
    across = (-axis[1], axis[0])
    plus, minus = opening((E["x"], E["y"]), across, plan_walls)
    plan = dict(axis_into_cave=[round(axis[0], 3), round(axis[1], 3)],
                side_a=describe(plus), side_b=describe(minus))
    plan["width_m"] = None if (plus is None or minus is None) else round(plus[0] + minus[0], 2)
    for side in (plus, minus):
        if side is not None and side[2] == "bridge":
            report["warnings"].append("plan: no wall drawn on one side of the entrance - used the area's fill edge")
    plan["width_scan"] = scan_line((E["x"], E["y"]), axis, across, plan_walls)
    if pit:
        p2, m2 = opening((E["x"], E["y"]), axis, plan_walls)
        plan["length_m"] = None if (p2 is None or m2 is None) else round(p2[0] + m2[0], 2)
        ring = footprint_around((E["x"], E["y"]), plan_walls[0])
        if ring is None:
            report["warnings"].append("pit: no drawn ring encloses the entrance station")
        else:
            wmin, amin, wmax, amax = feret(ring)
            plan["footprint"] = dict(points=len(ring), min_m=round(wmin, 2), min_deg=amin, max_m=round(wmax, 2), max_deg=amax,
                                     bbox=[round(min(x for x, _ in ring), 2), round(min(y for _, y in ring), 2),
                                           round(max(x for x, _ in ring), 2), round(max(y for _, y in ring), 2)])
    report["plan"] = plan

    # ---- profile (y = depth, positive down; x = developed distance d)
    prof_walls = wall_paths(root, "profile")
    o = (E["d"], E["z"])
    up = side_hit(o, (0.0, -1.0), prof_walls)
    down = side_hit(o, (0.0, 1.0), prof_walls)
    prof = dict(station_at=[round(E["d"], 2), round(E["z"], 2)], up=describe(up), down=describe(down))
    prof["height_m"] = None if (up is None or down is None) else round(up[0] + down[0], 2)
    if up is not None and up[2] == "bridge":
        report["warnings"].append("profile: no ceiling drawn over the entrance - used the area's fill edge")
    if down is not None and down[2] == "bridge":
        report["warnings"].append("profile: no floor drawn under the entrance - used the area's fill edge")
    sign = 1.0 if other["d"] >= E["d"] else -1.0
    prof["height_scan"] = scan_line(o, (sign, 0.0), (0.0, 1.0), prof_walls)
    report["profile"] = prof

    # ---- splay cross-check (LRUD at the entrance station)
    lat = {"a": [], "b": []}
    ups, downs, used = [], [], []
    for sp in splays(root, ent):
        dx, dy, dz = sp["x"] - E["x"], sp["y"] - E["y"], sp["z"] - E["z"]
        horiz = math.hypot(dx, dy)
        inc = math.degrees(math.atan2(-dz, horiz))      # + = up
        along = dx * axis[0] + dy * axis[1]
        lateral = dx * across[0] + dy * across[1]
        if abs(inc) >= UD_INC_DEG and horiz <= UD_HORIZ_M:
            (ups if inc > 0 else downs).append(abs(dz))
            used.append([sp["n"], "up" if inc > 0 else "down", round(inc, 1), round(abs(dz), 2)])
        elif abs(inc) < LRUD_INC_DEG and abs(along) <= LRUD_ALONG_M:
            key = "a" if lateral > 0 else "b"
            lat[key].append(abs(lateral))
            used.append([sp["n"], key, round(inc, 1), round(abs(lateral), 2)])
    pick = max if pit else min       # a pit's rim is the farthest shot, a passage wall the nearest
    a = pick(lat["a"]) if lat["a"] else None
    b = pick(lat["b"]) if lat["b"] else None
    u = max(ups) if ups else None
    d = max(downs) if downs else None
    report["splays"] = dict(width_m=None if (a is None or b is None) else round(a + b, 2),
                            side_a_m=None if a is None else round(a, 2), side_b_m=None if b is None else round(b, 2),
                            height_m=None if (u is None and d is None) else round((u or 0) + (d or 0), 2),
                            up_m=None if u is None else round(u, 2), down_m=None if d is None else round(d, 2), used=used)
    return report, (root, st, E, axis, across, plan_walls, prof_walls)


def draw(report, ctx, out_png):
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    root, st, E, axis, across, plan_walls, prof_walls = ctx
    fig, axes = plt.subplots(1, 2, figsize=(18, 9))
    for ax, name, walls, o, sides in (
            (axes[0], "plan", plan_walls, (E["x"], E["y"]), (report["plan"]["side_a"], report["plan"]["side_b"])),
            (axes[1], "profile", prof_walls, (E["d"], E["z"]), (report["profile"]["up"], report["profile"]["down"]))):
        for p in walls[0]:
            ax.plot([q[0] for q in p], [q[1] for q in p], "-", lw=1.2, color="C0")
        for p in walls[1]:
            ax.plot([q[0] for q in p], [q[1] for q in p], "--", lw=0.7, color="gray")
        for n, s in st.items():
            px, py = (s["x"], s["y"]) if name == "plan" else (s["d"], s["z"])
            ax.plot(px, py, "r^"); ax.annotate(n, (px, py), color="red", fontsize=12)
        for h in sides:
            if h:
                ax.plot([o[0], h["at"][0]], [o[1], h["at"][1]], "-", color="magenta" if h["via"] == "wall" else "orange", lw=2)
                ax.plot(h["at"][0], h["at"][1], "o", color="magenta" if h["via"] == "wall" else "orange")
        ax.set_aspect("equal"); ax.grid(True, lw=0.3)
        ax.set_xlim(o[0] - 5, o[0] + 5); ax.set_ylim(o[1] - 4, o[1] + 4)
        if name == "profile":
            ax.invert_yaxis()
        ax.set_title("%s  %s  (blue = drawn wall, grey dashed = fill bridge, magenta = wall hit, orange = bridge hit)"
                     % (report["file"], name), fontsize=9)
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
