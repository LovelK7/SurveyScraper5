"""Auto-merge a FRESH import (one stroke per item): every open cave-pen stroke of a design
into one border, turned by the survey and chained by automerge_sim.auto_merge; render it."""
import os, sys, math, time
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.path import Path
from matplotlib.patches import PathPatch
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "production", "tools"))
import wall_orient as wo
import automerge_sim as am

def run(path, design, ax):
    import orient_walls_proto as o
    root, _ = o.load(path)
    D = root.find(design)
    lines = wo.survey_lines(root, design)
    strokes, closed = [], []
    wgrid = wo._Grid()
    for ii, item in wo.borders_items(D):
        _m, pts = wo.parse_points((item.find("points").get("data") if item.find("points") is not None else "") or "")
        for a, b in wo.sequence_ranges(pts):
            poly = [wo._xy(p) for p in pts[a:b + 1]]
            for k, (p, q) in enumerate(zip(poly, poly[1:])):
                wgrid.add_segment(p, q, (k, p, q))
            pen = item.find("pen")
            if item.get("type") != "4" or pen is None or pen.get("type") not in wo.SAFE_PENS or len(poly) < 2:
                continue
            (closed if math.dist(poly[0], poly[-1]) < 0.05 else strokes).append(poly)
    sgrid = wo._Grid()
    for s in wo._interior_samples(lines, wgrid):
        sgrid.add_point(s[:2], s)
    judged, raw = {}, []
    for k, poly in enumerate(strokes):
        sc, cov = wo.wall_side(poly, sgrid, wgrid)
        judged[k] = (1 if sc > 0 else -1) if sc is not None and abs(sc) >= wo.MIN_SCORE and cov >= wo.MIN_COVERAGE else None
        raw.append([k, False, poly])
    t = time.time()
    merged = am.auto_merge(raw, judged)
    dt = time.time() - t
    ring = [p for _k, _r, s in merged for p in s]
    ax.add_patch(PathPatch(Path(ring + [ring[0]], closed=True), facecolor="wheat", edgecolor="none"))
    for poly in closed:
        ax.add_patch(PathPatch(Path(poly, closed=True), facecolor="wheat", edgecolor="none"))
    for _k, _r, s in merged:
        ax.plot([p[0] for p in s], [p[1] for p in s], "-k", lw=1.2)
    for a, b in zip(merged, merged[1:] + merged[:1]):
        ax.plot([a[2][-1][0], b[2][0][0]], [a[2][-1][1], b[2][0][1]], ":", color="crimson", lw=1)
    for kind, a, b, _w in lines:
        if kind == "leg":
            ax.plot([a[0], b[0]], [a[1], b[1]], "-", color="red", lw=0.6)
    ax.set_aspect("equal"); ax.invert_yaxis()
    j = sum(math.dist(a[2][-1], b[2][0]) for a, b in zip(merged, merged[1:] + merged[:1]))
    ax.set_title("%s %s: %d strokes (%d unjudged) -> one border, joins %.1f m, %.1fs; red dotted = fill joins"
                 % (os.path.basename(path)[:28], design, len(strokes), sum(v is None for v in judged.values()), j, dt), fontsize=8)

C = "../../../example/csx_entrances/"
for f in sys.argv[1:]:
    fig, axes = plt.subplots(1, 2, figsize=(20, 10))
    for ax, d in zip(axes, ("plan", "profile")):
        run(C + f, d, ax)
    out = "_out/" + os.path.splitext(f)[0] + "_automerge.png"
    plt.tight_layout(); plt.savefig(out, dpi=75); print(out)
