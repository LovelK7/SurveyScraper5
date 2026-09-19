"""The doctor must FAIL LOUDLY when an input is missing.

The previous version had eight places where a missing input meant `return` or
`continue`: the check silently examined nothing and the run still exited 0.
/feature-dev and /wrap-up both gate on that exit code, so a clean report from a
doctor that checked nothing is worse than a crash.

Every test here deletes or breaks one input and asserts exit 1. That is the
regression test for the whole silent-no-op class, including shapes nobody has
thought of yet — the work-counter floors catch those.
"""

from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path

import pytest

DOCTOR = Path(__file__).resolve().parents[1] / "pipeline_doctor.py"
REPO = Path(__file__).resolve().parents[2]

README_WITH_CODE = '# 4O\n\nRuns `cavedossier osz prefill`. Code in osz/. See [design](docs/design.md).\n\nA code span: `[B11](M6)` and a fence:\n\n```\n[B6](B7)\n```\n\n<pre>\n[B10](M5) inside a raw HTML block\n</pre>\n'

README_WITH_REAL_BREAK = '# 4O\n\nRuns `cavedossier osz prefill`. Code in osz/.\nSee [design](docs/design.md) and [gone](docs/gone.md).\n'


def load_doctor():
    """A fresh module each time — the doctor accumulates into module globals."""
    spec = importlib.util.spec_from_file_location("pipeline_doctor_under_test", DOCTOR)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run(manifest: Path) -> int:
    return load_doctor().main(["--manifest", str(manifest)])


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    """A miniature repo the doctor can pass cleanly."""
    r = tmp_path / "repo"
    (r / "stages" / "0P-platform" / "src" / "cave_dossier" / "cli").mkdir(parents=True)
    (r / "stages" / "0P-platform" / "src" / "cave_dossier" / "core").mkdir(parents=True)
    (r / "stages" / "4O-osz" / "src" / "cave_dossier" / "osz").mkdir(parents=True)
    (r / "stages" / "4O-osz" / "docs").mkdir(parents=True)

    pkg = r / "stages" / "0P-platform" / "src" / "cave_dossier"
    (pkg / "cli" / "__init__.py").write_text(
        'sub = parser.add_subparsers()\n'
        'sub.add_parser("osz")\n', encoding="utf-8")
    (pkg / "core" / "__init__.py").write_text("", encoding="utf-8")
    (r / "stages" / "4O-osz" / "src" / "cave_dossier" / "osz" / "__init__.py").write_text(
        "", encoding="utf-8")

    (r / "stages" / "0P-platform" / "README.md").write_text(
        "# 0P\n\nThe spine: core and cli.\n", encoding="utf-8")
    (r / "stages" / "4O-osz" / "README.md").write_text(
        "# 4O\n\nRuns `cavedossier osz prefill`. Code in osz/. See "
        "[design](docs/design.md).\n", encoding="utf-8")
    (r / "stages" / "4O-osz" / "docs" / "design.md").write_text("# design\n", encoding="utf-8")

    (r / "ARCHITECTURE.md").write_text(
        "# arch\n\n### Bridge catalog\n\n| B6 | `cavedossier osz prefill` |\n\n"
        "### Chains\n\nx\n", encoding="utf-8")
    (r / "STATUS.md").write_text("# status\n\n| M4 | planned |\n", encoding="utf-8")

    (r / "pipeline.yaml").write_text(
        "version: 1\n"
        "package: cave_dossier\n"
        "skip_dirs: [.git]\n"
        "history_dirs: [journal]\n"
        "bridge_exempt: []\n"
        "stages:\n"
        "  - id: platform\n"
        "    label: '0P'\n"
        "    dir: stages/0P-platform\n"
        "    modules: [core, cli]\n"
        "    commands: []\n"
        "  - id: osz\n"
        "    label: '4O'\n"
        "    dir: stages/4O-osz\n"
        "    modules: [osz]\n"
        "    commands: [osz]\n",
        encoding="utf-8")
    return r


def relax_floors(mod) -> None:
    """The fixture repo is tiny; the floors are calibrated for the real one."""
    for key in mod.MINIMUM_WORK:
        mod.MINIMUM_WORK[key] = 0


def run_relaxed(manifest: Path) -> int:
    mod = load_doctor()
    relax_floors(mod)
    return mod.main(["--manifest", str(manifest)])


def test_clean_repo_passes(repo: Path):
    assert run_relaxed(repo / "pipeline.yaml") == 0


def test_missing_stage_dir_fails(repo: Path):
    shutil.rmtree(repo / "stages" / "4O-osz")
    assert run_relaxed(repo / "pipeline.yaml") == 1


def test_missing_stage_readme_fails(repo: Path):
    (repo / "stages" / "4O-osz" / "README.md").unlink()
    assert run_relaxed(repo / "pipeline.yaml") == 1


def test_unclaimed_stage_dir_fails(repo: Path):
    (repo / "stages" / "9Z-mystery").mkdir()
    assert run_relaxed(repo / "pipeline.yaml") == 1


def test_unclaimed_subpackage_fails(repo: Path):
    extra = repo / "stages" / "4O-osz" / "src" / "cave_dossier" / "smuggled"
    extra.mkdir()
    (extra / "__init__.py").write_text("", encoding="utf-8")
    assert run_relaxed(repo / "pipeline.yaml") == 1


def test_command_not_in_owning_stage_readme_fails(repo: Path):
    (repo / "stages" / "4O-osz" / "README.md").write_text(
        "# 4O\n\nNothing about the command here. Code in osz/.\n", encoding="utf-8")
    assert run_relaxed(repo / "pipeline.yaml") == 1


def test_missing_cli_module_fails(repo: Path):
    (repo / "stages" / "0P-platform" / "src" / "cave_dossier" / "cli" / "__init__.py").unlink()
    assert run_relaxed(repo / "pipeline.yaml") == 1


def test_missing_architecture_fails(repo: Path):
    """The old doctor silently skipped both the bridge and the STALE checks."""
    (repo / "ARCHITECTURE.md").unlink()
    assert run_relaxed(repo / "pipeline.yaml") == 1


def test_missing_status_fails(repo: Path):
    (repo / "STATUS.md").unlink()
    assert run_relaxed(repo / "pipeline.yaml") == 1


def test_renamed_bridge_catalog_heading_fails(repo: Path):
    """A find()-based slice used to return garbage here and check nothing."""
    (repo / "ARCHITECTURE.md").write_text(
        "# arch\n\n### Bridges\n\n| B6 | x |\n\n### Chains\n\nx\n", encoding="utf-8")
    assert run_relaxed(repo / "pipeline.yaml") == 1


def test_broken_link_fails(repo: Path):
    (repo / "stages" / "4O-osz" / "README.md").write_text(
        "# 4O\n\n`cavedossier osz prefill`, code in osz/. See [gone](docs/gone.md).\n",
        encoding="utf-8")
    assert run_relaxed(repo / "pipeline.yaml") == 1


def test_duplicate_test_basenames_fail(repo: Path):
    for stage in ("0P-platform", "4O-osz"):
        d = repo / "stages" / stage / "tests"
        d.mkdir(parents=True, exist_ok=True)
        (d / "test_models.py").write_text("", encoding="utf-8")
    assert run_relaxed(repo / "pipeline.yaml") == 1


def test_starved_check_fails_even_with_no_findings(repo: Path):
    """The core of the fix: doing too little work is itself a failure.

    With the real floors in force, the tiny fixture repo cannot possibly have
    examined enough — and must NOT report a clean bill of health.
    """
    mod = load_doctor()          # floors NOT relaxed
    assert mod.main(["--manifest", str(repo / "pipeline.yaml")]) == 1


def test_real_repo_is_clean():
    """The actual repo must pass, with its real floors."""
    assert load_doctor().main(["--manifest", str(REPO / "pipeline.yaml")]) == 0

def test_link_syntax_in_code_and_pre_is_not_a_link(repo: Path):
    """[label](target) is not a link inside a code span, fence or <pre>.

    GitHub does not parse markdown in any of those, so it renders literally.
    The doctor used to scan raw text, which failed on this repo's own
    ARCHITECTURE diagrams and on backlog entries quoting the syntax on purpose.
    """
    (repo / "stages" / "4O-osz" / "README.md").write_text(
        README_WITH_CODE, encoding="utf-8")
    assert run_relaxed(repo / "pipeline.yaml") == 0


def test_a_real_broken_link_outside_code_still_fails(repo: Path):
    """...but the same syntax in ordinary prose is still checked."""
    (repo / "stages" / "4O-osz" / "README.md").write_text(
        README_WITH_REAL_BREAK, encoding="utf-8")
    assert run_relaxed(repo / "pipeline.yaml") == 1
