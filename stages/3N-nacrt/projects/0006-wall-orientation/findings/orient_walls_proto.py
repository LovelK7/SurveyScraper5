"""Prototype: reverse the wall sequences that run the wrong way round the cave (project 0006).

Convention: in a cSurvey file the cave lies on the RIGHT of every wall's
stored direction (y down, as on screen). TopoDroid's guide asks for walls
drawn counterclockwise, cave on the left (TopoDroidAndCSurvey.pdf p.1-2),
and the import reverses every stroke (cImportTopoDroidHelper.vb:68-77) - so a
wall drawn by the book arrives cave-on-right. The finished Golobreška profile
(the user's hand fix, 2026-10-03) reads cave-on-right on all 7 sequences.

The side each sequence actually has comes from wall_side_proto (the survey
is inside the cave). A sequence is reversed only when the vote is clear
(|score| >= MIN_SCORE over >= MIN_COVERAGE of its length); a doubtful one is
reported and left alone.

Only cave-border areas are touched: Borders items of type 4 whose pen is one
of the non-directional cave pens (cPen.vb:1164-1167). Pit / overhang /
chimney lines carry one-sided decorations, and their direction is meaning.

The reversal mirrors cSequence.Reverse (cSequence.vb:229-242): point order
flipped, the B/P/T prefix moves to the new first point; segment bindings are
resolved first (a bare `S` means "same segment as the previous point",
cPoints.vb:585-592) and re-serialized; point joins
(<pointsjoins> "layer,item,point") are remapped to the new indices.

Usage:  python orient_walls_proto.py <survey.csx|.csz> [-o OUT] [--dry-run]
"""
import math, os, sys, zipfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import xml.etree.ElementTree as ET
import wall_side_proto as ws

SAFE_PENS = {"1", "8", "25", "26"}    # Cave, PresumedCave, TooNarrowCave, UnderlyingCave
MIN_SCORE = 0.6
MIN_COVERAGE = 0.3
REORDER_GAIN = 0.8           # a new sequence order is kept only if its joins are < 80% of the old


def chain_order(seqs_xy):
    """Sequence order with the shortest fill joins, NO reversals (direction is
    settled by the interior vote). Relocation search: take each sequence out
    and reinsert it where it adds the least join length, until nothing
    improves; sequence 0 stays first. cSurvey's own ReorderSequences
    (cPoints.vb:1084-1145) is a greedy nearest-END walk that also reverses -
    it flips a coin at an entrance mouth, and a nearest-start walk cannot fix
    Hrčava's profile, whose far-end piece sits last in the chain while it
    belongs between sequences 4 and 5 (29 m of joins vs 1 m)."""
    n = len(seqs_xy)
    gap = lambda a, b: math.dist(seqs_xy[a][-1], seqs_xy[b][0])
    cost = lambda o: sum(gap(a, b) for a, b in zip(o, o[1:] + o[:1]))
    order = list(range(n))
    improved = True
    while improved:
        improved = False
        for k in range(1, n):
            base = [s for s in order if s != k]
            best = min((base[:i] + [k] + base[i:] for i in range(1, len(base) + 1)), key=cost)
            if cost(best) < cost(order) - 1e-9:
                order, improved = best, True
    return order


# ---------------------------------------------------------------------------
# <points data> as cSurvey parses it (cPoints.vb:496-599)


def parse_points(data):
    """(meta prefix, [point dict]) with bindings RESOLVED (bare S inherits)."""
    meta = ""
    if data.startswith("#"):
        cut = data.index(" ") + 1
        meta, data = data[:cut], data[cut:]
    toks = data.split()
    pts, i, prev_bind = [], 0, ""
    while i < len(toks):
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
                p["T"], f = f[1], f[2:]
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
    """cSequence.Reverse on pts[s..e]: flip, hand the B/P/T prefix to the new first point."""
    head = {k: pts[s][k] for k in ("B", "P", "T")}
    seg = pts[s:e + 1][::-1]
    for k in ("B", "P", "T"):
        seg[-1][k] = False if k != "T" else None
    seg[0].update(head)
    pts[s:e + 1] = seg


# ---------------------------------------------------------------------------


def borders_items(design_el):
    """[(item index in its layer, item)] for the Borders layer, in file order - the index
    cSurvey's <pointsjoins> uses."""
    out = []
    for layer in design_el.find("layers").findall("layer"):
        if layer.get("type") != ws.LAYER_BORDERS:
            continue
        items_el = layer.find("items")
        kids = (items_el.findall("item") if items_el is not None else []) + layer.findall("item")
        out.extend(enumerate(kids))
    return out


def remap_joins(design_el, item_index, mapping):
    pj = design_el.find("pointsjoins")
    if pj is None:
        return 0
    n = 0
    for j in pj.findall("pointsjoin"):
        parts = []
        for ref in (j.get("data") or "").split():
            L, I, P = ref.split(",")
            if L == ws.LAYER_BORDERS and int(I) == item_index and int(P) in mapping:
                P = str(mapping[int(P)])
                n += 1
            parts.append("%s,%s,%s" % (L, I, P))
        j.set("data", " ".join(parts) + " ")
    return n


def fill_report(pts_ranges_xy):
    """Total length of the fill's straight joins and how many cross a drawn sequence."""
    seqs = pts_ranges_xy
    if len(seqs) < 2:
        return dict(join_m=0.0, crossing=0)
    joins = [(a[-1], b[0]) for a, b in zip(seqs, seqs[1:] + seqs[:1])]
    crossing = 0
    for p0, q0 in joins:
        if math.dist(p0, q0) < 1e-6:
            continue
        # shrink 2% at both ends: a join starts ON a sequence end and must not count that touch
        p = (p0[0] + 0.02 * (q0[0] - p0[0]), p0[1] + 0.02 * (q0[1] - p0[1]))
        q = (q0[0] - 0.02 * (q0[0] - p0[0]), q0[1] - 0.02 * (q0[1] - p0[1]))
        for s in seqs:
            if any(ws.segments_cross(p, q, a, b) for a, b in zip(s, s[1:])):
                crossing += 1
                break
    return dict(join_m=round(sum(math.dist(p, q) for p, q in joins), 2), crossing=crossing)


def orient(root):
    """Reverse the sequences that run against their own item. Returns the report.

    Relative, not absolute (corpus 2026-10-03): the fill only needs the
    sequences of ONE item to agree. 272's plan and Hrčava's plan are merged
    items running consistently cave-on-LEFT; forcing cave-on-right flipped
    each stroke on its own, kept the order, and blew the fill joins up from
    2.8 to 45.7 m and 5.1 to 36.5 m. So: the item's confident, length-weighted
    majority is "the right way"; only a confident minority is reversed; and
    the flips are kept only when the fill gets no longer and no more crossed.
    A one-sequence item has nothing to agree with and is left alone.
    """
    report = []
    for design in ("plan", "profile"):
        D = root.find(design)
        if D is None or D.find("layers") is None:
            continue
        A = ws.analyse_design(root, design)
        verdict = {(r["item"], r["seq"]): r for r in A["results"]}
        for ii, item in borders_items(D):
            if item.get("type") != ws.AREA_TYPE:
                continue
            pts_el = item.find("points")
            if pts_el is None:
                continue
            meta, pts = parse_points(pts_el.get("data") or "")
            ranges = sequence_ranges(pts)
            if len(ranges) < 2:
                continue
            # a sequence whose first point says P carries its own <pen> child of <points>,
            # in sequence order (cPoints.vb:567-571); otherwise the item's pen applies
            pen = item.find("pen")
            own = iter(pts_el.findall("pen"))
            seq_pen = [(next(own, None) if pts[s]["P"] else pen) for s, _e in ranges]
            sides, doubtful = {}, []
            for si in range(len(ranges)):
                r = verdict.get((ii, si))
                sp = seq_pen[si]
                if sp is None or sp.get("type") not in SAFE_PENS:
                    doubtful.append((si, "pen %s - direction is meaning, not touched" % (sp.get("type") if sp is not None else "?")))
                elif r is None or r["score"] is None:
                    doubtful.append((si, "no survey in sight"))
                elif abs(r["score"]) < MIN_SCORE or r["coverage"] < MIN_COVERAGE:
                    doubtful.append((si, "score %+.2f, coverage %.2f" % (r["score"], r["coverage"])))
                else:
                    sides[si] = (1 if r["score"] > 0 else -1, r["length"])
            left = sum(L for s, L in sides.values() if s > 0)
            right = sum(L for s, L in sides.values() if s < 0)
            xy = lambda P: [[(float(p["x"]), float(p["y"])) for p in P[s:e + 1]] for s, e in ranges]
            before = fill_report(xy(pts))
            entry = dict(design=design, item=ii, sequences=len(ranges), flipped=[], doubtful=doubtful,
                         majority=None, joins_remapped=0, fill_before=before, fill_after=before, applied=False)
            report.append(entry)
            if not sides or max(left, right) < 0.6 * (left + right):
                entry["note"] = "no clear majority (left %.1f m, right %.1f m)" % (left, right)
                continue
            major = 1 if left > right else -1
            entry["majority"] = "cave left" if major > 0 else "cave right"
            minority = [si for si, (s, _L) in sides.items() if s != major]
            if not minority:
                continue
            trial = [dict(p) for p in pts]
            mapping = {}
            for si in minority:
                s, e = ranges[si]
                reverse_range(trial, s, e)
                mapping.update({k: s + e - k for k in range(s, e + 1)})
            after = fill_report(xy(trial))
            entry.update(flipped=minority, fill_after=after)
            if after["join_m"] > before["join_m"] + 0.01 or after["crossing"] > before["crossing"]:
                entry["note"] = "flips would make the fill worse - left for the operator"
                continue
            pts_el.set("data", serialize_points(meta, trial))
            entry.update(applied=True, joins_remapped=remap_joins(D, ii, mapping))
    return report


def reorder(root):
    """Second pass: put each multi-sequence wall item's sequences into chain order."""
    report = []
    for design in ("plan", "profile"):
        D = root.find(design)
        if D is None or D.find("layers") is None:
            continue
        for ii, item in borders_items(D):
            if item.get("type") != ws.AREA_TYPE:
                continue
            pts_el = item.find("points")
            meta, pts = parse_points(pts_el.get("data") or "")
            ranges = sequence_ranges(pts)
            if len(ranges) < 3:
                continue         # two sequences have only one order
            xy = [[(float(p["x"]), float(p["y"])) for p in pts[s:e + 1]] for s, e in ranges]
            order = chain_order(xy)
            if order == list(range(len(ranges))):
                continue
            before, after = fill_report(xy), fill_report([xy[k] for k in order])
            ok = after["join_m"] < REORDER_GAIN * before["join_m"] and after["crossing"] <= before["crossing"]
            entry = dict(design=design, item=ii, order=order, fill_before=before, fill_after=after, applied=ok)
            report.append(entry)
            if not ok:
                continue
            # pens ride with their sequence: the <pen> children follow the P-sequences' new order
            pens = pts_el.findall("pen")
            it = iter(pens)
            seq_pen = [next(it) if pts[s]["P"] else None for s, _e in ranges]
            new_pts, mapping = [], {}
            for k in order:
                s, e = ranges[k]
                for j in range(s, e + 1):
                    mapping[j] = len(new_pts)
                    new_pts.append(pts[j])
            for p in pens:
                pts_el.remove(p)
            for k in order:
                if seq_pen[k] is not None:
                    pts_el.append(seq_pen[k])
            pts_el.set("data", serialize_points(meta, new_pts))
            entry["joins_remapped"] = remap_joins(D, ii, mapping)
    return report


def load(path):
    with open(path, "rb") as f:
        csz = f.read(4) == b"PK\x03\x04"
    if csz:
        with zipfile.ZipFile(path) as z:
            return ET.fromstring(z.read("_data.xml")), True
    return ET.parse(path).getroot(), False


if __name__ == "__main__":
    args = sys.argv[1:]
    dry = "--dry-run" in args
    args = [a for a in args if a not in ("--dry-run", "--reorder")]
    out = None
    if "-o" in args:
        k = args.index("-o"); out = args[k + 1]; del args[k:k + 2]
    for path in args:
        root, csz = load(path)
        rep = orient(root)
        rrep = reorder(root) if "--reorder" in sys.argv else []
        print("==", os.path.basename(path))
        for r in rrep:
            print("  REORDER %-7s item %-2d order=%s applied=%s fill %s -> %s"
                  % (r["design"], r["item"], r["order"], r["applied"], r["fill_before"], r["fill_after"]))
        for r in rep:
            print("  %-7s item %-2d seqs=%-2d majority=%s flip=%s applied=%s fill %s -> %s %s\n           doubtful=%s"
                  % (r["design"], r["item"], r["sequences"], r["majority"], r["flipped"], r["applied"],
                     r["fill_before"], r["fill_after"], r.get("note", ""), r["doubtful"]))
        if not dry and out:
            assert not csz, "prototype writes .csx only"
            ET.ElementTree(root).write(out, encoding="utf-8", xml_declaration=True)
            print("  wrote", out)
