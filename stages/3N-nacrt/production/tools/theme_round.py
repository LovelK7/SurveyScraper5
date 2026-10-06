#!/usr/bin/env python3
"""One symbol-theme tuning round on the theme mockup, in one command (project 0007).

Until r7 every round re-derived the procedure by hand (RUNLOG r2-r7): mockup ->
headless import on a DTD-free copy of cSurvey -> KORAK 2 -> theme_apply ->
headless print -> comparison sheets -> RUNLOG. This tool is that procedure.

  python theme_round.py LABEL [--split] [--svg DRAWING.svg]
                              [--themes boja,crno-bijelo] [--focus KEY,...]
                              [--seeds N] [--fresh-mockup] [--no-print]
                              [--date YYYY-MM-DD] [--detail-dpi 1600]

Steps (timed, printed as they finish):

 1. --split: theme_svg.py split of the drawing (default
    projects/0007-symbol-themes/drawing_catalogue.svg) into findings/t1-split/,
    then the split's signs/lines/areas files, index.json and report.json are
    copied into production/themes/boja/. theme.json is NEVER touched, and no
    file is deleted from the theme (hand-built units such as
    lines/ceiling-step@T.svg stay). Prints what changed against the theme's
    files, loudly warns on unnamed groups / `_x3C_Group` ids / duplicate names.
 2. themes.py check of every theme in --themes; a broken theme stops the round.
 3. Mockup cache: make_theme_mockup -> headless import (csurvey_driver recalc)
    on a DTD-free copy of cSurvey -> KORAK 2 (fix_imported_linetypes.py) ->
    fixed area seeds (make_theme_mockup.seed_areas) -> izvorno print. Built
    once per cache key (the mockup's symbol lists + hashes of the generator,
    KORAK 2, tdx-mapping.json and the cSurvey build) and reused by later rounds;
    --fresh-mockup rebuilds it.
 4. theme_apply (with --pre) per theme, then all prints in parallel on the real
    cSurvey install; --seeds N also prints the first theme with N alternative
    area seeds.
 5. Sheets in projects/0007-symbol-themes/runs/<date>-<label>/: per kind
    (znakovi, linije, plohe) every themed slot as izvorno | each theme, cropped
    from the vector PDFs at a fixed dpi (never a shrunk page); per focus key a
    full-resolution detail (a line slot holds the straight and the curved
    stroke); the seed sheet with ink cover; pregled.png (what changed on top).
 6. RUNLOG.md: inputs, theme.json diffs against the previous round's copies
    (stored in <run>/themes/), apply reports, ink cover, images, timings, and an
    empty "Feedback -> change" section for the session to fill.

--no-print only validates: themes.py check + a theme_apply dry run on the
cached imported mockup (when there is one). Nothing is written.

Cache (gitignored, workspace `runs/`): <workspace>/runs/theme-round/
  csurvey-nodtd/        copy of the cSurvey install with the DOCTYPE lines
                        stripped from Objects/**/*.svg (.NET fetches the w3.org
                        DTD on import and w3.org answers HTTP 429). Re-copied when
                        cSurveyPC.exe changes. The install itself is never touched.
  mockup-<key>/         theme-mockup.csx (raw), _imported, _izvorno (KORAK 2 +
                        seeds), -key.md, -layout.json, izvorno plan PDF/PNG.
  rounds/<run>/         seed-variant .csx/.pdf (not part of the record).

Needs Windows + cSurvey for the import and prints (csurvey_driver.py);
PyMuPDF and Pillow for the sheets (both already used in the repo).
"""

import argparse
import datetime
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import csurvey_driver                                           # noqa: E402
import make_theme_mockup                                        # noqa: E402
import themes                                                   # noqa: E402

PRODUCTION = os.path.dirname(HERE)
STAGE = os.path.dirname(PRODUCTION)
PROJECT = os.path.join(STAGE, "projects", "0007-symbol-themes")
RUNS = os.path.join(PROJECT, "runs")
DEFAULT_SVG = os.path.join(PROJECT, "drawing_catalogue.svg")
SPLIT_DIR = os.path.join(PROJECT, "findings", "t1-split")
SPLIT_THEME = "boja"            # the theme the drawing feeds
KINDS = ("signs", "lines", "areas")
MOCKUP = "theme-mockup"
IZVORNO = "izvorno"
# Bump when the cache layout or the steps that fill it change.
CACHE_VERSION = "1"
GENERATOR_FILES = ("make_theme_mockup.py", "fix_imported_linetypes.py",
                   "wall_orient.py", "tdx-mapping.json")

SHEETS = [  # kind, file stem, title, dpi, pad (m)
    ("signs", "znakovi", "ZNAKOVI – themed signs", 900, 0.0),
    ("lines", "linije", "LINIJE – straight (top) and curve (bottom)", 800, 0.1),
    ("areas", "plohe", "PLOHE – areas", 600, 0.1),
]
INK_DPI = 900


class RoundError(RuntimeError):
    pass


# ==========================================================================
# pure helpers (tests/test_theme_round.py)

def flatten(obj, prefix=""):
    """{dotted path: leaf} of a theme.json, comment keys (`_...`) left out."""
    out = {}
    if isinstance(obj, dict):
        for k in sorted(obj):
            if k.startswith("_"):
                continue
            p = "%s.%s" % (prefix, k) if prefix else k
            v = obj[k]
            if isinstance(v, dict) and v:
                out.update(flatten(v, p))
            else:
                out[p] = v
    else:
        out[prefix] = obj
    return out


def diff_theme_json(old, new):
    """[(op, path, old, new)] between two theme.json dicts; op is + - or ~.
    Comment keys are ignored; whole entries added or removed are one row."""
    if old is None:
        return []
    rows = []
    for kind in sorted(set(old) | set(new)):
        o, n = old.get(kind), new.get(kind)
        if kind.startswith("_"):
            continue
        if kind in KINDS and isinstance(o, dict) and isinstance(n, dict):
            for key in sorted(set(o) | set(n)):
                if key.startswith("_"):
                    continue
                if key not in o:
                    rows.append(("+", "%s.%s" % (kind, key), None, n[key]))
                elif key not in n:
                    rows.append(("-", "%s.%s" % (kind, key), o[key], None))
                else:
                    rows.extend(_diff_flat(flatten(o[key], "%s.%s" % (kind, key)),
                                           flatten(n[key], "%s.%s" % (kind, key))))
        else:
            rows.extend(_diff_flat(flatten(o, kind) if o is not None else {},
                                   flatten(n, kind) if n is not None else {}))
    return rows


def _diff_flat(fo, fn):
    rows = []
    for p in sorted(set(fo) | set(fn)):
        if p not in fo:
            rows.append(("+", p, None, fn[p]))
        elif p not in fn:
            rows.append(("-", p, fo[p], None))
        elif fo[p] != fn[p]:
            rows.append(("~", p, fo[p], fn[p]))
    return rows


def changed_keys(rows):
    """{(kind, key)} touched by diff rows (for the automatic focus)."""
    out = set()
    for _op, path, _o, _n in rows:
        parts = path.split(".", 2)
        if parts[0] in KINDS and len(parts) > 1:
            out.add((parts[0], parts[1]))
    return out


def jv(v):
    """A diff value as short text."""
    if v is None:
        return "–"
    return json.dumps(v, ensure_ascii=False, sort_keys=True)


def cache_key(symbol_lists, versions):
    """12 hex chars from the mockup's symbol lists and the generator versions."""
    blob = json.dumps({"symbols": symbol_lists, "versions": versions,
                       "cache": CACHE_VERSION}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:12]


def file_hash(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def _read(path):
    with open(path, "rb") as f:
        return f.read()


def _index(folder, kind):
    p = os.path.join(folder, kind, "index.json")
    if not os.path.exists(p):
        return {}
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def split_diff(theme_dir, split_dir, report, theme_raw):
    """What a fresh split changes against the theme's current files.

    -> {kind: {"added": [...], "changed": [...], "removed": [...], "unchanged": n},
        "no_entry": [(kind, key)], "colours": {(kind, key): [...]},
        "stroked": [(kind, key, n, stroke_only)], "unnamed": [...],
        "ai_ids": [...], "duplicates": [...]}"""
    out = {"no_entry": [], "colours": {}, "stroked": [], "ai_ids": [],
           "unnamed": list(report.get("unnamed", [])),
           "duplicates": list(report.get("duplicates", []))}
    for kind in KINDS:
        old_idx, new_idx = _index(theme_dir, kind), _index(split_dir, kind)
        d = {"added": [], "changed": [], "removed": [], "unchanged": 0}
        for key, fname in sorted(new_idx.items()):
            if key not in old_idx:
                d["added"].append(key)
                continue
            old_p = os.path.join(theme_dir, kind, old_idx[key])
            new_p = os.path.join(split_dir, kind, fname)
            if not os.path.exists(old_p) or _read(old_p) != _read(new_p):
                d["changed"].append(key)
            else:
                d["unchanged"] += 1
        d["removed"] = sorted(k for k in old_idx if k not in new_idx)
        out[kind] = d
        entries = {k for k in (theme_raw.get(kind) or {}) if not k.startswith("_")}
        out["no_entry"] += [(kind, k) for k in sorted(new_idx) if k not in entries]
    for e in report.get("pieces", []):
        kind, key = e.get("kind"), e.get("key")
        cols = [c for c in e.get("colours_flattened", [])
                if c.lower() not in ("#fff", "#ffffff", "white")]
        out["colours"][(kind, key)] = cols
        if e.get("strokes"):
            # signs: the split's own warning; units/tiles: no fill was flattened,
            # i.e. every shape came from an outlined stroke (blocks tile, r3)
            only = any("stroke-only" in w for w in e.get("warnings", [])) or (
                kind in ("lines", "areas") and not (e.get("fixed") or {}).get("fills flattened"))
            out["stroked"].append((kind, key, len(e["strokes"]), only))
        raw = e.get("id") or ""
        if "_x3C_" in raw or "Group" in raw:
            out["ai_ids"].append((kind, key, raw))
    for u in out["unnamed"]:
        raw = u.get("id") or ""
        if "_x3C_" in raw:
            out["ai_ids"].append((None, None, raw))
    return out


def format_split_summary(d):
    """Console / RUNLOG lines; lines starting with '!!' are loud warnings."""
    lines = []
    for kind in KINDS:
        k = d[kind]
        lines.append("%s: %d changed, %d added, %d removed, %d unchanged"
                     % (kind, len(k["changed"]), len(k["added"]), len(k["removed"]),
                        k["unchanged"]))
        for what in ("changed", "added", "removed"):
            for key in k[what]:
                col = d["colours"].get((kind, key)) or []
                extra = ""
                if what == "added":
                    extra = "  colour %s" % (", ".join(col) if col else "black/none")
                elif what == "removed":
                    extra = "  (no longer in the drawing; theme file kept)"
                lines.append("  %s %s/%s%s" % ({"changed": "~", "added": "+",
                                                 "removed": "-"}[what], kind, key, extra))
    for kind, key in d["no_entry"]:
        col = d["colours"].get((kind, key)) or []
        lines.append("  new key without a theme.json entry: %s/%s (colour %s)"
                     % (kind, key, ", ".join(col) if col else "black/none"))
    for kind, key, n, only in d["stroked"]:
        lines.append("  %s/%s: %d stroked shape(s)%s" % (
            kind, key, n, " – STROKE-ONLY" if only else "")
            + (" (outlined into fills)" if kind in ("lines", "areas") else
               " (signs: drawn by the pen only)"))
    for u in d["unnamed"]:
        lines.append("!! UNNAMED %s on layer %s (id=%s) – not exported; name the group"
                     % (u.get("element"), u.get("layer"), u.get("id")))
    for kind, key, raw in d["ai_ids"]:
        lines.append("!! Illustrator default id %r%s – rename the group" % (
            raw, " (%s/%s)" % (kind, key) if kind else ""))
    for dup in d["duplicates"]:
        lines.append("!! DUPLICATE name %s/%s (id=%s) – only the first (id=%s) is used"
                     % (dup.get("kind"), dup.get("key"), dup.get("id"), dup.get("kept")))
    return lines


def parse_focus(text):
    """'ceiling-step,lines/water,L04' -> [(kind|None, key-or-tag)]."""
    out = []
    for tok in (text or "").split(","):
        tok = tok.strip()
        if not tok:
            continue
        if "/" in tok:
            kind, key = tok.split("/", 1)
            out.append((kind if kind in KINDS else None, key))
        else:
            out.append((None, tok))
    return out


def match_focus(focus, slots):
    """Slots of the layout a focus list names (themed slots first)."""
    hits = []
    for kind, key in focus:
        found = [s for s in slots if s["tag"] == key or
                 (s["name"] == key and (kind is None or s["kind"] == kind))]
        themed = [s for s in found if s["themes"]]
        for s in (themed or found):
            if s not in hits:
                hits.append(s)
    return hits


def safe(key):
    return key.replace(":", "@").replace("/", "-")


def previous_run(runs_dir, current, theme_ids):
    """The newest other run folder holding theme.json copies, or None."""
    best = None
    if not os.path.isdir(runs_dir):
        return None
    for name in os.listdir(runs_dir):
        d = os.path.join(runs_dir, name)
        if name == current or not os.path.isdir(os.path.join(d, "themes")):
            continue
        copies = [os.path.join(d, "themes", "%s.theme.json" % t) for t in theme_ids]
        copies = [c for c in copies if os.path.exists(c)]
        if not copies:
            continue
        m = max(os.path.getmtime(c) for c in copies)
        if best is None or m > best[0]:
            best = (m, name)
    return best[1] if best else None


def report_summary(rep, theme_keys):
    """Short dict of one theme_apply report for the RUNLOG."""
    s = {"signs_themed": rep.get("themed", 0), "signs": rep.get("signs", 0),
         "sign_lookup": rep.get("lookup", {}), "notes": rep.get("notes", []),
         "fallbacks": [], "unthemed": [], "skipped": []}
    for sec in ("lines", "areas"):
        hit = rep.get(sec, {}).get("themed", {})
        names = {}
        for label, n in hit.items():
            key = label.split(" (", 1)[0]
            names[key] = names.get(key, 0) + n
            if "(target" in label:
                s["fallbacks"].append("%s/%s" % (sec, label))
        s[sec] = names
        s["skipped"] += ["%s: %s" % (sec, x) for x in rep.get(sec, {}).get("skipped", [])]
        s["unthemed"] += ["%s/%s" % (sec, k) for k in sorted(theme_keys.get(sec, ()))
                          if k not in names]
    for label, n in s["sign_lookup"].items():
        if label.startswith("target"):
            s["fallbacks"].append("signs/%s: %d" % (label, n))
    return s


def _cell(v):
    return str(v).replace("|", "\\|").replace("\n", " ")


def render_runlog(info):
    """The RUNLOG.md text of one round (info: see theme_round.run())."""
    L = []
    w = L.append
    w("# Theme round %s, %s" % (info["label"], info["date"]))
    w("")
    w("Written by `production/tools/theme_round.py` ([cheatsheet](../../../../production/tools/"
      "theme_tuning_cheatsheet.md)). Command:")
    w("")
    w("```text")
    w(info["command"])
    w("```")
    w("")
    w("## Look at these first")
    w("")
    w("- [`pregled.png`](pregled.png) — what changed this round, then the focus crops.")
    for path, what in info.get("details", []):
        w("- [`%s`](%s) — %s" % (path, path, what))
    for path, what in info.get("sheets", []):
        w("- [`%s`](%s) — %s" % (path, path, what))
    w("")
    w("## Inputs")
    w("")
    w("| What | Value |")
    w("|---|---|")
    for k, v in info.get("inputs", []):
        w("| %s | %s |" % (_cell(k), _cell(v)))
    w("")
    w("## theme.json changes")
    w("")
    prev = info.get("previous_run")
    if not prev:
        w("No earlier round with theme.json copies: this round is the baseline "
          "(copies in [`themes/`](themes/)).")
    else:
        w("Against [`%s`](../%s/RUNLOG.md) (copies in [`themes/`](themes/)):" % (prev, prev))
        w("")
        any_rows = False
        for tid, rows in info.get("theme_diffs", {}).items():
            if not rows:
                w("- `%s`: no change" % tid)
                continue
            any_rows = True
            w("")
            w("`%s`:" % tid)
            w("")
            w("| | Path | Before | After |")
            w("|---|---|---|---|")
            for op, path, o, n in rows:
                w("| %s | `%s` | %s | %s |" % (op, path, _cell(jv(o)), _cell(jv(n))))
        if not any_rows:
            w("")
            w("No value changed (comment keys are not compared).")
    w("")
    if info.get("split"):
        w("## Artwork split")
        w("")
        w("```text")
        L.extend(info["split"])
        w("```")
        w("")
    w("## Apply reports")
    w("")
    w("| Theme | Signs themed | Lines themed | Areas themed | Unthemed keys | Fallbacks (target) | Skipped |")
    w("|---|---|---|---|---|---|---|")
    for tid, s in info.get("reports", {}).items():
        w("| %s | %d / %d | %s | %s | %s | %s | %s |" % (
            tid, s["signs_themed"], s["signs"],
            _cell(", ".join("%s %d" % kv for kv in sorted(s["lines"].items())) or "–"),
            _cell(", ".join("%s %d" % kv for kv in sorted(s["areas"].items())) or "–"),
            _cell(", ".join(s["unthemed"]) or "–"),
            _cell(", ".join(s["fallbacks"]) or "–"),
            _cell("; ".join(s["skipped"]) or "–")))
    notes = [(t, n) for t, s in info.get("reports", {}).items() for n in s["notes"]]
    if notes:
        w("")
        for t, n in notes:
            w("- `%s`: %s" % (t, n))
    w("")
    ink = info.get("ink")
    if ink and ink.get("rows"):
        w("## Ink cover per area")
        w("")
        w("Share of the inner 1.88 × 1.38 m of each 2 × 1.5 m sample that is ink, at %d dpi "
          "(any pixel with a channel under 160; red station marks excluded, so a light solid fill "
          "such as izvorno's water counts as ink); `empty` = bare cells of 12 (0.47 m). "
          "s0 is the mockup's fixed seed, s1… the alternatives." % INK_DPI)
        w("")
        w("| Slot | Area | " + " | ".join(ink["cols"]) + " |")
        w("|---|---|" + "---|" * len(ink["cols"]))
        for tag, name, vals in ink["rows"]:
            cells = []
            for c in ink["cols"]:
                v = vals.get(c)
                cells.append("–" if v is None else "%.1f %%%s" % (
                    100 * v[0], " (%d empty)" % v[1] if v[1] else ""))
            w("| %s | %s | %s |" % (tag, name, " | ".join(cells)))
        w("")
    w("## Files")
    w("")
    w("| File | What |")
    w("|---|---|")
    for path, what in info.get("files", []):
        w("| [`%s`](%s) | %s |" % (path, path, _cell(what)))
    w("")
    w("`.csx` files are gitignored; the round re-creates them from the mockup cache "
      "(`%s`)." % info.get("cache_dir", "runs/theme-round"))
    w("")
    w("## Timings")
    w("")
    w("| Step | s |")
    w("|---|---|")
    for step, sec in info.get("timings", []):
        w("| %s | %.1f |" % (step, sec))
    w("| **total** | **%.1f** |" % sum(s for _, s in info.get("timings", [])))
    w("")
    if info.get("warnings"):
        w("## Warnings")
        w("")
        for x in info["warnings"]:
            w("- %s" % x)
        w("")
    w("## Feedback → change")
    w("")
    w("_To be filled by the session: the user's words on this round, and the theme.json "
      "change each one led to (see the cheatsheet)._")
    w("")
    w("| # | Feedback (user) | Key | Change | Seen in |")
    w("|---|---|---|---|---|")
    w("| 1 | … | … | … | … |")
    w("")
    return "\n".join(L)


# ==========================================================================
# cSurvey side

def cache_root():
    ws = csurvey_driver.workspace_root()
    if ws:
        return os.path.join(ws, "runs", "theme-round")
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return os.path.join(base, "CaveDossier", "theme-round")


_DOCTYPE = re.compile(rb"<!DOCTYPE[^\[>]*(\[[^\]]*\])?\s*>")


def ensure_nodtd(src, dest):
    """A copy of the cSurvey folder with DOCTYPE lines stripped from its SVGs.
    Re-copied when cSurveyPC.exe changes. Never writes into `src`."""
    exe = os.path.join(src, "cSurveyPC.exe")
    if not os.path.exists(exe):
        raise RoundError("cSurvey not found in %s" % src)
    st = os.stat(exe)
    stamp = {"source": os.path.abspath(src), "exe_size": st.st_size,
             "exe_mtime": int(st.st_mtime)}
    stamp_path = os.path.join(dest, ".nodtd-source.json")
    if os.path.exists(stamp_path):
        with open(stamp_path, encoding="utf-8") as f:
            old = json.load(f)
        if all(old.get(k) == v for k, v in stamp.items()):
            return dest, False
    if os.path.isdir(dest):
        shutil.rmtree(dest)
    shutil.copytree(src, dest)
    n = 0
    for base, _dirs, files in os.walk(os.path.join(dest, "Objects")):
        for fn in files:
            if fn.lower().endswith(".svg"):
                p = os.path.join(base, fn)
                data = _read(p)
                new = _DOCTYPE.sub(b"", data)
                if new != data:
                    with open(p, "wb") as f:
                        f.write(new)
                    n += 1
    with open(stamp_path, "w", encoding="utf-8") as f:
        json.dump(dict(stamp, stripped=n), f)
    return dest, True


def mockup_cache_key(csurvey_dir):
    lists, _w = make_theme_mockup.symbol_lists()
    versions = {f: file_hash(os.path.join(HERE, f)) for f in GENERATOR_FILES
                if os.path.exists(os.path.join(HERE, f))}
    exe = os.path.join(csurvey_dir, "cSurveyPC.exe")
    if os.path.exists(exe):
        st = os.stat(exe)
        versions["cSurveyPC.exe"] = "%d-%d" % (st.st_size, int(st.st_mtime))
    return cache_key(lists, versions), versions


def png_of(pdf, png, dpi=110):
    import pymupdf
    doc = pymupdf.open(pdf)
    doc[0].get_pixmap(dpi=dpi, alpha=False).save(png)
    doc.close()


def print_plans(jobs, csurvey_dir, tmp):
    """Print [(csx, dest_dir)] in parallel; -> {csx: pdf path in dest_dir}."""
    os.makedirs(tmp, exist_ok=True)

    def one(job):
        csx, dest = job
        sub = os.path.join(tmp, os.path.splitext(os.path.basename(csx))[0])
        os.makedirs(sub, exist_ok=True)
        last = None
        for _attempt in range(2):
            try:
                pdfs = csurvey_driver.print_pdfs(csx, sub, design="Plan",
                                                 csurvey_dir=csurvey_dir)
                break
            except csurvey_driver.DriverError as e:
                last = e
        else:
            raise RoundError("print %s: %s" % (os.path.basename(csx), last))
        target = os.path.join(dest, os.path.basename(pdfs["plan"]))
        try:
            os.replace(pdfs["plan"], target)
        except OSError as e:
            raise RoundError("cannot write %s (open in a viewer?): %s" % (target, e))
        return csx, target

    with ThreadPoolExecutor(max_workers=min(4, max(1, len(jobs)))) as ex:
        out = dict(ex.map(one, jobs))
    shutil.rmtree(tmp, ignore_errors=True)
    return out


def build_mockup_cache(cdir, nodtd, csurvey_dir, timer):
    if os.path.isdir(cdir):
        shutil.rmtree(cdir)
    os.makedirs(cdir)
    base = os.path.join(cdir, MOCKUP)
    xml, key, layout, warnings = make_theme_mockup.build()
    with open(base + ".csx", "w", encoding="utf-8", newline="\n") as f:
        f.write(xml)
    with open(base + "-key.md", "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(key) + "\n")
    with open(base + "-layout.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(layout, f, ensure_ascii=False, indent=1)
    for x in warnings:
        print("  WARNING (mockup): " + x)
    timer("mockup: generate")
    try:
        csurvey_driver.recalc(base + ".csx", base + "_imported.csx", csurvey_dir=nodtd)
    except csurvey_driver.DriverError as e:
        raise RoundError("headless import failed: %s" % e)
    timer("mockup: headless import (DTD-free copy)")
    done = subprocess.run([sys.executable, os.path.join(HERE, "fix_imported_linetypes.py"),
                           base + "_imported.csx", "-o", base + "_%s.csx" % IZVORNO],
                          capture_output=True, encoding="utf-8", errors="replace")
    if done.returncode != 0 or not os.path.exists(base + "_%s.csx" % IZVORNO):
        raise RoundError("KORAK 2 failed: %s" % (done.stderr or done.stdout).strip()[-400:])
    n = make_theme_mockup.seed_file(base + "_%s.csx" % IZVORNO)
    timer("mockup: KORAK 2 + %d fixed area seeds" % n)
    print_plans([(base + "_%s.csx" % IZVORNO, cdir)], csurvey_dir, os.path.join(cdir, "_print"))
    png_of(base + "_%s_plan.pdf" % IZVORNO, base + "_%s_plan.png" % IZVORNO)
    timer("mockup: izvorno print")
    with open(os.path.join(cdir, "cache.json"), "w", encoding="utf-8") as f:
        json.dump({"built": datetime.datetime.now().isoformat(timespec="seconds"),
                   "area_seeds": n, "warnings": warnings}, f, indent=1)


# ==========================================================================
# sheets (PyMuPDF + Pillow)

def _font(size, bold=False):
    from PIL import ImageFont
    for name in (("arialbd.ttf",) if bold else ()) + ("arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


class Print(object):
    """One plan PDF, its display list and the world -> page fit."""

    def __init__(self, pdf, layout, fallback=None):
        import pymupdf
        self.doc = pymupdf.open(pdf)
        self.page = self.doc[0]
        self.dl = self.page.get_displaylist()
        self.fit = fit_page(self.page, layout) or fallback
        if self.fit is None:
            raise RoundError("cannot locate the stations on %s" % pdf)

    def crop(self, box, dpi, fade=True):
        import pymupdf
        from PIL import Image
        ax, bx, ay, by = self.fit
        x0, y0, x1, y1 = box
        r = pymupdf.Rect(ax * x0 + bx, ay * y0 + by, ax * x1 + bx, ay * y1 + by)
        r.normalize()
        z = dpi / 72.0
        pix = self.dl.get_pixmap(matrix=pymupdf.Matrix(z, z), clip=r, alpha=False)
        im = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        if fade:
            im.paste((255, 215, 215), mask=red_mask(im, strict=True))
        return im


def fit_page(page, layout):
    """World (m) -> page (pt) from the red station triangles (compose3, r3)."""
    tri = []
    for d in page.get_drawings():
        f, c = d.get("fill"), d.get("color")
        if d.get("type") == "fs" and f and c and f[0] > 0.9 and f[1] < 0.1 and f[2] < 0.1:
            r = d["rect"]
            tri.append(((r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2))
    pts = [s["station"] for s in layout["slots"]]
    if len(tri) < max(5, len(pts) // 2):
        return None

    def rough(i):
        a = (max(t[i] for t in tri) - min(t[i] for t in tri)) / \
            (max(s[i] for s in pts) - min(s[i] for s in pts))
        return a, min(t[i] for t in tri) - a * min(s[i] for s in pts)
    (ax, bx), (ay, by) = rough(0), rough(1)
    pairs = [(s, min(tri, key=lambda t: (t[0] - ax * s[0] - bx) ** 2 + (t[1] - ay * s[1] - by) ** 2))
             for s in pts]

    def lsq(i):
        n = len(pairs)
        mx = sum(p[0][i] for p in pairs) / n
        my = sum(p[1][i] for p in pairs) / n
        a = sum((p[0][i] - mx) * (p[1][i] - my) for p in pairs) / \
            sum((p[0][i] - mx) ** 2 for p in pairs)
        return a, my - a * mx
    return lsq(0) + lsq(1)


def _thr(band, test):
    return band.point(lambda v: 255 if test(v) else 0)


def red_mask(im, strict=False):
    """The red station marks. strict: compose3's fade rule, which spares the
    rope's #EF5553; otherwise measure.py's exclusion."""
    from PIL import ImageChops
    r, g, b = im.split()
    if strict:
        m = ImageChops.multiply(ImageChops.multiply(_thr(r, lambda v: v > 180),
                                                    _thr(g, lambda v: v < 120)),
                                _thr(b, lambda v: v < 120))
        rope = ImageChops.multiply(_thr(r, lambda v: v > 220), _thr(g, lambda v: v > 70))
        return ImageChops.subtract(m, rope)
    return ImageChops.multiply(ImageChops.multiply(_thr(r, lambda v: v > 180),
                                                   _thr(g, lambda v: v < 140)),
                               _thr(b, lambda v: v < 140))


def ink_stats(im):
    """(ink share, empty cells of a 4 x 3 grid) of an RGB crop (measure.py, r6)."""
    from PIL import ImageChops
    r, g, b = im.split()
    dark = _thr(ImageChops.darker(ImageChops.darker(r, g), b), lambda v: v < 160)
    ink = ImageChops.subtract(dark, red_mask(im))
    W, H = ink.size
    total = ink.histogram()[255]
    empty = 0
    for j in range(3):
        for i in range(4):
            c = ink.crop((W * i // 4, H * j // 3, W * (i + 1) // 4, H * (j + 1) // 3))
            area = max(1, c.size[0] * c.size[1])
            if c.histogram()[255] / float(area) < 0.003:
                empty += 1
    return total / float(max(1, W * H)), empty


def area_inner(slot):
    x, yb = slot["station"]
    return (x + 0.06, yb + 1.66, x + 1.94, yb + 3.04)


def grid_sheet(title, col_heads, rows, out, label_w=280):
    """rows: [(label, [image|None per column])] -> PNG, images at 1:1."""
    from PIL import Image, ImageDraw
    if not rows:
        return None
    ncol = len(col_heads)
    cw = [max([r[1][i].width for r in rows if r[1][i] is not None] + [200]) for i in range(ncol)]
    heads, gap = 92, 16
    hs = [max([im.height for im in r[1] if im is not None] + [40]) for r in rows]
    W = label_w + sum(c + gap for c in cw)
    H = heads + sum(h + 12 for h in hs)
    S = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(S)
    fb, f = _font(26, True), _font(20)
    d.text((10, 10), title, fill="black", font=fb)
    x = label_w
    for i, h in enumerate(col_heads):
        d.text((x + 8, 52), h, fill="black", font=fb)
        x += cw[i] + gap
    y = heads
    for (label, ims), h in zip(rows, hs):
        d.multiline_text((10, y + max(0, h // 2 - 24)), label, fill="black", font=f)
        x = label_w
        for i, im in enumerate(ims):
            if im is not None:
                S.paste(im, (x, y))
                d.rectangle([x - 1, y - 1, x + im.width, y + im.height], outline=(200, 200, 200))
            x += cw[i] + gap
        y += h + 12
    S.save(out)
    return S.size


def text_block(lines, width, size=20):
    from PIL import Image, ImageDraw
    f = _font(size)
    lh = size + 6
    S = Image.new("RGB", (width, lh * len(lines) + 20), "white")
    d = ImageDraw.Draw(S)
    for i, ln in enumerate(lines):
        bold = ln.startswith("# ")
        d.text((12, 10 + i * lh), ln[2:] if bold else ln,
               fill=(170, 0, 0) if ln.startswith("!!") else "black",
               font=_font(size + 6, True) if bold else f)
    return S


def stack(images, out):
    from PIL import Image
    images = [i for i in images if i is not None]
    W = max(i.width for i in images)
    H = sum(i.height + 10 for i in images)
    S = Image.new("RGB", (W, H), "white")
    y = 0
    for i in images:
        S.paste(i, (0, y))
        y += i.height + 10
    S.save(out)
    return S.size


# ==========================================================================
# the round

class Timer(object):
    def __init__(self):
        self.t = self.t0 = time.time()
        self.rows = []

    def __call__(self, step):
        now = time.time()
        self.rows.append((step, now - self.t))
        print("  [%5.1f s] %s" % (now - self.t, step))
        self.t = now


def load_raw(tid):
    with open(os.path.join(themes.default_themes_root(), tid, "theme.json"), encoding="utf-8") as f:
        return json.load(f)


def do_split(svg, timer):
    import theme_svg
    if not os.path.exists(svg):
        raise RoundError("drawing not found: %s" % svg)
    if os.path.isdir(SPLIT_DIR):
        shutil.rmtree(SPLIT_DIR)
    buf = io.StringIO()
    old_out, sys.stdout = sys.stdout, buf
    try:
        report = theme_svg.split(svg, SPLIT_DIR)
    finally:
        sys.stdout = old_out
    theme_dir = os.path.join(themes.default_themes_root(), SPLIT_THEME)
    d = split_diff(theme_dir, SPLIT_DIR, report, load_raw(SPLIT_THEME))
    lines = format_split_summary(d)
    # refresh the theme's artwork: split files + index.json + report.json; never theme.json
    for kind in KINDS:
        src = os.path.join(SPLIT_DIR, kind)
        if not os.path.isdir(src):
            continue
        dst = os.path.join(theme_dir, kind)
        os.makedirs(dst, exist_ok=True)
        for fn in os.listdir(src):
            shutil.copyfile(os.path.join(src, fn), os.path.join(dst, fn))
    shutil.copyfile(os.path.join(SPLIT_DIR, "report.json"), os.path.join(theme_dir, "report.json"))
    print("  split %s -> findings/t1-split/ -> themes/%s/ (theme.json untouched)"
          % (os.path.basename(svg), SPLIT_THEME))
    for ln in lines:
        print(("  " if not ln.startswith("!!") else "  !!!!! ") + ln)
    timer("split + refresh themes/%s" % SPLIT_THEME)
    return lines, d


def check_themes(ids):
    bad = []
    for tid in ids:
        errs = themes.validate(tid)
        print("  themes.py check %s: %s" % (tid, "OK" if not errs else "%d problem(s)" % len(errs)))
        for e in errs:
            print("    - " + e)
            bad.append("%s: %s" % (tid, e))
    return bad


def apply_theme(izvorno, pre, tid, out, report_path=None, dry_run=False):
    import theme_apply
    rep = theme_apply.theme_file(izvorno, tid, pre, out, dry_run=dry_run)
    if report_path:
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(rep, f, ensure_ascii=False, indent=1)
    buf = io.StringIO()
    theme_apply.print_report(rep, buf)
    return rep, buf.getvalue()


def rel(path, start):
    return os.path.relpath(path, start).replace("\\", "/")


def run(args):
    timer = Timer()
    theme_ids = [t.strip() for t in args.themes.split(",") if t.strip()]
    date = args.date or datetime.date.today().isoformat()
    run_name = "%s-%s" % (date, args.label)
    run_dir = os.path.join(RUNS, run_name)
    warnings = []
    info = {"label": args.label, "date": date,
            "command": "python production/tools/theme_round.py " + " ".join(args.argv),
            "inputs": [], "warnings": warnings}

    print("theme round %s (%s)" % (args.label, ", ".join(theme_ids)))
    split_lines = None
    if args.split:
        split_lines, sd = do_split(args.svg, timer)
        for ln in split_lines:
            if ln.startswith("!!"):
                warnings.append(ln[3:])

    bad = check_themes(theme_ids)
    timer("themes.py check")
    if bad:
        raise RoundError("theme check failed – fix theme.json first")

    real = csurvey_driver.find_csurvey_dir()
    croot = cache_root()
    key, versions = mockup_cache_key(real)
    cdir = os.path.join(croot, "mockup-" + key)
    base = os.path.join(cdir, MOCKUP)
    izvorno = base + "_%s.csx" % IZVORNO
    have_cache = os.path.exists(os.path.join(cdir, "cache.json"))

    if args.no_print:
        if not have_cache:
            print("  no mockup cache for key %s yet – apply dry run skipped "
                  "(run a round without --no-print first)" % key)
        else:
            for tid in theme_ids:
                rep, text = apply_theme(izvorno, base + ".csx", tid, None, dry_run=True)
                print(text.rstrip())
            timer("theme_apply dry run")
        print("validated (--no-print): nothing written%s"
              % (" except the split" if args.split else ""))
        return 0

    fresh = args.fresh_mockup or not have_cache
    if fresh:
        print("  mockup cache %s: %s" % (key, "rebuild (--fresh-mockup)" if have_cache
                                          else "new key – building"))
        nodtd, copied = ensure_nodtd(real, os.path.join(croot, "csurvey-nodtd"))
        timer("DTD-free cSurvey copy (%s)" % ("copied" if copied else "reused"))
        build_mockup_cache(cdir, nodtd, real, timer)
    else:
        print("  mockup cache %s: reused" % key)

    os.makedirs(os.path.join(run_dir, "themes"), exist_ok=True)
    with open(base + "-layout.json", encoding="utf-8") as f:
        layout = json.load(f)
    for suffix in ("-layout.json", "-key.md", "_%s_plan.pdf" % IZVORNO, "_%s_plan.png" % IZVORNO):
        shutil.copyfile(base + suffix, os.path.join(run_dir, MOCKUP + suffix))

    # theme.json copies and diffs
    prev = previous_run(RUNS, run_name, theme_ids)
    diffs = {}
    for tid in theme_ids:
        src = os.path.join(themes.default_themes_root(), tid, "theme.json")
        dst = os.path.join(run_dir, "themes", "%s.theme.json" % tid)
        shutil.copyfile(src, dst)
        old = None
        if prev:
            p = os.path.join(RUNS, prev, "themes", "%s.theme.json" % tid)
            if os.path.exists(p):
                with open(p, encoding="utf-8") as f:
                    old = json.load(f)
        diffs[tid] = diff_theme_json(old, load_raw(tid)) if old is not None else []
    info.update(previous_run=prev, theme_diffs=diffs)

    # apply
    reports = {}
    for tid in theme_ids:
        out = os.path.join(run_dir, "%s_%s.csx" % (MOCKUP, tid))
        rep, text = apply_theme(izvorno, base + ".csx", tid, out,
                                os.path.join(run_dir, "report_%s.json" % tid))
        t = themes.load_theme(tid)
        reports[tid] = report_summary(rep, {"lines": set(t.lines), "areas": set(t.areas)})
        print("    " + text.splitlines()[0])
    timer("theme_apply × %d" % len(theme_ids))

    # seed variants of the first theme (cache, not the record)
    seed_dir = os.path.join(croot, "rounds", run_name)
    jobs = [(os.path.join(run_dir, "%s_%s.csx" % (MOCKUP, tid)), run_dir) for tid in theme_ids]
    seed_pdfs = {}
    if args.seeds:
        if os.path.isdir(seed_dir):
            shutil.rmtree(seed_dir)
        os.makedirs(seed_dir)
        first = os.path.join(run_dir, "%s_%s.csx" % (MOCKUP, theme_ids[0]))
        for k in range(1, args.seeds + 1):
            dst = os.path.join(seed_dir, "%s_%s_s%d.csx" % (MOCKUP, theme_ids[0], k))
            make_theme_mockup.seed_file(first, dst, variant=k)
            jobs.append((dst, seed_dir))
    printed = print_plans(jobs, real, os.path.join(croot, "_print", run_name))
    for tid in theme_ids:
        pdf = os.path.join(run_dir, "%s_%s_plan.pdf" % (MOCKUP, tid))
        png_of(pdf, pdf[:-4] + ".png")
    for k in range(1, (args.seeds or 0) + 1):
        seed_pdfs[k] = os.path.join(seed_dir, "%s_%s_s%d_plan.pdf" % (MOCKUP, theme_ids[0], k))
    timer("headless print × %d (parallel)" % len(printed))

    # sheets
    iz = Print(os.path.join(run_dir, "%s_%s_plan.pdf" % (MOCKUP, IZVORNO)), layout)
    prints = {IZVORNO: iz}
    for tid in theme_ids:
        prints[tid] = Print(os.path.join(run_dir, "%s_%s_plan.pdf" % (MOCKUP, tid)), layout,
                            fallback=iz.fit)
    variants = [IZVORNO] + theme_ids
    slots = layout["slots"]
    sheets, files = [], []
    for kind, stem, title, dpi, pad in SHEETS:
        rows = []
        for s in slots:
            if s["kind"] != kind or not s["themes"]:
                continue
            b = s["box"]
            # lines: from just above the wall loop (the label band carries nothing)
            top = s["station"][1] + 1.0 if kind == "lines" else b[1] - pad
            box = (b[0] - pad, top, b[2] + pad, b[3] + pad)
            rows.append(("%s %s" % (s["tag"], s["name"]), [prints[v].crop(box, dpi) for v in variants]))
        name = "%s_%s_usporedba.png" % (MOCKUP, stem)
        if grid_sheet("%s  (%d dpi)" % (title, dpi), variants, rows, os.path.join(run_dir, name)):
            sheets.append((name, "%s, every themed slot: %s (%d dpi crops)"
                           % (stem, " · ".join(variants), dpi)))
    timer("comparison sheets")

    # focus
    focus = parse_focus(args.focus)
    auto = False
    if not focus:
        ck = set()
        for rows in diffs.values():
            ck |= changed_keys(rows)
        if split_lines:
            for kind in KINDS:
                ck |= {(kind, k) for k in sd[kind]["changed"] + sd[kind]["added"]}
        focus = sorted(ck)[:6]
        auto = bool(focus)
    focus_slots = match_focus(focus, slots)
    details = []
    detail_imgs = []
    for s in focus_slots:
        b = s["box"]
        if s["kind"] == "lines":
            box = (b[0] - 0.05, b[1] + 1.5, b[2], b[3] - 0.3)   # both strokes, no label
            what = "straight (top) and curve (bottom)"
        elif s["kind"] == "areas":
            x, yb = s["station"]
            box = (x - 0.1, yb + 1.5, x + 2.1, yb + 3.2)
            what = "the 2 × 1.5 m sample"
        else:
            box = tuple(b)
            what = "the sign"
        ims = [prints[v].crop(box, args.detail_dpi) for v in variants]
        name = "%s_detalj_%s_%s.png" % (MOCKUP, s["tag"], safe(s["name"]))
        grid_sheet("%s %s – %s, %d dpi" % (s["tag"], s["name"], what, args.detail_dpi),
                   variants, [("%s\n%s" % (s["tag"], s["name"]), ims)], os.path.join(run_dir, name),
                   label_w=170)
        details.append((name, "focus %s %s at %d dpi: %s" % (s["tag"], s["name"],
                                                             args.detail_dpi, " · ".join(variants))))
        detail_imgs.append((s, [prints[v].crop(box, 600) for v in variants]))
    if focus_slots:
        timer("focus details × %d" % len(focus_slots))

    # ink cover + seed sheet
    area_slots = [s for s in slots if s["kind"] == "areas" and s["themes"]]
    cols = [IZVORNO] + ["%s s0" % t for t in theme_ids] + \
        ["%s s%d" % (theme_ids[0], k) for k in sorted(seed_pdfs)]
    seed_prints = {}
    for k, pdf in sorted(seed_pdfs.items()):
        seed_prints[k] = Print(pdf, layout, fallback=iz.fit)
    ink_rows = []
    seed_rows = [[] for _ in range(len(seed_prints) + 1)]
    for s in area_slots:
        vals = {}
        inner = area_inner(s)
        vals[IZVORNO] = ink_stats(iz.crop(inner, INK_DPI, fade=False))
        for tid in theme_ids:
            vals["%s s0" % tid] = ink_stats(prints[tid].crop(inner, INK_DPI, fade=False))
        for k, p in sorted(seed_prints.items()):
            vals["%s s%d" % (theme_ids[0], k)] = ink_stats(p.crop(inner, INK_DPI, fade=False))
        ink_rows.append((s["tag"], s["name"], vals))
        if seed_prints:
            x, yb = s["station"]
            box = (x - 0.1, yb + 1.5, x + 2.1, yb + 3.2)
            seed_rows[0].append(prints[theme_ids[0]].crop(box, 700))
            for k, p in sorted(seed_prints.items()):
                seed_rows[k].append(p.crop(box, 700))
    info["ink"] = {"cols": cols, "rows": ink_rows}
    if seed_prints:
        rows = []
        for k, ims in enumerate(seed_rows):
            rows.append(("seed s%d%s" % (k, " (fixed)" if k == 0 else ""), ims))
        name = "%s_plohe_seedovi.png" % MOCKUP
        heads = ["%s %s" % (s["tag"], s["name"]) for s in area_slots]
        grid_sheet("PLOHE – %s, %d placement seeds (700 dpi)" % (theme_ids[0], len(rows)),
                   heads, rows, os.path.join(run_dir, name), label_w=170)
        sheets.append((name, "%s areas, one row per placement seed; ink cover in RUNLOG"
                       % theme_ids[0]))
    timer("ink cover%s" % (" + seed sheet" if seed_prints else ""))

    # pregled.png
    head = ["# Theme round %s, %s – %s" % (args.label, date, " · ".join(variants))]
    if focus_slots:
        head.append("Focus%s: %s" % (" (auto: changed keys)" if auto else "",
                                     ", ".join("%s %s" % (s["tag"], s["name"]) for s in focus_slots)))
    if prev:
        head.append("theme.json changes since %s:" % prev)
        n = 0
        for tid, rows in diffs.items():
            for op, path, o, nw in rows:
                head.append("  %s %s  %s: %s -> %s" % (op, tid, path, jv(o)[:60], jv(nw)[:60]))
                n += 1
        if not n:
            head.append("  (none)")
    else:
        head.append("Baseline round: no earlier theme.json copies to compare.")
    if split_lines:
        head.append("Artwork split (%s):" % os.path.basename(args.svg))
        head += ["  " + ln if not ln.startswith("!!") else ln for ln in split_lines[:40]]
    blocks = [text_block(head, 1800)]
    for s, ims in detail_imgs:
        from PIL import Image as _I
        rows = [("%s\n%s" % (s["tag"], s["name"]), ims)]
        tmp = os.path.join(run_dir, "_pregled_tmp.png")
        grid_sheet("%s %s (600 dpi)" % (s["tag"], s["name"]), variants, rows, tmp, label_w=170)
        blocks.append(_I.open(tmp).copy())
        os.remove(tmp)
    tail = ["Files in this round:"] + ["  %s" % n for n, _ in details + sheets]
    blocks.append(text_block(tail, 1800))
    stack(blocks, os.path.join(run_dir, "pregled.png"))
    timer("pregled.png")

    # RUNLOG
    svg_mtime = datetime.datetime.fromtimestamp(os.path.getmtime(args.svg)).isoformat(
        sep=" ", timespec="minutes") if os.path.exists(args.svg) else "–"
    info["inputs"] = [
        ("drawing", "`%s`, modified %s%s" % (rel(args.svg, PROJECT), svg_mtime,
                                              " – re-split this round" if args.split else
                                              " – not re-split")),
        ("themes", ", ".join("`%s`" % t for t in theme_ids)),
        ("mockup cache", "`mockup-%s` (%s)" % (key, "built this round" if fresh else "reused")),
        ("cache key inputs", ", ".join("%s %s" % kv for kv in sorted(versions.items()))),
        ("cSurvey (prints)", "`%s`" % real),
        ("cSurvey (import)", "DTD-free copy under the cache"),
        ("area seeds", "fixed per area (make_theme_mockup.area_seed); %d alternative(s)"
         % (args.seeds or 0)),
    ]
    info["split"] = split_lines
    info["reports"] = reports
    info["details"] = details
    info["sheets"] = sheets
    info["cache_dir"] = "<workspace>/runs/theme-round/mockup-%s" % key
    files = [("pregled.png", "overview: changes on top, focus crops")]
    files += details + sheets
    files += [("%s_%s_plan.pdf" % (MOCKUP, v), "cSurvey headless plan print (+ `.png` at 110 dpi)")
              for v in variants]
    files += [("report_%s.json" % t, "`theme_apply` report") for t in theme_ids]
    files += [("themes/%s.theme.json" % t, "theme.json as used this round") for t in theme_ids]
    files += [("%s-key.md" % MOCKUP, "slot table"), ("%s-layout.json" % MOCKUP,
                                                     "slot world coordinates")]
    info["files"] = files
    timer("RUNLOG")
    info["timings"] = timer.rows
    with open(os.path.join(run_dir, "RUNLOG.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write(render_runlog(info))
    total = sum(s for _, s in timer.rows)
    print("done in %.1f s -> %s" % (total, rel(run_dir, STAGE)))
    for n, _ in [("pregled.png", "")] + details + sheets:
        print("  " + n)
    for x in warnings:
        print("  !!! " + x)
    return 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("label", help="round label, e.g. r8-blocks (run folder <date>-<label>)")
    ap.add_argument("--split", action="store_true", help="re-split the drawing into themes/boja first")
    ap.add_argument("--svg", default=DEFAULT_SVG, help="the Illustrator export (default: %(default)s)")
    ap.add_argument("--themes", default="boja,crno-bijelo")
    ap.add_argument("--focus", default="", help="keys for detail crops: key, kind/key or slot tag")
    ap.add_argument("--seeds", type=int, default=0, help="N alternative area seeds (first theme)")
    ap.add_argument("--fresh-mockup", action="store_true", help="rebuild the mockup cache")
    ap.add_argument("--no-print", action="store_true", help="validate only")
    ap.add_argument("--date", help="run folder date (default today)")
    ap.add_argument("--detail-dpi", type=int, default=2000)
    args = ap.parse_args(argv)
    args.argv = argv
    if not re.match(r"^[A-Za-z0-9._-]+$", args.label):
        ap.error("label: letters, digits, . _ - only")
    try:
        return run(args)
    except (RoundError, themes.ThemeError) as e:
        print("ERROR: %s" % e, file=sys.stderr)
        return 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
