"""Could KORAK 2 do the merge itself? (project 0006)

Each of the user's FINISHED merged wall items is scattered back into what the
import gives - separate strokes, random order, random direction - and rebuilt
by an automatic merge:
  1. every stroke the survey can judge is turned cave-on-right (absolute: there
     is no item yet to agree with);
  2. the chain order with the shortest fill joins is searched (relocation);
     a stroke the survey cannot judge may also be reversed where that fits better.
Success = the rebuilt item has the user's directions (all agree) and joins no
longer than the user's own (+0.5 m). cSurvey's own Merge is the baseline."""
import os, random, math, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "production", "tools"))
import wall_orient as wo
import merge_sim as ms

def auto_merge(strokes, judged):
    """strokes: [[id, rev, pts]]; judged[id] = side in the CURRENT direction (+1 left, -1 right) or None.
    Judged strokes are turned cave-on-right and stay so; unjudged ones may flip.
    For every start stroke: greedy nearest end->start walk, then relocation (with
    flips for the unjudged) until nothing improves; the shortest result wins."""
    base = []
    for k, rev, p in strokes:
        if judged[k] is not None and judged[k] > 0:
            rev, p = not rev, p[::-1]
        base.append((k, rev, p))
    n = len(base)
    free = {i for i in range(n) if judged[base[i][0]] is None}

    def pts(i, f):
        return base[i][2][::-1] if f else base[i][2]

    def cost(o):        # o = [(index, flipped)]
        return sum(math.dist(pts(a, fa)[-1], pts(b, fb)[0]) for (a, fa), (b, fb) in zip(o, o[1:] + o[:1]))

    best = None
    for s0 in range(n):
        o, left = [(s0, False)], set(range(n)) - {s0}
        while left:
            end = pts(*o[-1])[-1]
            opts = [(math.dist(end, pts(i, f)[0]), i, f) for i in left for f in ((False, True) if i in free else (False,))]
            _d, i, f = min(opts)
            o.append((i, f)); left.discard(i)
        improved = True
        while improved:
            improved = False
            for k in range(n):
                rest = [x for x in o if x[0] != k]
                cands = [rest[:j] + [(k, f)] + rest[j:] for j in range(len(rest) + 1)
                         for f in ((False, True) if k in free else (False,))]
                c = min(cands, key=cost)
                if cost(c) < cost(o) - 1e-9:
                    o, improved = c, True
        if best is None or cost(o) < cost(best):
            best = o
    out = []
    for i, f in best:
        k, rev, p = base[i]
        out.append([k, rev != f, p[::-1] if f else p])
    return out


def _main():
  random.seed(2)
  N = 300
  for f in ms.CASES:
      root, _ = wo_load = (None, None)
      import orient_walls_proto as o
      root, _ = o.load(os.path.join(ms.C, f))
      for design in ("plan", "profile"):
          D = root.find(design)
          if D is None or D.find("layers") is None: continue
          res = {(r["item"], r["seq"]): r for r in __import__("wall_side_proto").analyse_design(root, design)["results"]}
          for ii, item in o.borders_items(D):
              if item.get("type") != "4": continue
              _m, pts = o.parse_points(item.find("points").get("data"))
              rng = o.sequence_ranges(pts)
              if len(rng) < 2: continue
              strokes = [[(float(p["x"]), float(p["y"])) for p in pts[a:b + 1]] for a, b in rng]
              side = []
              for k in range(len(rng)):
                  r = res[(ii, k)]
                  ok = r["score"] is not None and abs(r["score"]) >= o.MIN_SCORE and r["coverage"] >= o.MIN_COVERAGE
                  side.append((1 if r["score"] > 0 else -1) if ok else None)
              gt = ms.joins([[k, False, s] for k, s in enumerate(strokes)])
              okC = okA = 0; jC = jA = 0.0
              for _ in range(N):
                  order = list(range(len(strokes))); random.shuffle(order)
                  flips = {k: random.random() < 0.5 for k in order}
                  raw = [[k, flips[k], strokes[k][::-1] if flips[k] else strokes[k]] for k in order]
                  mC = ms.cs_reorder([list(x) for x in raw])
                  cur = {k: (None if side[k] is None else side[k] * (-1 if rev else 1)) for k, rev, _p in raw}
                  mA = auto_merge([list(x) for x in raw], cur)
                  for m, tag in ((mC, "C"), (mA, "A")):
                      good = ms.consistent(m, side) and ms.joins(m) <= gt + 0.5
                      if tag == "C": okC += good; jC += ms.joins(m)
                      else: okA += good; jA += ms.joins(m)
              print("%-30s %-7s strokes=%-2d | cSurvey Merge: %5.1f%% as good as by hand (joins %.1f m) | auto-merge: %5.1f%% (joins %.1f m) | by hand %.1f m"
                    % (f[:30], design, len(strokes), 100.0 * okC / N, jC / N, 100.0 * okA / N, jA / N, gt))


if __name__ == "__main__":
    _main()
