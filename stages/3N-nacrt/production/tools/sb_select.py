#!/usr/bin/env python3
"""Pick the intake folders of specific caves by their Redni broj (SB number).

Shared by preprocess_tdx_csx.py and tdx_zip_to_csx.py so that a double-click
asks *which* caves to process instead of sweeping the whole intake tree (user,
2026-09-20: "I don't want all files in Za digitalizirat preprocessed").

The unit of work on the Drive is a leaf folder per cave under
`!Za digitalizirat`, named `SB_<Redni broj>_<Ime>[_…]` — see
prod/drive-layout.md. Numbers are compared numerically, so 811, 0811 and a
folder named `SB_00811_…` all match each other.

Stdlib only, no imports from the rest of the repo: this file travels into the
operator kit (`csurvey_alati/`) beside the two tools that use it.
"""

import os
import re

# SB_<broj> optionally followed by _<anything>. The broj may be zero-padded.
_LEAF = re.compile(r"^SB[_-]0*(\d+)(?:[_\-. ].*)?$", re.I)


def parse_numbers(tokens):
    """['811', '0908,', '9'] -> [811, 908, 9]; raises ValueError on junk."""
    numbers = []
    for raw in tokens:
        for part in re.split(r"[,;]+", str(raw)):
            part = part.strip()
            if not part:
                continue
            if not part.isdigit():
                raise ValueError(part)
            numbers.append(int(part))
    return numbers


def leaf_number(dirname):
    """The Redni broj a leaf folder name carries, or None."""
    m = _LEAF.match(dirname)
    return int(m.group(1)) if m else None


def find_dirs(root, numbers):
    """Resolve SB numbers to leaf folders under `root`.

    Returns (dirs, missing): the matched folder paths (sorted, deduplicated,
    outermost match wins — a nested SB_ folder inside a matched one is already
    covered by it) and the numbers that matched nothing.
    """
    wanted = set(numbers)
    found = {}
    for dirpath, dirnames, _files in os.walk(root):
        for name in sorted(dirnames):
            n = leaf_number(name)
            if n in wanted:
                found.setdefault(n, []).append(os.path.join(dirpath, name))
        # don't descend into a folder we already matched
        dirnames[:] = [d for d in dirnames if leaf_number(d) not in found]
    dirs = sorted({p for paths in found.values() for p in paths})
    missing = [n for n in numbers if n not in found]
    return dirs, missing


def resolve(root, tokens, label="!Za digitalizirat"):
    """Full CLI path: tokens -> folder list, printing what it found.

    Returns the list of folders, or None if the selection is unusable (bad
    input, or no folder found for any number) — the caller should then stop.
    """
    try:
        numbers = parse_numbers(tokens)
    except ValueError as bad:
        print("ERROR: '%s' nije broj. Upisi Redni broj objekta, npr. 811." % bad)
        return None
    if not numbers:
        print("ERROR: nijedan Redni broj nije upisan.")
        return None
    if not os.path.isdir(root):
        print("ERROR: ne mogu pronaci mapu %s (%s)" % (label, root))
        return None

    dirs, missing = find_dirs(root, numbers)
    for n in missing:
        print("UPOZORENJE: nema mape SB_%d_... u %s" % (n, label))
    if not dirs:
        print("nothing to do - ni jedan upisani broj nema svoju mapu")
        return None
    for d in dirs:
        print("SB %s -> %s" % (leaf_number(os.path.basename(d)), d))
    return dirs


def list_files(dirs, exts, skip_suffixes=()):
    """Every file with one of `exts` under the given folders, sorted.

    `skip_suffixes` drops outputs a tool made itself (e.g. `_lt`), so a second
    pass over a cave folder does not offer <name>_lt as an input again.
    """
    exts = tuple(e.lower() for e in exts)
    skip = tuple(s.lower() for s in skip_suffixes)
    found = []
    for d in dirs:
        for dirpath, _dirs, names in os.walk(d):
            for fn in sorted(names):
                stem, ext = os.path.splitext(fn)
                if ext.lower() not in exts:
                    continue
                if stem.lower().endswith(skip):
                    continue
                found.append(os.path.join(dirpath, fn))
    return sorted(found)


def choose(paths, labels=None, root=None, prompt="Koju datoteku? ",
           allow_all=True):
    """Ask which of `paths` to work on. Returns a list, or None to stop.

    One candidate is used without asking (and named, so the operator sees what
    happened). Several produce a numbered menu; `labels[i]` annotates entry i
    (here: whether the file has been through cSurvey's import yet). The answer
    may be a number, SVE for all of them, or Enter to cancel.
    """
    def show(p):
        if root:
            try:
                return os.path.relpath(p, root)
            except ValueError:
                pass
        return p

    if not paths:
        return None
    if len(paths) == 1:
        print("datoteka: %s" % show(paths[0]))
        return list(paths)

    print()
    print("  Nasao sam vise datoteka:")
    for i, p in enumerate(paths, 1):
        note = "  - %s" % labels[i - 1] if labels else ""
        print("   %2d) %s%s" % (i, show(p), note))
    print()
    if allow_all:
        print("  Upisi broj datoteke, SVE za sve, Enter = odustani.")
    else:
        print("  Upisi broj datoteke, Enter = odustani.")
    try:
        raw = input(prompt).strip()
    except EOFError:
        raw = ""
    if not raw:
        print("odustao si - nista nije promijenjeno")
        return None
    if allow_all and raw.upper() in ("SVE", "ALL", "*"):
        return list(paths)
    if raw.isdigit() and 1 <= int(raw) <= len(paths):
        return [paths[int(raw) - 1]]
    print("ERROR: '%s' nije ponudeni broj." % raw)
    return None
