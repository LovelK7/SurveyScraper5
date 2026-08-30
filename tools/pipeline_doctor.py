# -*- coding: utf-8 -*-
"""Pipeline doctor — structural health of the SurveyScraper5 codebase docs.

The closing step of `/feature-dev` (and useful ad hoc):

    python tools/pipeline_doctor.py

Checks (FAIL breaks the exit code, WARN is a worklist, INFO is a reminder):

  1. LINKS    every relative markdown link resolves to a real file, and
              every `#fragment` to a real heading slug or <a name> anchor
  2. CLI↔DOC  every `cavedossier` subcommand registered in cli.py appears
              in the feature README's Commands section AND in ARCHITECTURE's
              bridge catalog
  3. INDEX    every Python module under src/ appears in the feature's
              _INDEX.md, and every path _INDEX mentions still exists
  4. ORPHANS  every file in a feature's docs/ is referenced from that
              feature's _INDEX.md or README.md
  5. STALE    lines in ARCHITECTURE / STATUS that claim "waiting on /
              not started / planned" — a human or agent re-confirms each
              is still true (these rot silently; the 2.1b row did)

Exit codes: 0 clean (warnings allowed), 1 any FAIL.
"""

from __future__ import annotations

import re
import sys
import unicodedata
from pathlib import Path
from urllib.parse import unquote

sys.stdout.reconfigure(encoding="utf-8")

REPO = Path(__file__).resolve().parents[1]

# Directories whose .md files are part of the structural documentation.
DOC_DIRS = [REPO] + sorted(p for p in (REPO / "features").iterdir() if p.is_dir())
SKIP_DIR_NAMES = {".git", ".venv", "node_modules", "__pycache__", "runs", "example",
                  "data", "literature", "sb-sync", ".claude"}

LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
ANCHOR_RE = re.compile(r'<a\s+(?:name|id)="([^"]+)"')
HEADING_RE = re.compile(r"^#{1,6}\s+(.*)$", re.MULTILINE)
ADD_PARSER_RE = re.compile(r'add_parser\(\s*\n?\s*"([a-z-]+)"')

failures: list[str] = []
warnings: list[str] = []
infos: list[str] = []


def md_files() -> list[Path]:
    found: list[Path] = []
    for base in DOC_DIRS:
        for path in base.rglob("*.md"):
            if any(part in SKIP_DIR_NAMES for part in path.relative_to(REPO).parts):
                continue
            found.append(path)
    return sorted(set(found))


def github_slug(heading: str) -> str:
    """Approximate GitHub's heading→anchor slugger."""
    text = re.sub(r"`([^`]*)`", r"\1", heading)          # strip code spans
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)  # strip links, keep text
    text = re.sub(r"[*_]", "", text)
    out = []
    for ch in unicodedata.normalize("NFC", text.strip().lower()):
        if ch.isalnum():
            out.append(ch)
        elif ch in (" ", "-"):
            out.append("-" if ch == "-" else "-")
    return "".join(out)


def anchors_of(path: Path, cache: dict[Path, set[str]]) -> set[str]:
    if path not in cache:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            cache[path] = set()
            return cache[path]
        slugs = {github_slug(h) for h in HEADING_RE.findall(text)}
        slugs |= set(ANCHOR_RE.findall(text))
        cache[path] = slugs
    return cache[path]


# Historical logs were migrated VERBATIM (CLAUDE.md §Path conventions): their
# pre-migration paths are expected to dangle — worklist, not failure.
HISTORY_DIR_NAMES = {"sessions", "projects"}
# Citations into the read-only reference clone resolve against ../cSurvey.
CSURVEY_CLONE = REPO.parent / "cSurvey"
# A doc copied verbatim from another repo keeps its original links; mark it
# with this comment near the provenance header and the doctor skips them.
SKIP_MARKER = "<!-- doctor:skip-links -->"


def check_links() -> None:
    cache: dict[Path, set[str]] = {}
    for md in md_files():
        text = md.read_text(encoding="utf-8")
        if SKIP_MARKER in text:
            continue
        rel = md.relative_to(REPO)
        historical = bool(HISTORY_DIR_NAMES & set(rel.parts))
        for raw_target in LINK_RE.findall(text):
            target = unquote(raw_target)
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            if "..." in target:  # a literal placeholder path, not a link
                continue
            file_part, _, fragment = target.partition("#")
            if file_part:
                resolved = (md.parent / file_part).resolve()
                if not resolved.exists():
                    # cSurvey citations: try the reference clone.
                    clone_hit = None
                    normalized = re.sub(r"^(\.\./)+", "", file_part)
                    for prefix in ("cSurvey/", "cSurveyPC/"):
                        if normalized.startswith(prefix):
                            candidate = (CSURVEY_CLONE /
                                         normalized.removeprefix("cSurvey/"))
                            if candidate.exists():
                                clone_hit = candidate
                            break
                    if clone_hit is None:
                        message = f"{rel}: broken link → {raw_target}"
                        if historical:
                            warnings.append(f"LINK   {message} (historical log — "
                                            "migrated verbatim, fix only if cheap)")
                        else:
                            failures.append(f"LINK   {message}")
                    continue
            else:
                resolved = md
            if fragment and resolved.suffix == ".md" and not re.fullmatch(r"L\d+(-L\d+)?", fragment):
                if fragment not in anchors_of(resolved, cache):
                    warnings.append(f"ANCHOR {rel}: #{fragment} not found in "
                                    f"{resolved.relative_to(REPO)}")


def check_cli_vs_docs() -> None:
    cli = REPO / "features" / "cave-dossier" / "src" / "cave_dossier" / "cli.py"
    readme = REPO / "features" / "cave-dossier" / "README.md"
    arch = REPO / "ARCHITECTURE.md"
    if not cli.exists():
        return
    commands = sorted(set(ADD_PARSER_RE.findall(cli.read_text(encoding="utf-8"))))
    readme_text = readme.read_text(encoding="utf-8") if readme.exists() else ""
    arch_text = arch.read_text(encoding="utf-8") if arch.exists() else ""
    catalog = arch_text[arch_text.find("### Bridge catalog"):arch_text.find("### Chains")]
    for command in commands:
        if command not in readme_text:
            failures.append(f"CLIDOC subcommand '{command}' is registered in cli.py "
                            f"but absent from the feature README")
        if command not in catalog and command not in ("columns", "inspect", "stats",
                                                      "audit-authors", "unclassified",
                                                      "check-flag", "za-istrazit"):
            warnings.append(f"BRIDGE subcommand '{command}' not named in "
                            f"ARCHITECTURE's bridge catalog — new bridge, or part "
                            f"of an existing one? say so there")


def check_index() -> None:
    for feature in sorted((REPO / "features").iterdir()):
        index = feature / "_INDEX.md"
        src = feature / "src"
        if not index.exists() or not src.exists():
            continue
        index_text = index.read_text(encoding="utf-8")
        for py in sorted(src.rglob("*.py")):
            if py.name == "__init__.py" or "__pycache__" in py.parts:
                continue
            package_rel = py.relative_to(next(src.iterdir()))  # src/<pkg>/…
            as_posix = package_rel.as_posix()
            package_dir = package_rel.parts[0] + "/" if len(package_rel.parts) > 1 else ""
            if as_posix not in index_text and py.name not in index_text and (
                not package_dir or f"`{package_dir}`" not in index_text
            ):
                warnings.append(f"INDEX  {feature.name}: {as_posix} is not in _INDEX.md")
        for mention in re.findall(r"`((?:src/|docs/|tests/|config/)[^`]+)`", index_text):
            if not (feature / mention).exists():
                failures.append(f"INDEX  {feature.name}: _INDEX.md mentions missing "
                                f"path {mention}")


def check_doc_orphans() -> None:
    for feature in sorted((REPO / "features").iterdir()):
        docs = feature / "docs"
        if not docs.is_dir():
            continue
        referencers = ""
        for name in ("_INDEX.md", "README.md"):
            page = feature / name
            if page.exists():
                referencers += page.read_text(encoding="utf-8")
        for doc in sorted(docs.glob("*.md")):
            if doc.name not in referencers:
                warnings.append(f"ORPHAN {feature.name}: docs/{doc.name} is not "
                                f"referenced from _INDEX.md or README.md")


def check_stale_claims() -> None:
    suspects = re.compile(r"waiting on|not started|planned|gated|pending|NOT STARTED",
                          re.IGNORECASE)
    for name in ("ARCHITECTURE.md", "STATUS.md"):
        path = REPO / name
        if not path.exists():
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if suspects.search(line) and "|" in line:  # table rows rot the fastest
                infos.append(f"STALE? {name}:{lineno}: {line.strip()[:100]}")


def main() -> int:
    check_links()
    check_cli_vs_docs()
    check_index()
    check_doc_orphans()
    check_stale_claims()

    for f in failures:
        print(f"FAIL  {f}")
    for w in warnings:
        print(f"WARN  {w}")
    if infos:
        print()
        print("Re-confirm these status claims are still true (they rot silently):")
        for i in infos:
            print(f"  {i}")
    print()
    print(f"pipeline doctor: {len(failures)} fail · {len(warnings)} warn · "
          f"{len(infos)} status claims to re-confirm")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
