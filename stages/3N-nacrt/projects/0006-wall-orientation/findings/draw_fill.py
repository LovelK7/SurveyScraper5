"""Render each wall item's FILL the way cSurvey builds it (sequences chained end->start,
closed last->first, alternate fill), before and after orient_walls_proto. Usage:
python draw_fill.py <survey> <design> [xmin xmax ymin ymax]"""
import copy, os, sys
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.path import Path
from matplotlib.patches import PathPatch
import orient_walls_proto as o

def polys(root, design):
    out = []
    for _ii, item in o.borders_items(root.find(design)):
        if item.get("type") != "4":
            continue
        _m, pts = o.parse_points(item.find("points").get("data") or "")
        out.append([[(float(p["x"]), float(p["y"])) for p in pts[s:e + 1]] for s, e in o.sequence_ranges(pts)])
    return out

def panel(ax, seqsets, title, box):
    for seqs in seqsets:
        ring = [pt for s in seqs for pt in s]
        if len(ring) < 3:
            continue
        ax.add_patch(PathPatch(Path(ring + [ring[0]], closed=True), facecolor="wheat", edgecolor="none", alpha=0.8))
        for k, s in enumerate(seqs):
            ax.plot([p[0] for p in s], [p[1] for p in s], "-", color="black", lw=1.6)
            m = len(s) // 2
            if len(s) > 2:
                ax.annotate("", xy=s[m], xytext=s[m - 1], arrowprops=dict(arrowstyle="->", color="crimson", lw=1.4))
            if len(seqs) > 1:
                ax.annotate(str(k), s[0], color="blue", fontsize=8)
        for a, b in zip(seqs, seqs[1:] + seqs[:1]):
            if len(seqs) > 1:
                ax.plot([a[-1][0], b[0][0]], [a[-1][1], b[0][1]], ":", color="gray", lw=1)
    ax.set_aspect("equal"); ax.invert_yaxis(); ax.set_title(title, fontsize=9)
    if box:
        ax.set_xlim(box[0], box[1]); ax.set_ylim(box[3], box[2])

path, design = sys.argv[1], sys.argv[2]
box = [float(v) for v in sys.argv[3:7]] if len(sys.argv) >= 7 else None
root, _ = o.load(path)
before = polys(root, design)
rep = o.orient(root); rrep = o.reorder(root)
after = polys(root, design)
fig, axes = plt.subplots(1, 2, figsize=(16, 8))
panel(axes[0], before, "%s %s - as saved" % (os.path.basename(path), design), box)
panel(axes[1], after, "after orient + reorder (red arrows = drawing direction, numbers = sequence order)", box)
plt.tight_layout()
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_out", os.path.splitext(os.path.basename(path))[0] + "_%s_fill.png" % design)
plt.savefig(out, dpi=80); print(out)
