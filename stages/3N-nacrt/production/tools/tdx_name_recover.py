#!/usr/bin/env python3
"""Recover the TopoDroid symbol name of every item in a cSurvey file after import.

Spike T8 of projects/0007-symbol-themes (brief §3.1 addendum, §3.6 T8).
cSurvey's TopoDroid import keeps only its own sign/pen/brush types: the
TopoDroid `name` and the `tdxpp:<name>` marker KORAK 1 writes into `options`
are dropped. This tool gets them back by matching geometry against the
pre-import file (the raw export or the KORAK 1 `_prep`/`_pp` output).

What the import does to geometry (cImportTopoDroidHelper.vb ConvertItem,
pConvertItem; checked on every pair in the repo, findings/t8-name-recovery.md):
  * coordinates are copied as they are (Points.Parse) - no transform,
    crosssection items aside (MoveBy Location, always 0,0 in this build);
  * the point order is reversed unless the item has reversed="1";
  * closed="1" only re-flags the sequence (CloseSequences);
  * the point flags are re-encoded: `B` gains segment bindings (`BS<guid>`,
    `S`), so the raw `data` strings never compare equal;
  * item count and point count are kept; lines can become areas (wall,
    rock-border, wall:presumed) and items are regrouped into layers.
KORAK 2 (wall_orient.py, run by fix_imported_linetypes.py) and a hand Merge in
cSurvey then fold several wall strokes into ONE item with several sequences,
and may reverse any sequence. So the unit matched here is the SEQUENCE.

Method:
  1. exact - key = (design, set of coordinates at 1 cm). Order- and
     reversal-proof. Duplicate keys are fine when every candidate carries the
     same name; otherwise the sequence is reported ambiguous.
  2. tolerant - for what is left, in the same design and the same class
     (point / path): points by nearest neighbour within --tol; paths by
     mutual coverage (share of each side's vertices within --tol of the other
     polyline, the smaller of the two). A point is accepted anywhere within
     --tol, a path at >= --min-score; either only when no differently named
     runner-up is within --margin. Greedy best-first, one-to-one.
  3. anything else is reported - `miss` for a TopoDroid-stamped sequence with
     no source, `native` for an item drawn in cSurvey (no TopoDroid datarow),
     and every source sequence left unused. Nothing is guessed.

Usage:
  python production/tools/tdx_name_recover.py recover PRE.csx POST.csx|POST.csz [--json OUT]
      [--tol 0.05] [--min-score 0.5] [--margin 0.15] [--quiet]

Stdlib only. Read-only on both inputs.
"""

import argparse
import json
import math
import re
import sys
import zipfile
import xml.etree.ElementTree as ET

DATA_ENTRY = "_data.xml"
TDX_STAMP = "TopoDroid"
DESIGNS = ("plan", "profile")
_NUM = re.compile(r"^[-+]?(\d|\.\d)")


# ------------------------------------------------------------------ loading

def load_root(path):
    """Parse a .csx, or the _data.xml inside a .csz (zip)."""
    with open(path, "rb") as f:
        head = f.read(4)
    if head == b"PK\x03\x04":
        with zipfile.ZipFile(path) as z:
            if DATA_ENTRY not in z.namelist():
                raise ValueError("zip has no %s - not a cSurvey file" % DATA_ENTRY)
            return ET.fromstring(z.read(DATA_ENTRY))
    return ET.parse(path).getroot()


def parse_sequences(data):
    """`points@data` -> list of sequences, each a list of (x, y).

    Both formats share the shape `x y [flags]`; a flag token starting with B
    begins a new sequence (raw TopoDroid: `B`; cSurvey: `B[P][T#][L][S<id>]`).
    """
    toks = (data or "").split()
    seqs, cur, i = [], [], 0
    while i + 1 < len(toks):
        try:
            x, y = float(toks[i]), float(toks[i + 1])
        except ValueError:
            i += 1
            continue
        i += 2
        flag = ""
        if i < len(toks) and not _NUM.match(toks[i]):
            flag = toks[i]
            i += 1
        if flag.startswith("B") and cur:
            seqs.append(cur)
            cur = []
        cur.append((x, y))
    if cur:
        seqs.append(cur)
    return seqs


def tdxpp_name(options):
    for tok in (options or "").split():
        if tok.startswith("tdxpp:"):
            return tok[len("tdxpp:"):]
    return None


def pre_units(root):
    """Every sequence of every TopoDroid item in a pre-import file."""
    if root.find("properties") is not None and \
            root.find("properties").get("creat_postprocessed"):
        raise ValueError("PRE is already a post-import save (creat_postprocessed set)")
    units = []
    for design in DESIGNS:
        d = root.find(design)
        if d is None:
            continue
        idx = 0
        for item, xsec in _iter_pre_items(d, False):
            kind = (item.get("type") or "").lower()
            name = item.get("name") or ""
            marker = tdxpp_name(item.get("options"))
            pts = item.find("points")
            seqs = parse_sequences(pts.get("data") if pts is not None else "")
            for s, seq in enumerate(seqs):
                units.append({
                    "design": design, "index": idx, "seq": s, "kind": kind,
                    "tdx_name": marker or name, "prep_name": name,
                    "name_from": "tdxpp" if marker else "name",
                    "text": item.get("text"), "xsection": xsec, "coords": seq,
                })
            idx += 1
    return units


def _iter_pre_items(parent, xsec):
    for item in parent.findall("item"):
        yield item, xsec
        for cs in item.findall("crosssection"):
            yield from _iter_pre_items(cs, True)


def post_units(root):
    """Every sequence of every item in a post-import (cSurvey) file."""
    units, items = [], []
    for design in DESIGNS:
        layers = root.find(design + "/layers")
        if layers is None:
            continue
        for layer in layers.findall("layer"):
            its = layer.find("items")
            if its is None:
                continue
            for k, item in enumerate(its.findall("item")):
                pen, brush = item.find("pen"), item.find("brush")
                row = item.findtext("datarow") or ""
                pts = item.find("points")
                seqs = parse_sequences(pts.get("data") if pts is not None else "")
                info = {
                    "design": design, "layer": layer.get("type"),
                    "layer_name": layer.get("name"), "index": k,
                    "type": item.get("type"), "category": item.get("category"),
                    "sign": item.get("sign"), "name": item.get("name"),
                    "text": item.get("text"),
                    "pen": pen.get("type") if pen is not None else None,
                    "brush": brush.get("type") if brush is not None else None,
                    "tdx_stamp": row.startswith(TDX_STAMP),
                    "n_seq": len(seqs), "sequences": [],
                }
                items.append(info)
                for s, seq in enumerate(seqs):
                    units.append({"item": info, "design": design, "seq": s,
                                  "coords": seq})
    return units, items


# ------------------------------------------------------------------ geometry

def _q(v):
    return int(round(v * 100.0))


def coord_key(coords):
    return frozenset((_q(x), _q(y)) for x, y in coords)


def _cls(n_or_kind):
    if isinstance(n_or_kind, str):
        return "point" if n_or_kind == "point" else "path"
    return "point" if n_or_kind == 1 else "path"


def _bbox(c):
    xs = [p[0] for p in c]
    ys = [p[1] for p in c]
    return min(xs), min(ys), max(xs), max(ys)


def _seg_dist(p, a, b):
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    L = dx * dx + dy * dy
    if L == 0:
        return math.hypot(p[0] - ax, p[1] - ay)
    t = max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / L))
    return math.hypot(p[0] - ax - t * dx, p[1] - ay - t * dy)


def _near(p, poly, tol):
    if len(poly) == 1:
        return math.hypot(p[0] - poly[0][0], p[1] - poly[0][1]) <= tol
    for a, b in zip(poly, poly[1:]):
        if _seg_dist(p, a, b) <= tol:
            return True
    return False


def coverage(a, b, tol):
    """Share of a's vertices within tol of polyline b."""
    return sum(1 for p in a if _near(p, b, tol)) / float(len(a))


def path_score(a, b, tol):
    ba, bb = _bbox(a), _bbox(b)
    if ba[0] > bb[2] + tol or bb[0] > ba[2] + tol or \
            ba[1] > bb[3] + tol or bb[1] > ba[3] + tol:
        return 0.0
    return min(coverage(a, b, tol), coverage(b, a, tol))


def point_score(a, b, tol):
    d = math.hypot(a[0][0] - b[0][0], a[0][1] - b[0][1])
    return 1.0 - d / tol if d <= tol else 0.0


# ------------------------------------------------------------------ matching

def _src(u):
    return {"design": u["design"], "index": u["index"], "seq": u["seq"],
            "kind": u["kind"], "tdx_name": u["tdx_name"],
            "prep_name": u["prep_name"], "name_from": u["name_from"]}


def match(pre, post, tol=0.05, min_score=0.5, margin=0.15):
    """Assign each post sequence a pre sequence. Mutates post units, adding
    `status` (exact|tolerant|ambiguous|miss|native), `source`, `score`,
    `why`. Returns the list of pre units left unused."""
    used = set()
    by_key = {}
    for i, u in enumerate(pre):
        by_key.setdefault((u["design"], coord_key(u["coords"])), []).append(i)

    # 1. exact
    for pu in post:
        cands = [i for i in by_key.get((pu["design"], coord_key(pu["coords"])), [])
                 if i not in used]
        if not cands:
            continue
        names = {pre[i]["tdx_name"] for i in cands}
        if len(names) == 1:
            i = cands[0]
            used.add(i)
            pu.update(status="exact", source=_src(pre[i]), score=1.0,
                      why="same coordinate set" +
                      (" (%d identical sources, same name)" % len(cands)
                       if len(cands) > 1 else ""))
        else:
            pu.update(status="ambiguous", source=None, score=1.0,
                      candidates=[_src(pre[i]) for i in cands],
                      why="identical geometry, different names: %s"
                      % ", ".join(sorted(names)))

    # 2. tolerant, best-first and one-to-one
    left = [pu for pu in post if "status" not in pu]
    pairs = []
    per_post = {}
    for j, pu in enumerate(left):
        c = _cls(len(pu["coords"]))
        scored = []
        for i, u in enumerate(pre):
            if i in used or u["design"] != pu["design"] or _cls(u["kind"]) != c:
                continue
            s = (point_score if c == "point" else path_score)(
                pu["coords"], u["coords"], tol)
            if s > 0:
                scored.append((s, i))
        scored.sort(reverse=True)
        per_post[j] = scored
        for s, i in scored:
            pairs.append((s, j, i))
    pairs.sort(key=lambda t: -t[0])
    done_post = set()
    for s, j, i in pairs:
        pu = left[j]
        floor = min_score if len(pu["coords"]) > 1 else 0.0  # a point: within tol
        if j in done_post or i in used or s < floor:
            continue
        rivals = [(s2, i2) for s2, i2 in per_post[j] if i2 != i and i2 not in used]
        if rivals and rivals[0][0] >= floor and s - rivals[0][0] <= margin \
                and pre[rivals[0][1]]["tdx_name"] != pre[i]["tdx_name"]:
            pu.update(status="ambiguous", source=None, score=round(s, 3),
                      candidates=[_src(pre[i]), _src(pre[rivals[0][1]])],
                      why="two sources within %.2f: %.2f vs %.2f"
                      % (margin, s, rivals[0][0]))
            done_post.add(j)
            continue
        used.add(i)
        done_post.add(j)
        pu.update(status="tolerant", source=_src(pre[i]), score=round(s, 3),
                  why="%s within %.3g m" % ("nearest point" if len(pu["coords"]) == 1
                                            else "mutual vertex coverage", tol))

    # 3. leftovers
    for j, pu in enumerate(left):
        if "status" in pu:
            continue
        best = [(s, i) for s, i in per_post.get(j, []) if i not in used]
        hint = ("best free source scores %.2f, below the %.2f floor"
                % (best[0][0], min_score)
                if best else "no source geometry within %.3g m" % tol)
        if not pu["item"]["tdx_stamp"]:
            pu.update(status="native", source=None, score=0.0,
                      why="no TopoDroid datarow: drawn in cSurvey")
        else:
            pu.update(status="miss", source=None, score=round(best[0][0], 3)
                      if best else 0.0, why=hint)
    return [u for i, u in enumerate(pre) if i not in used]


def recover(pre_path, post_path, tol=0.05, min_score=0.5, margin=0.15):
    pre = pre_units(load_root(pre_path))
    post, items = post_units(load_root(post_path))
    unused = match(pre, post, tol, min_score, margin)

    for pu in post:
        seq = {"seq": pu["seq"], "n_points": len(pu["coords"]),
               "status": pu["status"], "score": pu["score"], "why": pu["why"],
               "source": pu.get("source")}
        if "candidates" in pu:
            seq["candidates"] = pu["candidates"]
        pu["item"]["sequences"].append(seq)
    for it in items:
        names = sorted({s["source"]["tdx_name"] for s in it["sequences"] if s["source"]})
        sts = {s["status"] for s in it["sequences"]}
        it["tdx_names"] = names
        it["tdx_name"] = names[0] if len(names) == 1 and \
            sts <= {"exact", "tolerant"} else None
        it["status"] = (sts.pop() if len(sts) == 1 else "mixed") if sts else "empty"

    # acceptance: share of source items (by TopoDroid kind) found again
    pre_items = {}
    for u in pre:
        pre_items.setdefault((u["design"], u["index"]), u["kind"])
    unused_items = {(u["design"], u["index"]) for u in unused}
    kinds = {}
    for key, kind in pre_items.items():
        k = kinds.setdefault(kind, {"total": 0, "recovered": 0})
        k["total"] += 1
        k["recovered"] += key not in unused_items
    statuses = {}
    for pu in post:
        statuses[pu["status"]] = statuses.get(pu["status"], 0) + 1
    return {
        "pre": pre_path, "post": post_path,
        "params": {"tol": tol, "min_score": min_score, "margin": margin},
        "summary": {"pre_items": len(pre_items), "post_items": len(items),
                    "post_sequences": len(post), "sequence_status": statuses,
                    "by_kind": kinds},
        "items": items,
        "unused_sources": [_src(u) for u in unused],
    }


# ------------------------------------------------------------------ CLI

def _fmt_item(it):
    t = "%s L%s#%d type=%s cat=%s" % (it["design"], it["layer"], it["index"],
                                     it["type"], it["category"])
    if it["sign"]:
        t += " sign=%s" % it["sign"]
    return t


def print_report(res, quiet=False, out=None):
    s = res["summary"]
    w = (out or sys.stdout).write
    w("PRE  %s\nPOST %s\n" % (res["pre"], res["post"]))
    w("items: %d source, %d after import (%d sequences)\n"
      % (s["pre_items"], s["post_items"], s["post_sequences"]))
    w("sequences: %s\n" % ", ".join("%s %d" % kv for kv in sorted(s["sequence_status"].items())))
    for kind, k in sorted(s["by_kind"].items()):
        pct = 100.0 * k["recovered"] / k["total"] if k["total"] else 100.0
        w("  %-6s %d/%d recovered (%.1f %%)\n" % (kind, k["recovered"], k["total"], pct))
    if not quiet:
        for it in res["items"]:
            w("  %-42s %-9s %s\n" % (_fmt_item(it), it["status"],
                                    "+".join(it["tdx_names"]) or "-"))
    probs = [(it, sq) for it in res["items"] for sq in it["sequences"]
             if sq["status"] in ("ambiguous", "miss", "native")]
    if probs:
        w("not recovered:\n")
        for it, sq in probs:
            w("  %s seq %d: %s - %s\n" % (_fmt_item(it), sq["seq"], sq["status"], sq["why"]))
    if res["unused_sources"]:
        w("source sequences not found after import:\n")
        for u in res["unused_sources"]:
            w("  %s #%d seq %d %s %s\n" % (u["design"], u["index"], u["seq"],
                                           u["kind"], u["tdx_name"]))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("recover", help="map post-import items to TopoDroid names")
    r.add_argument("pre", help="pre-import .csx (raw export or KORAK 1 output)")
    r.add_argument("post", help="post-import .csx or .csz")
    r.add_argument("--json", help="write the full result as JSON here")
    r.add_argument("--tol", type=float, default=0.05, help="metres (default 0.05)")
    r.add_argument("--min-score", type=float, default=0.5)
    r.add_argument("--margin", type=float, default=0.15)
    r.add_argument("--quiet", action="store_true", help="summary and problems only")
    a = ap.parse_args(argv)
    try:
        res = recover(a.pre, a.post, a.tol, a.min_score, a.margin)
    except (OSError, ValueError, ET.ParseError, zipfile.BadZipFile) as e:
        print("ERROR: %s" % e, file=sys.stderr)
        return 1
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False, indent=1)
    print_report(res, a.quiet)
    return 0


if __name__ == "__main__":
    sys.exit(main())
