# -*- coding: utf-8 -*-
"""Pipeline doctor — structural health of the SurveyScraper5 docs and tree.

The closing step of `/feature-dev` (and useful ad hoc):

    python tools/pipeline_doctor.py

Checks (FAIL breaks the exit code, WARN is a worklist, INFO is a reminder):

  1. STRUCTURE every stage in pipeline.yaml exists with a README; every stage
               folder, subpackage and CLI command is claimed by exactly one
               stage; no duplicate test basenames
  2. LINKS     every relative markdown link resolves to a real file, and every
               `#fragment` to a real heading slug or <a name> anchor
  3. CLI-DOC   every `cavedossier` subcommand registered in cli.py appears in
               the README of the stage that CLAIMS it, and in ARCHITECTURE's
               bridge catalog
  4. INDEX     every Python module is reachable from its stage's README, and
               every path a stage README mentions still exists
  5. ORPHANS   every file in a stage's docs/ is referenced from its README
  6. STALE     lines in ARCHITECTURE / STATUS claiming "waiting on / not
               started / planned" — re-confirm each is still true

WHY THE WORK COUNTERS. The previous version had eight places where a missing
input meant `return` or `continue`, so the check silently examined nothing and
the doctor reported a clean bill of health. Since /feature-dev and /wrap-up
both gate on the exit code, that is worse than a crash. Every check now
records how much work it did, and anything below its floor is a FAIL.

Exit codes: 0 clean (warnings allowed), 1 any FAIL or any check that did too
little work. A crash is also 1, never a traceback the shell might misread.
"""

from __future__ import annotations

import argparse
import re
import sys
import traceback
import unicodedata
from collections import Counter
from pathlib import Path
from urllib.parse import unquote

sys.stdout.reconfigure(encoding="utf-8")

LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
ANCHOR_RE = re.compile(r'<a\s+(?:name|id)="([^"]+)"')
HEADING_RE = re.compile(r"^#{1,6}\s+(.*)$", re.MULTILINE)
ADD_PARSER_RE = re.compile(r'add_parser\(\s*\n?\s*"([a-z-]+)"')
# Any backticked token that looks like a path: at least one "/" and a suffix.
PATH_IN_BACKTICKS_RE = re.compile(r"`([A-Za-z0-9_./-]+/[A-Za-z0-9_.-]+\.[A-Za-z0-9]+)`")
# Illustrative stand-ins, not real paths: projects/NNNN/, <broj>, glob stars.
PLACEHOLDER_RE = re.compile(r"NNNN|[<>*]")

# Citations into the read-only reference clone resolve against ../cSurvey.
SKIP_MARKER = "<!-- doctor:skip-links -->"

# Minimum work each check must do. Derived from the tree as it stands; a
# number well below these means a check stopped finding its inputs.
MINIMUM_WORK = {
    "LINKS": 300,
    "CLIDOC": 8,
    "INDEX": 40,
    "ORPHAN": 5,
    "STALE": 2,
    "STRUCTURE": 10,
}

failures: list[str] = []
warnings: list[str] = []
infos: list[str] = []
examined: Counter = Counter()


def fail(msg: str) -> None:
    failures.append(msg)


def need(path: Path, check: str, why: str, repo: Path) -> Path | None:
    """A required input. Missing means FAIL, never a silent skip."""
    if not path.exists():
        try:
            shown = path.relative_to(repo)
        except ValueError:
            shown = path
        fail(f"{check:<6} missing required input: {shown} ({why})")
        return None
    return path


def find_repo(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / "pipeline.yaml").exists() or (candidate / ".git").exists():
            return candidate
    raise SystemExit("pipeline doctor: no pipeline.yaml or .git above this script")


def load_manifest(path: Path) -> dict:
    try:
        import yaml
    except ModuleNotFoundError:
        raise SystemExit(
            "pipeline doctor: PyYAML is required.\n"
            '  Install the package first:  pip install -e ".[dev]"'
        )
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def github_slug(heading: str) -> str:
    """Approximate GitHub's heading-to-anchor slugger."""
    text = re.sub(r"`([^`]*)`", r"\1", heading)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"[*_]", "", text)
    out = []
    for ch in unicodedata.normalize("NFC", text.strip().lower()):
        if ch.isalnum():
            out.append(ch)
        elif ch in (" ", "-"):
            out.append("-")
    return "".join(out)


class Doctor:
    def __init__(self, repo: Path, manifest: dict) -> None:
        self.repo = repo
        self.m = manifest
        self.stages = manifest["stages"]
        self.package = manifest["package"]
        self.skip_dirs = set(manifest.get("skip_dirs", []))
        self.history_dirs = set(manifest.get("history_dirs", []))
        self.bridge_exempt = set(manifest.get("bridge_exempt", []))
        self.csurvey = repo.parent / "cSurvey"
        self._anchors: dict[Path, set[str]] = {}

    # ---------------------------------------------------------------- helpers
    def stage_dir(self, stage: dict) -> Path:
        return self.repo / stage["dir"]

    def md_files(self) -> list[Path]:
        found = []
        for path in self.repo.rglob("*.md"):
            parts = path.relative_to(self.repo).parts
            if any(p in self.skip_dirs for p in parts):
                continue
            found.append(path)
        return sorted(set(found))

    def anchors_of(self, path: Path) -> set[str]:
        if path not in self._anchors:
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                self._anchors[path] = set()
                return self._anchors[path]
            slugs = {github_slug(h) for h in HEADING_RE.findall(text)}
            slugs |= set(ANCHOR_RE.findall(text))
            self._anchors[path] = slugs
        return self._anchors[path]

    # ------------------------------------------------------------- 1 STRUCTURE
    def check_structure(self) -> None:
        seen_dirs = set()
        for stage in self.stages:
            d = self.stage_dir(stage)
            label = stage["label"]
            if need(d, "STRUCT", f"stage {label} dir", self.repo) is None:
                continue
            need(d / "README.md", "STRUCT", f"stage {label} README", self.repo)
            seen_dirs.add(d.name)
            examined["STRUCTURE"] += 1

        # Every folder under stages/ must be claimed.
        stages_root = self.repo / "stages"
        if need(stages_root, "STRUCT", "the stages/ root", self.repo):
            for child in sorted(stages_root.iterdir()):
                if child.is_dir() and child.name not in seen_dirs:
                    fail(f"STRUCT stages/{child.name} is not in pipeline.yaml")

        # Every subpackage must be claimed by exactly one stage.
        claimed = Counter(m for s in self.stages for m in s["modules"])
        for mod, n in claimed.items():
            if n > 1:
                fail(f"STRUCT subpackage '{mod}' is claimed by {n} stages")
        on_disk = set()
        for stage in self.stages:
            src = self.stage_dir(stage) / "src" / self.package
            if not src.is_dir():
                continue
            for child in src.iterdir():
                if child.is_dir() and (child / "__init__.py").exists():
                    on_disk.add(child.name)
        for mod in sorted(on_disk - set(claimed)):
            fail(f"STRUCT subpackage '{mod}' exists but no stage claims it")
        for mod in sorted(set(claimed) - on_disk):
            fail(f"STRUCT pipeline.yaml claims subpackage '{mod}', which does not exist")

        # Duplicate test basenames would collide under pytest's prepend import
        # mode (which the stage dir names force -- "4O-osz" is not an identifier).
        names = Counter(
            p.name for p in self.repo.rglob("test_*.py")
            if not any(x in self.skip_dirs for x in p.relative_to(self.repo).parts)
        )
        for name, n in names.items():
            if n > 1:
                fail(f"STRUCT {n} test files named {name}; prepend import mode "
                     f"will raise 'import file mismatch'")

    # ----------------------------------------------------------------- 2 LINKS
    def check_links(self) -> None:
        for md in self.md_files():
            text = md.read_text(encoding="utf-8")
            if SKIP_MARKER in text:
                continue
            rel = md.relative_to(self.repo)
            historical = bool(self.history_dirs & set(rel.parts))
            for raw_target in LINK_RE.findall(text):
                examined["LINKS"] += 1
                target = unquote(raw_target)
                if target.startswith(("http://", "https://", "mailto:")):
                    continue
                if "..." in target:
                    continue
                file_part, _, fragment = target.partition("#")
                if file_part:
                    resolved = (md.parent / file_part).resolve()
                    if not resolved.exists():
                        clone_hit = None
                        normalized = re.sub(r"^(\.\./)+", "", file_part)
                        for prefix in ("cSurvey/", "cSurveyPC/"):
                            if normalized.startswith(prefix):
                                candidate = self.csurvey / normalized.removeprefix("cSurvey/")
                                if candidate.exists():
                                    clone_hit = candidate
                                break
                        if clone_hit is None:
                            message = f"{rel}: broken link -> {raw_target}"
                            if historical:
                                warnings.append(
                                    f"LINK   {message} (historical log — migrated "
                                    f"verbatim, fix only if cheap)")
                            else:
                                fail(f"LINK   {message}")
                        continue
                else:
                    resolved = md
                if (fragment and resolved.suffix == ".md"
                        and not re.fullmatch(r"L\d+(-L\d+)?", fragment)):
                    if fragment not in self.anchors_of(resolved):
                        warnings.append(
                            f"ANCHOR {rel}: #{fragment} not found in "
                            f"{resolved.relative_to(self.repo)}")

    # --------------------------------------------------------------- 3 CLI-DOC
    def check_cli_vs_docs(self) -> None:
        platform = next((s for s in self.stages if "cli" in s["modules"]), None)
        if platform is None:
            fail("CLIDOC no stage claims the 'cli' module")
            return
        cli = self.stage_dir(platform) / "src" / self.package / "cli" / "__init__.py"
        if need(cli, "CLIDOC", "the CLI module", self.repo) is None:
            return
        arch = need(self.repo / "ARCHITECTURE.md", "CLIDOC", "the bridge catalog",
                    self.repo)
        if arch is None:
            return

        commands = sorted(set(ADD_PARSER_RE.findall(cli.read_text(encoding="utf-8"))))
        if not commands:
            fail("CLIDOC no add_parser() subcommands found in cli.py — the regex "
                 "or the CLI structure changed")
            return

        arch_text = arch.read_text(encoding="utf-8")
        match = re.search(r"### Bridge catalog\n(.*?)\n### ", arch_text, re.S)
        if match is None:
            fail("CLIDOC ARCHITECTURE.md has no '### Bridge catalog' section "
                 "followed by another '### ' heading — the catalog check cannot run")
            return
        catalog = match.group(1)

        owner: dict[str, dict] = {}
        for stage in self.stages:
            for cmd in stage["commands"]:
                if cmd in owner:
                    fail(f"CLIDOC command '{cmd}' is claimed by both "
                         f"{owner[cmd]['label']} and {stage['label']}")
                owner[cmd] = stage

        # Top-level groups are what stages own; sub-verbs belong to their group.
        top_level = self._top_level_commands(cli.read_text(encoding="utf-8"))
        for command in commands:
            examined["CLIDOC"] += 1
            if command in top_level:
                stage = owner.get(command)
                if stage is None:
                    fail(f"CLIDOC command '{command}' is registered in cli.py but "
                         f"no stage in pipeline.yaml claims it")
                    continue
                readme = self.stage_dir(stage) / "README.md"
                if not readme.exists():
                    fail(f"CLIDOC stage {stage['label']} claims '{command}' but has "
                         f"no README")
                    continue
                # Require the INVOCATION, not a bare mention: "code in osz/"
                # must not count as documenting the `osz` command.
                if f"cavedossier {command}" not in readme.read_text(encoding="utf-8"):
                    fail(f"CLIDOC '{command}' is claimed by {stage['label']} but "
                         f"{stage['dir']}/README.md never shows "
                         f"`cavedossier {command}` being run")
            if command not in catalog and command not in self.bridge_exempt:
                warnings.append(
                    f"BRIDGE subcommand '{command}' not named in ARCHITECTURE's "
                    f"bridge catalog — new bridge, or part of an existing one?")

        for cmd in sorted(set(owner) - set(commands)):
            fail(f"CLIDOC pipeline.yaml claims command '{cmd}', which cli.py does "
                 f"not register")

    @staticmethod
    def _top_level_commands(cli_text: str) -> set[str]:
        """Subcommands added to the ROOT subparsers object, not a nested one."""
        root = re.search(r"(\w+)\s*=\s*parser\.add_subparsers", cli_text)
        if root is None:
            return set()
        var = root.group(1)
        return set(re.findall(rf'{var}\.add_parser\(\s*\n?\s*"([a-z-]+)"', cli_text))

    # ----------------------------------------------------------------- 4 INDEX
    def check_index(self) -> None:
        for stage in self.stages:
            d = self.stage_dir(stage)
            readme = d / "README.md"
            if not readme.exists():
                continue  # already FAILed in check_structure
            text = readme.read_text(encoding="utf-8")

            src = d / "src" / self.package
            if src.is_dir():
                for py in sorted(src.rglob("*.py")):
                    if "__pycache__" in py.parts:
                        continue
                    examined["INDEX"] += 1
                    rel = py.relative_to(src)
                    subpkg = rel.parts[0] if len(rel.parts) > 1 else rel.stem
                    # The README must at least name the subpackage it belongs to.
                    if subpkg not in text:
                        warnings.append(
                            f"INDEX  {stage['label']}: {rel.as_posix()} — its "
                            f"subpackage '{subpkg}' is not mentioned in the README")

            for mention in PATH_IN_BACKTICKS_RE.findall(text):
                if mention.startswith(("http", "SB_", "!")):
                    continue
                if PLACEHOLDER_RE.search(mention):
                    continue  # projects/NNNN/brief.md and friends
                # A README names a module the way a human would -- "core/config.py",
                # not "src/cave_dossier/core/config.py" -- so match the mention as a
                # SUFFIX of a real path, anywhere in the repo (stages cite each other).
                if self._resolves(mention):
                    continue
                warnings.append(
                    f"INDEX  {stage['label']}: README mentions `{mention}`, which "
                    f"matches no file in the repo")

    def _resolves(self, mention: str) -> bool:
        if (self.repo / mention).exists():
            return True
        suffix = "/" + mention
        return any(p.endswith(suffix) for p in self._all_paths())

    def _all_paths(self) -> set[str]:
        if not hasattr(self, "_paths_cache"):
            paths = set()
            for p in self.repo.rglob("*"):
                rel = p.relative_to(self.repo)
                if any(x in self.skip_dirs for x in rel.parts):
                    continue
                paths.add(rel.as_posix())
            self._paths_cache = paths
        return self._paths_cache

    # --------------------------------------------------------------- 5 ORPHANS
    def check_doc_orphans(self) -> None:
        for stage in self.stages:
            d = self.stage_dir(stage)
            docs = d / "docs"
            if not docs.is_dir():
                continue
            readme = d / "README.md"
            if not readme.exists():
                fail(f"ORPHAN {stage['label']} has a docs/ but no README to "
                     f"reference it from")
                continue
            referencers = readme.read_text(encoding="utf-8")
            for doc in sorted(docs.rglob("*")):
                if not doc.is_file():
                    continue
                examined["ORPHAN"] += 1
                if doc.name not in referencers:
                    warnings.append(
                        f"ORPHAN {stage['label']}: docs/{doc.relative_to(docs).as_posix()}"
                        f" is not referenced from the stage README")

    # ----------------------------------------------------------------- 6 STALE
    def check_stale_claims(self) -> None:
        suspects = re.compile(
            r"waiting on|not started|planned|gated|pending|NOT STARTED", re.IGNORECASE)
        for name in ("ARCHITECTURE.md", "STATUS.md"):
            path = need(self.repo / name, "STALE", "a status document", self.repo)
            if path is None:
                continue
            examined["STALE"] += 1
            for lineno, line in enumerate(
                    path.read_text(encoding="utf-8").splitlines(), 1):
                if suspects.search(line) and "|" in line:
                    infos.append(f"STALE? {name}:{lineno}: {line.strip()[:100]}")

    # ------------------------------------------------------------------- drive
    def run(self) -> None:
        self.check_structure()
        self.check_links()
        self.check_cli_vs_docs()
        self.check_index()
        self.check_doc_orphans()
        self.check_stale_claims()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--manifest", type=Path, default=None,
                    help="pipeline.yaml to check against (default: found upward)")
    args = ap.parse_args(argv)

    try:
        repo = (args.manifest.resolve().parent if args.manifest
                else find_repo(Path(__file__).resolve().parent))
        manifest_path = args.manifest or (repo / "pipeline.yaml")
        if not manifest_path.exists():
            print(f"FAIL  DOCTOR no manifest at {manifest_path}")
            return 1
        Doctor(repo, load_manifest(manifest_path)).run()
    except SystemExit:
        raise
    except Exception:
        print("FAIL  DOCTOR crashed — this is a gate failure, not a clean run:")
        traceback.print_exc()
        return 1

    for f in failures:
        print(f"FAIL  {f}")
    for w in warnings:
        print(f"WARN  {w}")
    if infos:
        print()
        print("Re-confirm these status claims are still true (they rot silently):")
        for i in infos:
            print(f"  {i}")

    # A check that examined far too little has stopped finding its inputs.
    starved = []
    for check, floor in sorted(MINIMUM_WORK.items()):
        if examined[check] < floor:
            starved.append(f"{check} examined {examined[check]}, expected >= {floor}")
    for s in starved:
        print(f"FAIL  WORK   {s} — the check is not seeing its inputs")

    print()
    print("examined: " + " · ".join(
        f"{k} {examined[k]}" for k in sorted(MINIMUM_WORK)))
    total_fail = len(failures) + len(starved)
    print(f"pipeline doctor: {total_fail} fail · {len(warnings)} warn · "
          f"{len(infos)} status claims to re-confirm")
    return 1 if total_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
