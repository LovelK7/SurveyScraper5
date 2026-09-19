# -*- coding: utf-8 -*-
"""One-shot: rewrite relative markdown links for the stages/ restructure.

Driven by git's OWN rename records, so the rewrite cannot disagree with what
actually moved:

    python tools/rewrite_doc_links.py --since pre-restructure          # dry run
    python tools/rewrite_doc_links.py --since pre-restructure --apply

The rule that removes every judgement call:

    Rewrite only links that RESOLVED BEFORE the move.
    Leave everything else byte-for-byte alone.

That automatically preserves the pre-migration `dev/...` and bare
`cSurveyPC/...` paths in the verbatim-migrated logs (journal/SESSIONS.md, the
per-project log.md and RUNLOG.md files) — they were already dangling, so they
are not ours to "fix" — while catching every link that this restructure, and
only this restructure, broke.

KNOWN LIMITATION: git records renames for FILES, not directories, so a link
whose target is a directory resolves as "unmoved" and comes out pointing at
the old path. The doctor catches those (three of them in this restructure);
fix them by hand afterwards.

Delete this file once the restructure is merged; the pipeline doctor is what
keeps links honest from then on.
"""

from __future__ import annotations

import argparse
import posixpath
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote, unquote

LINK_RE = re.compile(r"(\[[^\]]*\]\()([^)\s]+)(\))")
SKIP_MARKER = "<!-- doctor:skip-links -->"
REPO = Path(__file__).resolve().parents[1]


def git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(REPO), *args],
                          capture_output=True, text=True, check=True).stdout


def move_map(since: str) -> dict[str, str]:
    """old repo-relative path -> new repo-relative path, from git's renames."""
    out = git("diff", "--name-status", "-M", f"{since}..HEAD")
    moves: dict[str, str] = {}
    for line in out.splitlines():
        parts = line.split("\t")
        if parts[0].startswith("R") and len(parts) == 3:
            moves[parts[1]] = parts[2]
    return moves


def paths_at(rev: str) -> set[str]:
    """Every file AND directory that existed at rev.

    git ls-tree -r lists files only, but docs link to directories too
    ("[features/cave-dossier/](features/cave-dossier/README.md)" is a file link,
    but "[reference/](reference/)" is not). Without the parent dirs those links
    look like they were already broken, and get left behind.
    """
    files = set(git("ls-tree", "-r", "--name-only", rev).splitlines())
    dirs: set[str] = set()
    for f in files:
        parts = f.split("/")
        for i in range(1, len(parts)):
            dirs.add("/".join(parts[:i]))
    return files | dirs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", required=True, help="tag/ref of the pre-move tree")
    ap.add_argument("--apply", action="store_true", help="write changes (default: dry run)")
    args = ap.parse_args()

    moves = move_map(args.since)
    before = paths_at(args.since)
    reverse = {new: old for old, new in moves.items()}

    changed = skipped = 0
    for md in sorted(REPO.rglob("*.md")):
        rel_new = md.relative_to(REPO).as_posix()
        if any(p in rel_new.split("/") for p in
               (".git", ".venv", "node_modules", "__pycache__", "literature", "example")):
            continue
        text = md.read_text(encoding="utf-8")
        if SKIP_MARKER in text:
            continue

        # Where this file used to live -- link targets were written relative to THAT.
        rel_old = reverse.get(rel_new, rel_new)
        old_dir = posixpath.dirname(rel_old)
        new_dir = posixpath.dirname(rel_new)
        file_changed = False

        def fix(m: re.Match) -> str:
            nonlocal file_changed, skipped
            head, target, tail = m.group(1), m.group(2), m.group(3)
            if target.startswith(("http://", "https://", "mailto:", "#")) or "..." in target:
                return m.group(0)
            raw_file, sep, frag = unquote(target).partition("#")
            if not raw_file:
                return m.group(0)
            old_target = posixpath.normpath(posixpath.join(old_dir, raw_file))
            if old_target.startswith(".."):
                return m.group(0)          # points outside the repo (../cSurvey)
            if old_target not in before:
                skipped += 1
                return m.group(0)          # was already broken -- not ours to touch
            new_target = moves.get(old_target, old_target)
            new_rel = posixpath.relpath(new_target, new_dir or ".")
            if new_rel == raw_file:
                return m.group(0)
            file_changed = True
            # Re-quote only what needs it, so readable paths stay readable.
            out = quote(new_rel, safe="/._-()!~*'")
            return f"{head}{out}{sep}{frag}{tail}"

        new_text = LINK_RE.sub(fix, text)
        if file_changed:
            changed += 1
            print(f"  {'rewrote' if args.apply else 'would rewrite'}  {rel_new}")
            if args.apply:
                md.write_text(new_text, encoding="utf-8")

    print(f"\n{changed} files {'rewritten' if args.apply else 'to rewrite'}; "
          f"{skipped} links left alone (already broken before the move)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
