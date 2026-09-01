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
from cave_dossier.sb.loader import CaveRow


def _cave(serial: int, name: str) -> CaveRow:
    """A minimal SB row — enough for the intake-folder naming."""
    return CaveRow(row_number=serial, object_name=name, sue_number=None,
                   values={"Redni broj": serial, "Ime objekta": name})

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
def queue(tmp_path: Path) -> Path:
    """The `…za istražit` staging folder, named as the 2026-08-28 sweep left it."""
    folder = tmp_path / "!!Fotografije ulaza" / "!!Fotografije ulaza za istražit"
    folder.mkdir(parents=True)
    return folder


@pytest.fixture()
def drive_settings(settings: Settings, leaf: Path, queue: Path) -> Settings:
    """Settings whose intake dir is the synthetic drive root."""
    return replace(
        settings,
        local_drive_root=leaf.parent.parent,
        archive_dirs={
            "intake_dir": "!Za digitalizirat",
            "queued_photos_dir": "!!Fotografije ulaza/!!Fotografije ulaza za istražit",
        },
        photo_targets={"target_long_edge_px": 1920, "target_max_bytes": 1_500_000},
        photo_ignore_names=["STATS.png"],
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
    plans, _ = process_mod.plan_photos(leaf, 1220, "Hrđava špilja", "LKukuljan")
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
    sources, _ = process_mod.source_photos(leaf, 1220)
    assert all(not p.name.startswith("SB_1220") for p in sources)
    assert len(sources) == 2


def test_a_foreign_sb_prefix_is_still_a_source(leaf: Path) -> None:
    """Only THIS cave's prefix means "already processed"; a photo carrying
    another cave's number is raw material that landed in the wrong place."""
    _write_photo(leaf / "SB_976_Billova ponikva_SClashin_1.jpg", (800, 600))
    sources, _ = process_mod.source_photos(leaf, 1220)
    assert any(p.name.startswith("SB_976") for p in sources)


def test_stats_screenshots_are_skipped_and_reported(leaf: Path) -> None:
    """`STATS.png` is the cSurvey stats screenshot, not an entrance photo, and
    it recurs leaf after leaf (user, 2026-09-01). It is taken out BEFORE the
    numbering, so its presence never shifts a photo's index — and it is
    returned, not dropped, so the run can say it was skipped."""
    _write_photo(leaf / "STATS.png", (900, 700))

    plans, ignored = process_mod.plan_photos(
        leaf, 1220, "Hrđava špilja", "LKukuljan", ["STATS.png"]
    )

    assert [p.name for p in ignored] == ["STATS.png"]
    assert [p.target.name for p in plans] == [
        "SB_1220_Hrđava špilja_LKukuljan_1.jpg",
        "SB_1220_Hrđava špilja_LKukuljan_2.jpg",
    ]


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("STATS.png", True),
        ("stats.png", True),          # matched case-insensitively
        ("STATS (1).png", True),      # the copies Windows makes
        ("statistika.png", False),
        ("304 ulaz.jpg", False),
    ],
)
def test_the_ignore_list_takes_patterns(name: str, expected: bool) -> None:
    assert process_mod.is_ignored(name, ["STATS*.png"]) is expected


def test_nothing_is_ignored_without_a_list(leaf: Path) -> None:
    _write_photo(leaf / "STATS.png", (900, 700))
    photos, ignored = process_mod.source_photos(leaf, 1220)
    assert ignored == []
    assert len(photos) == 3


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


def test_a_jpeg_that_needs_nothing_is_copied_byte_for_byte(leaf: Path) -> None:
    """Re-encoding an already-small, already-compressed JPEG is pure loss — and
    on a phone photo it GREW the file (0.25 → 0.35 MB, SB 1250, 2026-09-01)."""
    source = _write_photo(leaf / "already fine.jpg", (1200, 900))
    plan = process_mod.PhotoPlan(source=source, target=leaf / "copied.jpg")

    outcome = process_mod.process_photo(plan, long_edge_px=1920, max_bytes=50_000_000)

    assert outcome.status == "written"
    assert outcome.target_bytes == outcome.source_bytes
    assert plan.target.read_bytes() == source.read_bytes()


def test_an_oversized_jpeg_within_the_pixel_target_is_still_recompressed(
    leaf: Path,
) -> None:
    """Small enough in pixels but over the size budget: the ladder must run."""
    source = _write_photo(leaf / "heavy.jpg", (1200, 900))
    plan = process_mod.PhotoPlan(source=source, target=leaf / "heavy_out.jpg")

    outcome = process_mod.process_photo(plan, long_edge_px=1920, max_bytes=100_000)

    assert outcome.target_bytes < outcome.source_bytes
    assert outcome.target_px == (1200, 900)


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


def test_the_job_carries_the_configured_ignore_list(
    drive_settings: Settings, leaf: Path
) -> None:
    _write_photo(leaf / "STATS.png", (900, 700))

    job = process_mod.build_job(
        drive_settings, 1220, "Hrđava špilja", author_override="Lovel Kukuljan"
    )

    assert [p.name for p in job.ignored] == ["STATS.png"]
    assert len(job.plans) == 2


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


# ── the staging queue → the intake leaf ───────────────────────────────


def test_staged_photos_are_found_by_their_sb_prefix(
    drive_settings: Settings, queue: Path
) -> None:
    _write_photo(queue / "SB_1220_Hrđava špilja_ulaz.jpg", (900, 700))
    _write_photo(queue / "SB_976_Billova ponikva_ulaz.jpg", (900, 700))

    found = process_mod.staged_for_cave(drive_settings, 1220)

    assert [p.name for p in found] == ["SB_1220_Hrđava špilja_ulaz.jpg"]


def test_a_run_reports_the_queued_photos_it_cannot_see(
    drive_settings: Settings, queue: Path
) -> None:
    """The leaf alone cannot tell you a cave's photos are still queued — which
    is how a cave gets processed with half its photos missing (SB 811)."""
    _write_photo(queue / "SB_1220_Hrđava špilja_ulaz.jpg", (900, 700))

    job = process_mod.build_job(drive_settings, 1220, "Hrđava špilja")

    assert [p.name for p in job.staged] == ["SB_1220_Hrđava špilja_ulaz.jpg"]


def test_the_queue_is_scanned_even_when_the_cave_has_no_leaf(
    drive_settings: Settings, queue: Path
) -> None:
    """No leaf is usually *why* the photos are still queued, so that exit needs
    the hint most of all."""
    _write_photo(queue / "SB_4242_Nepoznata_ulaz.jpg", (900, 700))

    job = process_mod.build_job(drive_settings, 4242, "Nepoznata")

    assert job.folder is None
    assert [p.name for p in job.staged] == ["SB_4242_Nepoznata_ulaz.jpg"]


@pytest.mark.parametrize(
    ("staged", "expected"),
    [
        ("SB_811_Possibile Grotta_13 ulaz.jpg", "Possibile Grotta_13 ulaz.jpg"),
        ("SB_0811_Possibile Grotta.jpg", "Possibile Grotta.jpg"),
        ("SB_811.jpg", "SB_811.jpg"),  # nothing would be left — keep the name
    ],
)
def test_the_sb_prefix_is_dropped_on_the_way_in(staged: str, expected: str) -> None:
    assert process_mod.strip_sb_prefix(staged, 811) == expected


def test_a_pulled_photo_is_visible_to_the_processor(
    drive_settings: Settings, leaf: Path, queue: Path
) -> None:
    """The prefix MUST go: `source_photos` reads `SB_<broj>_` as its own output,
    so a pulled photo would otherwise be invisible to the next process run."""
    _write_photo(queue / "SB_1220_Hrđava špilja_ulaz.jpg", (900, 700))
    cave = _cave(1220, "Hrđava špilja")

    process_mod.apply_pull(process_mod.plan_pull(drive_settings, cave, 1220))

    photos, _ = process_mod.source_photos(leaf, 1220)
    assert "Hrđava špilja_ulaz.jpg" in [p.name for p in photos]


def test_pulling_moves_rather_than_copies(
    drive_settings: Settings, leaf: Path, queue: Path
) -> None:
    """The queue is a staging area, not a repository (design decision C3)."""
    source = _write_photo(queue / "SB_1220_Hrđava špilja_ulaz.jpg", (900, 700))

    outcomes = process_mod.apply_pull(
        process_mod.plan_pull(drive_settings, _cave(1220, "Hrđava špilja"), 1220)
    )

    assert [o.status for o in outcomes] == ["moved"]
    assert not source.exists()
    assert (leaf / "Hrđava špilja_ulaz.jpg").exists()


def test_pulling_creates_the_leaf_when_the_cave_has_none(
    drive_settings: Settings, queue: Path
) -> None:
    """A queued cave routinely has no intake folder yet — that is precisely why
    its photos are still queued."""
    _write_photo(queue / "SB_4242_Nova jama_ulaz.jpg", (900, 700))
    plan = process_mod.plan_pull(drive_settings, _cave(4242, "Nova jama"), 4242)

    assert not plan.folder_exists
    assert plan.folder.name.startswith("SB_4242_")
    assert any("stvorena" in note for note in plan.notes)

    outcomes = process_mod.apply_pull(plan)
    assert [o.status for o in outcomes] == ["moved"]
    assert (plan.folder / "Nova jama_ulaz.jpg").exists()


def test_pulling_never_overwrites_an_existing_file(
    drive_settings: Settings, leaf: Path, queue: Path
) -> None:
    _write_photo(queue / "SB_1220_Hrđava špilja_ulaz.jpg", (900, 700))
    kept = _write_photo(leaf / "Hrđava špilja_ulaz.jpg", (100, 100))
    stamp = kept.stat().st_size

    outcomes = process_mod.apply_pull(
        process_mod.plan_pull(drive_settings, _cave(1220, "Hrđava špilja"), 1220)
    )

    assert [o.status for o in outcomes] == ["exists"]
    assert kept.stat().st_size == stamp
    assert (queue / "SB_1220_Hrđava špilja_ulaz.jpg").exists()  # left in the queue


def test_an_empty_queue_plans_nothing(drive_settings: Settings) -> None:
    plan = process_mod.plan_pull(drive_settings, _cave(1220, "Hrđava špilja"), 1220)
    assert plan.moves == ()
