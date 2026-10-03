"""Render a survey after KORAK 2's wall pass (wall_orient.fix): each cave-border item filled
the way cSurvey chains it; strokes left out drawn blue. python render_k2.py <file> [...]"""
import os, sys
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.path import Path
from matplotlib.patches import PathPatch
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "production", "tools"))
import wall_orient as wo
import orient_walls_proto as o

for f in sys.argv[1:]:
    root, _ = o.load(f)
    rep = wo.fix(root)
    fig, axes = plt.subplots(1, 2, figsize=(20, 10))
    for ax, design in zip(axes, ("plan", "profile")):
        D = root.find(design)
        for ii, item in wo.borders_items(D):
            _m, pts = wo.parse_points(item.find("points").get("data") or "")
            seqs = [[wo._xy(p) for p in pts[a:b + 1]] for a, b in wo.sequence_ranges(pts)] if pts else []
            pen = item.find("pen")
            wall = item.get("type") == "4" and pen is not None and pen.get("type") in wo.SAFE_PENS
            if wall and seqs:
                ring = [p for s in seqs for p in s]
                if len(ring) > 2:
                    ax.add_patch(PathPatch(Path(ring + [ring[0]], closed=True), facecolor="wheat", edgecolor="none", alpha=0.8))
                for a, b in zip(seqs, seqs[1:] + seqs[:1]):
                    if len(seqs) > 1:
                        ax.plot([a[-1][0], b[0][0]], [a[-1][1], b[0][1]], ":", color="crimson", lw=1)
            for s in seqs:
                ax.plot([p[0] for p in s], [p[1] for p in s], "-", lw=1.2,
                        color=("black" if (wall and len(seqs) > 1) else ("royalblue" if wall else "gray")))
        for kind, a, b, _w in wo.survey_lines(root, design):
            if kind == "leg":
                ax.plot([a[0], b[0]], [a[1], b[1]], "-", color="red", lw=0.5)
        ax.set_aspect("equal"); ax.invert_yaxis(); ax.autoscale()
        ax.set_title("%s %s | black = merged border, blue = cave wall left as drawn, gray = other lines, red dotted = fill joins"
                     % (os.path.basename(f)[:30], design), fontsize=8)
    out = os.path.join("_out", os.path.splitext(os.path.basename(f))[0] + "_k2.png")
    plt.tight_layout(); plt.savefig(out, dpi=75); plt.close(fig); print(out, wo.describe(rep))
