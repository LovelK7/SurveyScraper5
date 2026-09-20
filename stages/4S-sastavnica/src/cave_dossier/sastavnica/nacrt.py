"""Orchestrator for ``cavedossier nacrt <Redni broj>`` — the cSurvey route's Nacrt.

Where ``prefill.py`` turns an SB row into a title block, this turns a cave that
has been through 3N's KORAK 3 into the finished sheet: the same title block,
prefilled from the **measured** survey, with the printed plan and profile
placed beside it at true scale.

    nacrt_finish.py + csurvey_driver.py   (3N, stdlib + cSurvey)
        -> <name>_plan.pdf, <name>_profile.pdf, <name>_dimenzije.json
    cavedossier nacrt <broj>              (here)
        -> SB_<padded>_nacrt.pdf in the cave's intake leaf

It reuses the sastavnica prefill for the page rather than re-deriving it, so
the two documents can never disagree about the same cave — with one switch
thrown: ``use_dimensions=True`` lets the KORAK 3 numbers outrank the zapisnik
for the three dimension cells and fills Mjerilo with the scale the designs were
actually printed at. Plain ``cavedossier sastavnica`` is untouched.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from cave_dossier import georef
from cave_dossier.core.config import Settings
from cave_dossier.sastavnica import addresses, compose as compose_mod
from cave_dossier.sastavnica.compose import ComposeError, Layout, NacrtInputs, Placement
from cave_dossier.sastavnica.models import NacrtResult, PlacedDrawing

# Its own stamp: a delivered nacrt and a delivered sastavnica are different
# documents, and neither may treat the other's file as its own to replace.
STAMP = "cave-dossier nacrt compose"

__all__ = ["ComposeError", "NacrtOutcome", "STAMP", "run_nacrt"]


@dataclass(frozen=True)
class NacrtOutcome:
    result: NacrtResult
    inputs: NacrtInputs
    layout: Layout
    placements: list[Placement]
    pdf_path: Path                # the run-dir copy (always exists on success)
    delivered_path: Path | None   # the Drive copy, when it could be written
    sidecar_path: Path


def run_nacrt(settings: Settings, serial: int, *, offline: bool = False,
              local_only: bool = False, force: bool = False) -> NacrtOutcome:
    from cave_dossier.sastavnica import prefill as prefill_mod

    folder = prefill_mod._intake_folder(settings, serial)
    if folder is None:
        raise ComposeError(
            f"Objekt {serial} nema intake mapu na Driveu (ili Drive nije "
            "dostupan) — tamo su KORAK 3 datoteke koje se slažu u nacrt.")
    inputs = compose_mod.find_inputs(folder)
    dims = compose_mod.read_dimensions(inputs.dimensions)
    layout = Layout.from_mapping(
        dims, pad_m=compose_mod.read_pad_m(inputs.layout_sidecar))

    # The title block, prefilled with the measured numbers. local_only: what we
    # want out of this run is the PAGE — the sastavnica is not a deliverable on
    # the cSurvey route, the composed nacrt is.
    sastavnica = prefill_mod.run_prefill(
        settings, serial, offline=offline, local_only=True,
        use_dimensions=True)
    page_result = sastavnica.result
    page_result.notes = [note for note in page_result.notes
                         if note != prefill_mod.LOCAL_SKIP_NOTE]

    placements = compose_mod.placements(inputs.plan, inputs.profile, layout)
    composed = compose_mod.compose_nacrt(
        sastavnica.pdf_path.read_bytes(), inputs.plan, inputs.profile, layout)
    composed = _stamp(composed, serial, page_result.cave_name)

    result = NacrtResult(
        serial=serial,
        cave_name=page_result.cave_name,
        sue_number=page_result.sue_number,
        sastavnica=page_result,
        inputs=[path.name for path in inputs.files],
        mjerilo=layout.mjerilo,
        arrangement=layout.arrangement,
        plan_scale=layout.plan_scale,
        profile_scale=layout.profile_scale,
        drawings=[_placed(item) for item in placements],
        notes=list(page_result.notes),
    )

    run_dir = prefill_mod.RUNS_DIR / georef.padded_serial(serial)
    run_dir.mkdir(parents=True, exist_ok=True)
    pdf_name = f"{prefill_mod._sb_prefix(serial)}_nacrt.pdf"
    pdf_path = run_dir / pdf_name
    pdf_path.write_bytes(composed)

    delivered_path = None
    if local_only:
        result.notes.append(prefill_mod.LOCAL_SKIP_NOTE)
    else:
        cave = georef.find_by_serial(prefill_mod.SBReader(settings), settings, serial)
        delivered_path = prefill_mod._deliver(
            settings, cave, serial, pdf_path, pdf_name, page_result,
            intake_folder=folder, force=force, stamp=STAMP)
        # _deliver writes its notes onto the sastavnica result; carry the new
        # ones across so the nacrt sidecar is the whole story of this run.
        result.notes = list(page_result.notes)

    sidecar_path = run_dir / "nacrt.json"
    sidecar_path.write_text(result.model_dump_json(indent=2), encoding="utf-8")

    return NacrtOutcome(result, inputs, layout, placements, pdf_path,
                        delivered_path, sidecar_path)


def _placed(item: Placement) -> PlacedDrawing:
    ink_w, ink_h = item.ink_mm
    res_w, res_h = item.reserved_mm
    return PlacedDrawing(
        design=item.design,
        source=item.source.name,
        scale=item.scale,
        ink_mm=[round(ink_w, 1), round(ink_h, 1)],
        reserved_mm=[round(res_w, 1), round(res_h, 1)],
        x_mm=round(item.target.x0 / compose_mod.MM, 1),
        y_mm=round(item.target.y0 / compose_mod.MM, 1),
    )


def _stamp(pdf_bytes: bytes, serial: int, cave_name: str) -> bytes:
    """Mark the delivered file as ours, the same mechanism `sastavnica` uses:
    an edit in any PDF editor replaces the producer, and a re-run then refuses
    to overwrite the edited file instead of destroying the work."""
    import pymupdf

    with pymupdf.open("pdf", pdf_bytes) as doc:
        doc.set_metadata({
            **(doc.metadata or {}),
            "title": f"Nacrt {georef.padded_serial(serial)}",
            "subject": cave_name,
            "creator": STAMP,
            "producer": f"{STAMP} ({addresses.TEMPLATE_VERSION})",
        })
        return doc.tobytes(garbage=4, deflate=True)
