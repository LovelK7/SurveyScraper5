"""Compose the cSurvey Nacrt: plan + profile onto the sastavnica page.

``cavedossier nacrt <Redni broj>`` — the last step of the cSurvey route
(3N-nacrt KORAK 3). cSurvey prints **one design per sheet** and always centres
it, so the Nacrt is made by printing plan and profile separately at a *fixed*
scale and placing both onto one A4 that already carries the title block.

The composition lives here, in the 4S package, and not in the 3N tools: 4S
already owns this page, the font, PyMuPDF and the delivery convention. The 3N
tools stay stdlib and only *produce* the inputs —

    nacrt_finish.py   the corrected survey -> _lt_fin.csx + a layout sidecar
    csurvey_driver.py -> <name>_plan.pdf, <name>_profile.pdf, <name>_dimenzije.json
    this module       -> SB_<padded>_nacrt.pdf in the cave's intake leaf

**Nothing is ever rescaled.** Each source page was printed at a true 1:100 /
1:200 / … and the whole point of the fixed scale is that a 5 m scale bar
measures 50 mm on the delivered sheet. So each drawing is placed by cropping
its page to the ink and dropping that crop, at its own size, centred on the
rectangle `nacrt_layout.choose_layout()` reserved for it. When the ink does not
fit that rectangle, or would cross the title block, the margin or the other
drawing, this module **refuses** rather than shrinking: the operator re-runs the
finisher with another layout (`nacrt_finish.py --layout N`).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from cave_dossier.sastavnica.addresses import BLOCK

MM = 72.0 / 25.4          # millimetres -> PDF points
A4_PORTRAIT_PT = (595.28, 841.89)
PAGE_MARGIN_MM = 10.0
# What nacrt_finish.py pads each design bbox by, when the sidecar does not say.
DEFAULT_PAD_M = 0.5

DESIGNS = ("profile", "plan")     # the profile is the primary drawing


class ComposeError(RuntimeError):
    """The page could not be composed; message is CLI-ready."""


@dataclass(frozen=True)
class Rect:
    """A rectangle in PDF points, origin top-left — PyMuPDF's own convention."""

    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def width(self) -> float:
        return self.x1 - self.x0

    @property
    def height(self) -> float:
        return self.y1 - self.y0

    @property
    def centre(self) -> tuple[float, float]:
        return ((self.x0 + self.x1) / 2, (self.y0 + self.y1) / 2)

    def intersects(self, other: "Rect", tol: float = 0.0) -> bool:
        return (self.x0 < other.x1 - tol and other.x0 < self.x1 - tol
                and self.y0 < other.y1 - tol and other.y0 < self.y1 - tol)

    def mm(self) -> tuple[float, float]:
        return self.width / MM, self.height / MM

    @classmethod
    def from_mm(cls, x: float, y: float, width: float, height: float) -> "Rect":
        return cls(x * MM, y * MM, (x + width) * MM, (y + height) * MM)

    @classmethod
    def centred(cls, centre: tuple[float, float], width: float,
                height: float) -> "Rect":
        cx, cy = centre
        return cls(cx - width / 2, cy - height / 2, cx + width / 2, cy + height / 2)


@dataclass(frozen=True)
class Placement:
    """One drawing: where its ink is, and where it goes."""

    design: str            # "plan" | "profile"
    source: Path
    scale: int             # the denominator it was printed at
    ink: Rect              # the crop taken out of the source page
    reserved: Rect         # what the layout kept free for it
    target: Rect           # where the crop lands, same size as `ink`

    @property
    def ink_mm(self) -> tuple[float, float]:
        return self.ink.mm()

    @property
    def reserved_mm(self) -> tuple[float, float]:
        return self.reserved.mm()


@dataclass(frozen=True)
class Layout:
    """The placement half of ``<name>_dimenzije.json`` (T1 via T2)."""

    plan: Rect
    profile: Rect
    plan_scale: int
    profile_scale: int
    arrangement: str
    mjerilo: str
    pad_m: float = DEFAULT_PAD_M

    def rect(self, design: str) -> Rect:
        return self.plan if design == "plan" else self.profile

    def scale(self, design: str) -> int:
        return self.plan_scale if design == "plan" else self.profile_scale

    @property
    def scales_differ(self) -> bool:
        return self.plan_scale != self.profile_scale

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any], *,
                     pad_m: float | None = None) -> "Layout":
        """Build from the dimensions JSON, naming precisely what is missing."""
        missing = [key for key in ("plan_mm", "profile_mm", "plan_scale",
                                   "profile_scale")
                   if not data.get(key)]
        if missing:
            raise ComposeError(
                "Dimenzije JSON ne sadrži raspored (%s) — nacrt_finish.py je "
                "vjerojatno završio s 'fit-to-page' (ništa ne stane na A4) ili "
                "je datoteka od starije verzije. Pokreni KORAK 3 ponovno."
                % ", ".join(missing))
        return cls(
            plan=_rect_from_mm(data["plan_mm"], "plan_mm"),
            profile=_rect_from_mm(data["profile_mm"], "profile_mm"),
            plan_scale=int(data["plan_scale"]),
            profile_scale=int(data["profile_scale"]),
            arrangement=str(data.get("arrangement") or "vertical"),
            mjerilo=str(data.get("mjerilo") or ""),
            pad_m=float(pad_m if pad_m is not None
                        else data.get("pad_m", DEFAULT_PAD_M)),
        )


def _rect_from_mm(box: Mapping[str, Any], label: str) -> Rect:
    try:
        return Rect.from_mm(float(box["x"]), float(box["y"]),
                            float(box["width"]), float(box["height"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise ComposeError(f"{label} nije {{x, y, width, height}}: {box!r}") from exc


# ── the inputs in the cave's intake leaf ─────────────────────────────

SUFFIXES = {"plan": "_plan.pdf", "profile": "_profile.pdf",
            "dimensions": "_dimenzije.json"}


@dataclass(frozen=True)
class NacrtInputs:
    """The trio KORAK 3 leaves in the leaf, plus the finisher's own sidecar."""

    stem: str
    plan: Path
    profile: Path
    dimensions: Path
    layout_sidecar: Path | None      # <survey>_lt_fin.layout.json, when present

    @property
    def files(self) -> list[Path]:
        return [self.plan, self.profile, self.dimensions]


def find_inputs(folder: Path) -> NacrtInputs:
    """The newest complete `<stem>_{plan,profile}.pdf` + `<stem>_dimenzije.json`.

    Matched by stem rather than by newest-of-each, so a leaf that has been
    through KORAK 3 twice under different survey names can never be composed
    from a plan of one run and a profile of another.
    """
    if folder is None or not Path(folder).is_dir():
        raise ComposeError(f"Intake mapa objekta nije dostupna: {folder}")
    folder = Path(folder)
    found: dict[str, dict[str, Path]] = {}
    for kind, suffix in SUFFIXES.items():
        for path in folder.glob("*" + suffix):
            found.setdefault(path.name[: -len(suffix)], {})[kind] = path

    complete = [(stem, trio) for stem, trio in found.items()
                if len(trio) == len(SUFFIXES)]
    if not complete:
        have = sorted({kind for trio in found.values() for kind in trio})
        raise ComposeError(
            "U mapi %s nema kompletnog KORAKA 3 (%s). Treba: <ime>_plan.pdf, "
            "<ime>_profile.pdf, <ime>_dimenzije.json — napravi ih s "
            "nacrt_finish.py pa csurvey_driver.py finish."
            % (folder.name, "nađeno: " + ", ".join(have) if have else "mapa je prazna"))
    complete.sort(key=lambda pair: max(p.stat().st_mtime for p in pair[1].values()),
                  reverse=True)
    stem, trio = complete[0]
    return NacrtInputs(stem=stem, plan=trio["plan"], profile=trio["profile"],
                       dimensions=trio["dimensions"],
                       layout_sidecar=_layout_sidecar(folder))


def _layout_sidecar(folder: Path) -> Path | None:
    """nacrt_finish.py's own sidecar. Optional: everything the composition
    needs is merged into the dimensions JSON, except `pad_m` on files written
    before that key travelled — this is where it is recovered."""
    candidates = sorted(folder.glob("*.layout.json"),
                        key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0] if candidates else None


# ── ink ──────────────────────────────────────────────────────────────

def ink_bbox(page) -> Rect:
    """The bbox of everything drawn on a printed design page.

    Union of the vector paths and any text blocks. The pages cSurvey prints for
    us carry nothing else — the finisher turns the page-corner scale/compass/box
    gadgets off, so there is no furniture to exclude and no white background
    rectangle to trip over. Station labels come out of "Microsoft Print to PDF"
    as paths rather than text, which is why the text half is a safety net and
    not the main event.
    """
    boxes = [d["rect"] for d in page.get_drawings()]
    for block in page.get_text("dict")["blocks"]:
        boxes.append(block["bbox"])
    if not boxes:
        raise ComposeError("Stranica je prazna — nema što složiti.")
    page_rect = page.rect
    x0 = max(min(float(b[0]) for b in boxes), page_rect.x0)
    y0 = max(min(float(b[1]) for b in boxes), page_rect.y0)
    x1 = min(max(float(b[2]) for b in boxes), page_rect.x1)
    y1 = min(max(float(b[3]) for b in boxes), page_rect.y1)
    if x1 <= x0 or y1 <= y0:
        raise ComposeError("Nacrtani sadržaj nema upotrebljive dimenzije.")
    return Rect(x0, y0, x1, y1)


# ── placing ──────────────────────────────────────────────────────────

def _title_block() -> Rect:
    return Rect(*BLOCK)


def _page_box(page_pt: tuple[float, float]) -> Rect:
    margin = PAGE_MARGIN_MM * MM
    return Rect(margin, margin, page_pt[0] - margin, page_pt[1] - margin)


def placements(plan_pdf: Path, profile_pdf: Path, layout: Layout, *,
               gap_mm: float = 10.0,
               page_pt: tuple[float, float] = A4_PORTRAIT_PT) -> list[Placement]:
    """Where each drawing's ink goes, or a ComposeError naming the millimetres.

    The reserved rectangle was computed for the *padded* bbox, so it is a few
    millimetres larger than the ink; centring the ink inside it is what keeps
    T4's gaps honest. The tolerance is exactly that padding — an ink bigger than
    its rectangle by more than the padding means the printed page is not the one
    the layout was chosen for.
    """
    pymupdf = _pymupdf()
    placed: list[Placement] = []
    for design, source in (("profile", profile_pdf), ("plan", plan_pdf)):
        if not Path(source).exists():
            raise ComposeError(f"Nema datoteke: {source}")
        with pymupdf.open(source) as doc:
            if doc.page_count < 1:
                raise ComposeError(f"{Path(source).name} nema nijednu stranicu.")
            ink = ink_bbox(doc[0])
        reserved = layout.rect(design)
        target = Rect.centred(reserved.centre, ink.width, ink.height)
        placed.append(Placement(design=design, source=Path(source),
                                scale=layout.scale(design), ink=ink,
                                reserved=reserved, target=target))

    _check(placed, layout, gap_mm=gap_mm, page_pt=page_pt)
    return placed


def _check(placed: list[Placement], layout: Layout, *, gap_mm: float,
           page_pt: tuple[float, float]) -> None:
    """Refuse, with numbers, rather than fudge the scale (brief §3.4)."""
    page_box, block = _page_box(page_pt), _title_block()
    for item in placed:
        # Tolerance: how much bigger than its reserved rectangle an ink may be.
        # The rectangle already carries pad_m on every side, so the slack is
        # that padding converted to millimetres at this design's scale.
        slack_mm = layout.pad_m * 1000.0 / item.scale
        ink_w, ink_h = item.ink_mm
        res_w, res_h = item.reserved_mm
        if ink_w - res_w > slack_mm or ink_h - res_h > slack_mm:
            raise ComposeError(
                "%s: nacrtano %.1f x %.1f mm, a raspored je rezervirao "
                "%.1f x %.1f mm (dopušteno odstupanje %.1f mm). Ne smanjujem "
                "crtež — mjerilo 1:%d mora ostati vjerno. Pokreni nacrt_finish.py "
                "ponovno i izaberi drugi raspored (--layout N)."
                % (_HR[item.design], ink_w, ink_h, res_w, res_h, slack_mm,
                   item.scale))
        if not _inside(item.target, page_box):
            raise ComposeError(
                "%s bi izašao izvan margina stranice (%.1f x %.1f mm na "
                "x=%.1f y=%.1f mm). Izaberi drugi raspored (--layout N)."
                % (_HR[item.design], ink_w, ink_h,
                   item.target.x0 / MM, item.target.y0 / MM))
        if item.target.intersects(block, tol=0.5):
            raise ComposeError(
                "%s bi prekrio sastavnicu. Izaberi drugi raspored (--layout N)."
                % _HR[item.design])
    first, second = placed[0], placed[1]
    if first.target.intersects(second.target, tol=0.5):
        raise ComposeError(
            "Profil i tlocrt se preklapaju na stranici (razmak bi trebao biti "
            "najmanje %.0f mm). Izaberi drugi raspored (--layout N)." % gap_mm)


_HR = {"plan": "Tlocrt", "profile": "Profil"}


def _inside(inner: Rect, outer: Rect, tol: float = 0.5) -> bool:
    return (inner.x0 >= outer.x0 - tol and inner.y0 >= outer.y0 - tol
            and inner.x1 <= outer.x1 + tol and inner.y1 <= outer.y1 + tol)


def compose_nacrt(sastavnica_pdf_bytes: bytes, plan_pdf: Path, profile_pdf: Path,
                  layout: Layout, *, gap_mm: float = 10.0) -> bytes:
    """The sastavnica page with both drawings dropped onto it, at true scale."""
    pymupdf = _pymupdf()
    with pymupdf.open("pdf", sastavnica_pdf_bytes) as page_doc:
        page = page_doc[0]
        placed = placements(plan_pdf, profile_pdf, layout, gap_mm=gap_mm,
                            page_pt=(page.rect.width, page.rect.height))
        for item in placed:
            with pymupdf.open(item.source) as src:
                # target and clip are the same size, so the transform is a pure
                # translation: 50 mm of drawing stays 50 mm of paper.
                page.show_pdf_page(
                    pymupdf.Rect(item.target.x0, item.target.y0,
                                 item.target.x1, item.target.y1),
                    src, 0,
                    clip=pymupdf.Rect(item.ink.x0, item.ink.y0,
                                      item.ink.x1, item.ink.y1),
                )
        # The sastavnica's fonts travel into this document; keep their hyphens
        # plain (render.plain_hyphens_and_spaces) — Illustrator hides U+00AD.
        from cave_dossier.sastavnica.render import plain_hyphens_and_spaces
        plain_hyphens_and_spaces(page_doc)
        return page_doc.tobytes(garbage=4, deflate=True)


def _pymupdf():
    try:
        import pymupdf
    except ImportError as exc:  # pragma: no cover - dependency guard
        raise ComposeError(
            "PyMuPDF is required for the nacrt: pip install -e .[sastavnica]"
        ) from exc
    return pymupdf


# ── the values the dimensions JSON contributes to the title block ────

# `mjerilo` supersedes 4S decision 3 ("the stub 1: stays") for the cSurvey
# route only — the Illustrator route never has a dimensions JSON and keeps it.
DIMENSION_FIELDS = ("stvarna_duljina", "tlocrtna_duljina", "dubina", "mjerilo")


def read_dimensions(path: Path) -> dict[str, Any]:
    import json

    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError) as exc:
        raise ComposeError(f"Ne mogu pročitati {Path(path).name}: {exc}") from exc
    if not isinstance(data, dict):
        raise ComposeError(f"{Path(path).name} nije JSON objekt.")
    return data


def read_pad_m(sidecar: Path | None) -> float | None:
    """`pad_m` out of nacrt_finish.py's sidecar, for a dimensions JSON that
    predates that key travelling across."""
    if sidecar is None:
        return None
    try:
        import json

        with open(sidecar, encoding="utf-8") as handle:
            value = json.load(handle).get("pad_m")
        return float(value) if value is not None else None
    except (OSError, ValueError, TypeError):
        return None
