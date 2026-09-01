"""Part 2.1d — `photos process`: the per-cave downsize + rename step.

Synthetic photos generated with Pillow (the same dependency the command uses),
in a folder shaped like a real intake leaf: raw camera names, a non-photo file,
and — for the idempotence test — the copies a previous run left behind.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from cave_dossier.core.config import Settings
from cave_dossier.photos import process as process_mod

Image = pytest.importorskip("PIL.Image")


def _write_photo(path: Path, size: tuple[int, int] = (2400, 1800)) -> Path:
    """A noisy JPEG — flat colour compresses to nothing, which would make every
    size assertion vacuous."""
    import numpy as np

    rng = np.random.default_rng(7)
    noise = rng.integers(0, 256, size=(size[1], size[0], 3), dtype="uint8")
    Image.fromarray(noise, "RGB").save(path, "JPEG", quality=95)
    return path


@pytest.fixture()
def leaf(tmp_path: Path) -> Path:
    folder = tmp_path / "!Za digitalizirat" / "SB_1220_Platak-Hrđava špilja_Flavio"
    folder.mkdir(parents=True)
    _write_photo(folder / "IMG_20260530_130138.jpg")
    _write_photo(folder / "IMG_20260530_130151.jpg")
    (folder / "Hrđava_špilja.csv").write_text("not a photo", encoding="utf-8")
    (folder / "desktop.ini").write_text("", encoding="utf-8")
    return folder


@pytest.fixture()
def drive_settings(settings: Settings, leaf: Path) -> Settings:
    """Settings whose intake dir is the synthetic drive root."""
    return replace(
        settings,
        local_drive_root=leaf.parent.parent,
        archive_dirs={"intake_dir": "!Za digitalizirat"},
        photo_targets={"target_long_edge_px": 1920, "target_max_bytes": 1_500_000},
    )


# ── the author token ──────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("full_name", "expected"),
    [
        ("Lovel Kukuljan", "LKukuljan"),          # the archive's own spelling
        ("Dalibor Reš", "DReš"),                  # diacritics survive
        ("L.Kukuljan", "LKukuljan"),              # SB shorthand collapses the same way
        ("Sara Kapidžić-Antolič", "SKapidžić-Antolič"),
        ("Renata", "Renata"),                     # single token passes through
        ("  ", ""),
    ],
)
def test_author_token_matches_the_archive_spelling(full_name: str, expected: str) -> None:
    assert process_mod.author_filename_token(full_name) == expected


# ── planning ──────────────────────────────────────────────────────────


def test_target_name_carries_broj_name_author_and_index() -> None:
    name = process_mod.target_name(1220, "Hrđava špilja", "LKukuljan", 2)
    assert name == "SB_1220_Hrđava špilja_LKukuljan_2.jpg"


def test_missing_author_drops_the_component_rather_than_guessing() -> None:
    assert process_mod.target_name(1220, "Hrđava špilja", None, 1) == \
        "SB_1220_Hrđava špilja_1.jpg"


def test_only_photos_are_planned(leaf: Path) -> None:
    plans = process_mod.plan_photos(leaf, 1220, "Hrđava špilja", "LKukuljan")
    assert [p.source.name for p in plans] == [
        "IMG_20260530_130138.jpg",
        "IMG_20260530_130151.jpg",
    ]
    assert [p.target.name for p in plans] == [
        "SB_1220_Hrđava špilja_LKukuljan_1.jpg",
        "SB_1220_Hrđava špilja_LKukuljan_2.jpg",
    ]


def test_a_previous_runs_copies_are_never_reprocessed(leaf: Path) -> None:
    """Copies live beside their originals, so the second run has to tell them
    apart — otherwise every run would square the number of files."""
    _write_photo(leaf / "SB_1220_Hrđava špilja_LKukuljan_1.jpg", (1920, 1440))
    sources = process_mod.source_photos(leaf, 1220)
    assert all(not p.name.startswith("SB_1220") for p in sources)
    assert len(sources) == 2


def test_a_foreign_sb_prefix_is_still_a_source(leaf: Path) -> None:
    """Only THIS cave's prefix means "already processed"; a photo carrying
    another cave's number is raw material that landed in the wrong place."""
    _write_photo(leaf / "SB_976_Billova ponikva_SClashin_1.jpg", (800, 600))
    assert any(p.name.startswith("SB_976") for p in process_mod.source_photos(leaf, 1220))


# ── writing ───────────────────────────────────────────────────────────


def test_processing_downsizes_the_copy_and_leaves_the_original_alone(leaf: Path) -> None:
    source = leaf / "IMG_20260530_130138.jpg"
    before = source.stat().st_size
    plan = process_mod.PhotoPlan(source=source, target=leaf / "out.jpg")

    outcome = process_mod.process_photo(plan, long_edge_px=1920, max_bytes=1_500_000)

    assert outcome.status == "written"
    assert outcome.target_px == (1920, 1440)
    assert outcome.target_bytes < before
    assert source.stat().st_size == before


def test_a_photo_smaller_than_the_target_is_never_upscaled(leaf: Path) -> None:
    source = _write_photo(leaf / "small.jpg", (800, 600))
    plan = process_mod.PhotoPlan(source=source, target=leaf / "small_out.jpg")

    outcome = process_mod.process_photo(plan, long_edge_px=1920, max_bytes=1_500_000)

    assert outcome.target_px == (800, 600)


def test_quality_drops_until_the_size_budget_is_met(leaf: Path) -> None:
    source = leaf / "IMG_20260530_130138.jpg"
    roomy = process_mod.process_photo(
        process_mod.PhotoPlan(source=source, target=leaf / "roomy.jpg"),
        long_edge_px=1920,
        max_bytes=50_000_000,
    )
    tight = process_mod.process_photo(
        process_mod.PhotoPlan(source=source, target=leaf / "tight.jpg"),
        long_edge_px=1920,
        max_bytes=roomy.target_bytes // 2,
    )

    assert tight.status == "written"
    # Same pixels, smaller file: the ladder really descended.
    assert tight.target_px == roomy.target_px
    assert tight.target_bytes < roomy.target_bytes


def test_a_copy_that_misses_the_budget_at_the_floor_is_still_written(leaf: Path) -> None:
    """Pure noise cannot reach 20 kB at quality 70. The documented choice is to
    keep the last rung: an honestly oversized copy (which the dossier gate
    already warns about) beats a mushy one or no file at all."""
    plan = process_mod.PhotoPlan(
        source=leaf / "IMG_20260530_130138.jpg", target=leaf / "floor.jpg"
    )

    outcome = process_mod.process_photo(plan, long_edge_px=1920, max_bytes=20_000)

    assert outcome.status == "written"
    assert outcome.target_bytes > 20_000


def test_an_existing_copy_is_skipped_unless_overwrite(leaf: Path) -> None:
    target = leaf / "existing.jpg"
    _write_photo(target, (100, 100))
    stamp = target.stat().st_size
    plan = process_mod.PhotoPlan(source=leaf / "IMG_20260530_130138.jpg", target=target)

    skipped = process_mod.process_photo(plan, long_edge_px=1920, max_bytes=1_500_000)
    assert skipped.status == "exists"
    assert target.stat().st_size == stamp

    rewritten = process_mod.process_photo(
        plan, long_edge_px=1920, max_bytes=1_500_000, overwrite=True
    )
    assert rewritten.status == "written"
    assert rewritten.target_px == (1920, 1440)


def test_a_heic_source_is_reported_not_silently_dropped(leaf: Path) -> None:
    source = leaf / "IMG_0001.heic"
    source.write_bytes(b"not really heic")
    plan = process_mod.PhotoPlan(source=source, target=leaf / "out.jpg", unsupported=True)

    outcome = process_mod.process_photo(plan, long_edge_px=1920, max_bytes=1_500_000)

    assert outcome.status == "unsupported"
    assert not plan.target.exists()


# ── the whole job ─────────────────────────────────────────────────────


def test_job_resolves_the_leaf_and_notes_the_missing_osz(drive_settings: Settings) -> None:
    job = process_mod.build_job(drive_settings, 1220, "Hrđava špilja")

    assert job.folder is not None and job.folder.name.startswith("SB_1220_")
    assert job.author is None
    assert any("Autor fotografije ulaza" in note or "OSZ" in note for note in job.notes)
    assert [p.target.name for p in job.plans] == [
        "SB_1220_Hrđava špilja_1.jpg",
        "SB_1220_Hrđava špilja_2.jpg",
    ]


def test_the_locators_reason_reaches_the_user(drive_settings: Settings, leaf: Path) -> None:
    """When the OSZ cannot be resolved, WHY must survive into the notes.

    Swallowing them (fixed 2026-09-01) reported a flat "no OSZ" for SB 1250,
    whose zapisnik was sitting in the leaf — the locator had rejected it as
    ambiguous and only its own note said so.
    """
    (leaf / "prva.docx").write_bytes(b"docx")
    (leaf / "druga.docx").write_bytes(b"docx")

    job = process_mod.build_job(drive_settings, 1220, "Hrđava špilja")

    assert job.author is None
    assert any("kandidata" in note for note in job.notes)


def test_author_override_skips_the_osz_entirely(drive_settings: Settings) -> None:
    job = process_mod.build_job(
        drive_settings, 1220, "Hrđava špilja", author_override="Lovel Kukuljan"
    )

    assert job.author == "LKukuljan"
    assert job.osz_path is None
    assert job.plans[0].target.name == "SB_1220_Hrđava špilja_LKukuljan_1.jpg"


def test_an_unresolvable_cave_folder_is_a_note_not_a_crash(
    drive_settings: Settings,
) -> None:
    job = process_mod.build_job(drive_settings, 4242, "Nepoznata")

    assert job.folder is None
    assert job.plans == ()
    assert any("SB_4242" in note for note in job.notes)


def test_process_job_writes_every_planned_copy(drive_settings: Settings, leaf: Path) -> None:
    job = process_mod.build_job(
        drive_settings, 1220, "Hrđava špilja", author_override="Lovel Kukuljan"
    )

    outcomes = process_mod.process_job(job, long_edge_px=1920, max_bytes=1_500_000)

    assert [o.status for o in outcomes] == ["written", "written"]
    assert sorted(p.name for p in leaf.glob("SB_1220_*")) == [
        "SB_1220_Hrđava špilja_LKukuljan_1.jpg",
        "SB_1220_Hrđava špilja_LKukuljan_2.jpg",
    ]
    # A second run finds nothing left to do — the copies are not their own input.
    assert process_mod.build_job(
        drive_settings, 1220, "Hrđava špilja", author_override="Lovel Kukuljan"
    ).plans == job.plans


def test_config_targets_are_what_the_command_aims_for(drive_settings: Settings) -> None:
    assert process_mod.resolve_targets(drive_settings) == (1920, 1_500_000)


def test_targets_fall_back_when_config_says_nothing(settings: Settings) -> None:
    assert process_mod.resolve_targets(replace(settings, photo_targets={})) == (
        process_mod.DEFAULT_LONG_EDGE_PX,
        process_mod.DEFAULT_MAX_BYTES,
    )
