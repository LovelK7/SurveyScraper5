"""Would orienting the separate strokes in KORAK 2 survive cSurvey's Merge?

Emulates cPoints.ReorderSequences (cPoints.vb:1084-1145) - which every Merge runs -
on the user's FINISHED merged items: each item is split back into its strokes, the
strokes are shuffled (selection order) and given random directions (TopoDroid has no
convention), then merged (a) as-is and (b) after each stroke is turned cave-on-right
by the interior vote, as a KORAK 2 pass would. Success = every confidently-judged
stroke agrees with its neighbours (the fill's precondition)."""
import os, random, sys, math
import wall_side_proto as ws, orient_walls_proto as o

C = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "example", "csx_entrances")
CASES = ["Golobreška_nanoekspedicija-1p-lk_pp_lt_fin.csx", "Hrđava_špilja-1s_pp_lt_fixed.csx",
         "272-2p_pp_lt.csx", "kilavcev_cepavpic-1p_pp.csx", "Sopača-1p.csx", "mockup_test1.CSZ"]

def cs_reorder(seqs):
    """seqs: list of [stroke id, reversed?, pts]. Exact port incl. the in-place reversal."""
    old = [list(s) for s in seqs]
    new, nxt = [], None
    while old:
        cur = old[0] if nxt is None else nxt
        old.remove(cur); new.append(cur)
        best, end = float("inf"), cur[2][-1]
        for c in old:
            d = math.dist(end, c[2][0])
            if d < best: best, nxt = d, c
            d = math.dist(end, c[2][-1])
            if d < best:
                best = d; c[1] = not c[1]; c[2] = c[2][::-1]; nxt = c
    return new

def consistent(merged, side):
    """side[id] = +1 cave-left / -1 cave-right as stored in the finished file (None = unjudged)."""
    eff = [side[i] * (-1 if rev else 1) for i, rev, _p in merged if side[i] is not None]
    return len(set(eff)) <= 1

def joins(merged):
    return sum(math.dist(a[2][-1], b[2][0]) for a, b in zip(merged, merged[1:] + merged[:1]))

random.seed(1)
N = 500
for f in CASES:
    root, _ = o.load(os.path.join(C, f))
    for design in ("plan", "profile"):
        D = root.find(design)
        if D is None or D.find("layers") is None: continue
        res = {(r["item"], r["seq"]): r for r in ws.analyse_design(root, design)["results"]}
        for ii, item in o.borders_items(D):
            if item.get("type") != "4": continue
            _m, pts = o.parse_points(item.find("points").get("data"))
            rng = o.sequence_ranges(pts)
            if len(rng) < 2: continue
            strokes = [[(float(p["x"]), float(p["y"])) for p in pts[s:e + 1]] for s, e in rng]
            side = []
            for k in range(len(rng)):
                r = res[(ii, k)]
                ok = r["score"] is not None and abs(r["score"]) >= o.MIN_SCORE and r["coverage"] >= o.MIN_COVERAGE
                side.append((1 if r["score"] > 0 else -1) if ok else None)
            gt = joins([[k, False, s] for k, s in enumerate(strokes)])
            okA = okB = 0; jA = jB = 0.0
            for _ in range(N):
                order = list(range(len(strokes))); random.shuffle(order)
                flips = {k: random.random() < 0.5 for k in order}
                raw = [[k, flips[k], strokes[k][::-1] if flips[k] else strokes[k]] for k in order]
                mA = cs_reorder(raw)
                # KORAK 2: turn each judged stroke cave-on-right (-1); unjudged keep the phone's direction
                pre = []
                for k, rev, p in raw:
                    if side[k] is not None and side[k] * (-1 if rev else 1) > 0:
                        rev, p = not rev, p[::-1]
                    pre.append([k, rev, p])
                mB = cs_reorder(pre)
                okA += consistent(mA, side); okB += consistent(mB, side)
                jA += joins(mA); jB += joins(mB)
            print("%-34s %-7s item %d strokes=%-2d judged=%-2d | merge as-is: %5.1f%% right, joins %.1f m | "
                  "KORAK-2-oriented: %5.1f%% right, joins %.1f m | finished file joins %.1f m"
                  % (f[:34], design, ii, len(strokes), sum(s is not None for s in side),
                     100.0 * okA / N, jA / N, 100.0 * okB / N, jB / N, gt))
