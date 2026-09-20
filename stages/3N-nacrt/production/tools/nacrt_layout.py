#!/usr/bin/env python3
"""Pick the print scale of each design and arrange both on the 4S sastavnica page.

T4 of projects/0004-nacrt-finishing. cSurvey prints **one design per sheet**,
always centred, so the Nacrt is made by printing plan and profile separately at
a *fixed* scale and composing them onto the 4S sastavnica A4 (T3). This module
is the chooser in between: given the two bounding boxes in metres it answers
"which scale for each, and where on the page" — never by rescaling a drawing,
only by picking among SCALES.

The scale of a design is written into `_preview.plan` / `_preview.profile` as
`scalemode`, which is the print dialog's **combo index**, not a denominator:
1 = 1:100, 2 = 1:200, 3 = 1:250, 4 = 1:300, 5 = 1:500 (brief 2.1); 1:400 is not
on the dialog's list, so it is written as the custom entry: scalemode 99 plus
`scale="400"` (frmPreview.vb:694-700 restores it, :1160 prints with it).

The rules are the user's, 2026-09-20 (brief 3.4, amended the same day after
reviewing the drawn proposals): scale per design (profile 1:200 with plan 1:100
is the common case), profile primary, plan promoted to a larger scale when the
two bboxes differ drastically — but **never more than one rung of the ladder
apart** (user, 2026-09-20: 1:500 beside 1:250 is two rungs, since 1:300 and
1:400 sit between), so the reader switches scale at most once per sheet; gaps and margins respected;
semi-automatic — the tool proposes, the operator may pick an alternative from
the numbered menu.

Stdlib only, no imports from the rest of the repo, like its siblings in this
folder: it travels into the operator kit beside the tools that call it.

    python nacrt_layout.py <plan_w> <plan_h> <profile_w> <profile_h>   # metres
"""

from __future__ import annotations

import sys
from dataclasses import dataclass

# --- page geometry -------------------------------------------------------
#
# A4 portrait, the same page 4S renders the sastavnica on: 595.28 x 841.89 pt
# = 210 x 297 mm. The title block sits in the upper-left; its extent is the
# bounding rectangle of the fifteen cells listed in
# stages/4S-sastavnica/docs/sastavnica-design.md ("Cell geometry") — leftmost
# x0 39.85 (crtali / istrazili), topmost y0 49.58, rightmost x1 291.43,
# bottommost y1 149.94, all in PDF points with y growing downward, that is
# 251.58 x 100.36 pt. 1 pt = 25.4/72 mm.

PT_MM = 25.4 / 72.0

A4_PORTRAIT_MM = (210.0, 297.0)

_BLOCK_PT = (39.85, 49.58, 291.43, 149.94)  # x0, y0, x1, y1

# cSurvey scalemode = the print dialog's combo index (0 fit, 1 1:100, 2 1:200,
# 3 1:250, 4 1:300, 5 1:500, 6 1:1000, 99 custom + `scale`). 1:250 joined the
# ladder on the user's review of the drawn proposals, 2026-09-20: a 40 m
# profile misses 1:200 by 10 mm and dropping it straight to 1:300 gives away
# more than it must. 1:400 followed the same day; it has no combo entry, so it
# goes out as the custom scale (99) with `scale="400"`.
SCALES = (100, 200, 250, 300, 400, 500)
SCALEMODE = {100: 1, 200: 2, 250: 3, 300: 4, 400: 99, 500: 5}

# A drawing counts as "tall and narrow" above this aspect (height / width).
TALL_ASPECT = 1.3
# "Drastically different" bboxes: profile's larger dimension over the plan's.
DRASTIC_RATIO = 1.6
# How far apart the two designs' scales may be on one sheet: at most this many
# rungs of SCALES (user, 2026-09-20, twice: "one step apart in the ladder" —
# 1:200 with 1:100 yes, 1:500 with 1:250 no, because 1:300 and 1:400 lie between).
MAX_STEP = 1

_EPS = 1e-9
_ARRANGEMENTS = ("vertical", "side_by_side")
_HR = {"vertical": "okomito", "side_by_side": "jedno uz drugo"}


@dataclass(frozen=True)
class BBox:
    """A design's extent in metres, read off the survey XML. Origin is irrelevant."""

    width: float
    height: float

    @property
    def larger(self):
        return max(self.width, self.height)

    @property
    def aspect(self):
        return self.height / self.width


@dataclass(frozen=True)
class Placement:
    """A rectangle on the A4 page, millimetres, origin top-left."""

    x: float
    y: float
    width: float
    height: float

    @property
    def right(self):
        return self.x + self.width

    @property
    def bottom(self):
        return self.y + self.height

    def overlaps(self, other, tol=0.0):
        return (self.x < other.right - tol and other.x < self.right - tol
                and self.y < other.bottom - tol and other.y < self.bottom - tol)


TITLE_BLOCK_MM = Placement(
    x=round(_BLOCK_PT[0] * PT_MM, 2),
    y=round(_BLOCK_PT[1] * PT_MM, 2),
    width=round((_BLOCK_PT[2] - _BLOCK_PT[0]) * PT_MM, 2),
    height=round((_BLOCK_PT[3] - _BLOCK_PT[1]) * PT_MM, 2),
)


@dataclass(frozen=True)
class Layout:
    """One proposal: a scale per design plus where each one goes."""

    plan_scale: int
    profile_scale: int
    arrangement: str
    profile: Placement
    plan: Placement
    mjerilo: str
    note: str

    @property
    def scalemodes(self):
        """(profile, plan) as cSurvey `_preview.*` scalemode indices."""
        return SCALEMODE[self.profile_scale], SCALEMODE[self.plan_scale]

    @property
    def key(self):
        """What makes two proposals distinct in the operator's menu."""
        return (self.profile_scale, self.plan_scale, self.arrangement)


# --- the free area -------------------------------------------------------


@dataclass(frozen=True)
class _Free:
    """The one band the drawings may use: full page width, below the title block.

    The page also leaves a strip free to the right of the block, and an earlier
    version of this module would push a narrow pair up into it to buy a larger
    scale. The user rejected that sheet on sight, 2026-09-20 — half the page
    empty beside a column of drawing — so the strip stays unused and every
    drawing starts below the block. Nothing is ever placed left of the block
    either: only ~4 mm of page lives there.
    """

    left: float
    right: float
    top: float
    bottom: float
    gap: float

    @property
    def width(self):
        return self.right - self.left

    @property
    def height(self):
        return self.bottom - self.top


def _free_area(page, title_block, margin_mm, gap_mm):
    return _Free(
        left=margin_mm,
        right=page[0] - margin_mm,
        top=title_block.bottom + gap_mm,
        bottom=page[1] - margin_mm,
        gap=gap_mm,
    )


# --- placement -----------------------------------------------------------


def _size_mm(bbox, scale):
    """A bbox in metres at 1:<scale>, in millimetres on the page."""
    return bbox.width * 1000.0 / scale, bbox.height * 1000.0 / scale


def _centred(free, w, h, y):
    """Centre a w x h rectangle horizontally in the band, or None if it spills."""
    if w > free.width + _EPS or y + h > free.bottom + _EPS:
        return None
    return Placement(round(free.left + (free.width - w) / 2.0, 1), round(y, 1),
                     round(w, 1), round(h, 1))


def _arrange(arrangement, prof_mm, plan_mm, free):
    """Place both drawings in the band, or None when they do not fit.

    The profile's top edge is the top of the band either way: packed to the top,
    so the leftover page collects at the bottom of the sheet where it reads as
    margin rather than as a hole (user, 2026-09-20).
    """
    pw, ph = prof_mm
    lw, lh = plan_mm
    if arrangement == "vertical":
        profile = _centred(free, pw, ph, free.top)
        if profile is None:
            return None
        plan = _centred(free, lw, lh, free.top + ph + free.gap)
        if plan is None:
            return None
        return profile, plan
    total = pw + free.gap + lw
    if total > free.width + _EPS or free.top + max(ph, lh) > free.bottom + _EPS:
        return None
    x = free.left + (free.width - total) / 2.0
    return (Placement(round(x, 1), round(free.top, 1), round(pw, 1), round(ph, 1)),
            Placement(round(x + pw + free.gap, 1), round(free.top, 1),
                      round(lw, 1), round(lh, 1)))


def _waste(profile, plan):
    """Empty square millimetres inside the footprint the two drawings occupy."""
    footprint = ((max(profile.right, plan.right) - min(profile.x, plan.x))
                 * (max(profile.bottom, plan.bottom) - min(profile.y, plan.y)))
    return footprint - profile.width * profile.height - plan.width * plan.height


def mjerilo(profile_scale, plan_scale):
    """The Mjerilo cell of the sastavnica (4S), brief 3.4."""
    if profile_scale == plan_scale:
        return "1:%d" % plan_scale
    return "profil/tlocrt: 1:%d/1:%d" % (profile_scale, plan_scale)


def _note(arrangement, profile_scale, plan_scale, profile, plan):
    """One line an operator reads in the console menu."""
    where = ("gore", "dolje") if arrangement == "vertical" else ("lijevo", "desno")
    return ("%s: profil 1:%d (%.0fx%.0f mm) %s, tlocrt 1:%d (%.0fx%.0f mm) %s"
            % (_HR[arrangement], profile_scale, profile.width, profile.height,
               where[0], plan_scale, plan.width, plan.height, where[1]))


def _no_fit_reason(plan, profile, free):
    pw, ph = _size_mm(profile, 500)
    lw, lh = _size_mm(plan, 500)
    return ("ni pri 1:500 ne stane na A4: profil %.0fx%.0f mm, tlocrt %.0fx%.0f mm, "
            "slobodno %.0fx%.0f mm" % (pw, ph, lw, lh, free.width, free.height))


# --- the chooser ---------------------------------------------------------


def choose_layout(plan, profile, *, page=A4_PORTRAIT_MM, title_block=TITLE_BLOCK_MM,
                  margin_mm=10.0, gap_mm=10.0, max_alternatives=3):
    """Return (best, ranked alternatives, reason_when_none).

    `best` is None only when nothing fits even at 1:500; `reason` is then one
    line naming the 1:500 sizes, and the caller falls back to cSurvey's own
    fit-to-page (`scalemode="0"`) with a warning.
    """
    for name, bbox in (("plan", plan), ("profile", profile)):
        if bbox.width <= 0 or bbox.height <= 0:
            raise ValueError("%s bbox must be positive, got %r" % (name, bbox))

    free = _free_area(page, title_block, margin_mm, gap_mm)

    # Vertical is the default arrangement (profile primary, on top). Side by
    # side only competes on equal terms when *both* drawings are tall and
    # narrow; even then vertical wins a tie, so it takes a real advantage —
    # a larger scale for one of the designs — to put them next to each other.
    both_tall = profile.aspect > TALL_ASPECT and plan.aspect > TALL_ASPECT
    # Drastically different bboxes -> the plan wants the larger scale, so that a
    # small plan does not get dragged down to the scale a long profile needs.
    drastic = profile.larger > DRASTIC_RATIO * plan.larger

    ranked = []
    for profile_scale in SCALES:
        prof_mm = _size_mm(profile, profile_scale)
        for plan_scale in SCALES:
            # One sheet, at most MAX_STEP rungs between the two scales.
            if abs(SCALES.index(profile_scale) - SCALES.index(plan_scale)) > MAX_STEP:
                continue
            plan_mm = _size_mm(plan, plan_scale)
            for arrangement in _ARRANGEMENTS:
                placed = _arrange(arrangement, prof_mm, plan_mm, free)
                if placed is None:
                    continue
                profile_at, plan_at = placed
                layout = Layout(
                    plan_scale=plan_scale,
                    profile_scale=profile_scale,
                    arrangement=arrangement,
                    profile=profile_at,
                    plan=plan_at,
                    mjerilo=mjerilo(profile_scale, plan_scale),
                    note=_note(arrangement, profile_scale, plan_scale,
                               profile_at, plan_at),
                )
                pi = SCALES.index(profile_scale)
                li = SCALES.index(plan_scale)
                ranked.append(((
                    pi + li,                                # largest scales first
                    0 if (not drastic or li < pi) else 1,   # plan promoted a step
                    pi,                                     # profile is the primary design
                    0 if (arrangement == "vertical" or both_tall) else 1,
                    round(_waste(profile_at, plan_at), 1),  # least empty page
                    _ARRANGEMENTS.index(arrangement),       # ties go to vertical
                ), layout))

    if not ranked:
        return None, [], _no_fit_reason(plan, profile, free)

    ranked.sort(key=lambda pair: pair[0])
    best = ranked[0][1]
    seen = {best.key}
    alternatives = []
    for _, layout in ranked[1:]:
        if layout.key in seen or _dominated(layout, ranked):
            continue
        seen.add(layout.key)
        alternatives.append(layout)
        if len(alternatives) >= max_alternatives:
            break
    return best, alternatives, ""


def _dominated(layout, ranked):
    """True when another candidate in the same arrangement has both scales at
    least as large and one strictly larger — a pointless downscale that only
    clutters the operator's menu (user, 2026-09-20: "way too many options which
    do not make sense"). What survives is one entry per arrangement per real
    trade-off: equal scales vs. a promoted plan, stacked vs. side by side."""
    pi, li = SCALES.index(layout.profile_scale), SCALES.index(layout.plan_scale)
    for _, other in ranked:
        if other.arrangement != layout.arrangement:
            continue
        oi, ol = SCALES.index(other.profile_scale), SCALES.index(other.plan_scale)
        if oi <= pi and ol <= li and (oi, ol) != (pi, li):
            return True
    return False


# --- tiny CLI ------------------------------------------------------------


def _describe(layout):
    return "%s  |  %s" % (layout.mjerilo, layout.note)


def main(argv):
    if len(argv) != 4:
        print("python nacrt_layout.py <plan_w> <plan_h> <profile_w> <profile_h>   (metri)")
        return 2
    try:
        plan_w, plan_h, prof_w, prof_h = (float(a.replace(",", ".")) for a in argv)
    except ValueError:
        print("ERROR: sve cetiri mjere moraju biti brojevi (metri).")
        return 2

    best, alternatives, reason = choose_layout(BBox(plan_w, plan_h),
                                               BBox(prof_w, prof_h))

    print("Tlocrt %.1f x %.1f m, profil %.1f x %.1f m  -  A4 portret, sastavnica gore lijevo"
          % (plan_w, plan_h, prof_w, prof_h))
    if best is None:
        print("  %s" % reason)
        print("  -> cSurvey fit-to-page (scalemode=0), mjerilo upisi rucno.")
        return 1

    print()
    print("  1) %s   <- prijedlog" % _describe(best))
    for i, layout in enumerate(alternatives, 2):
        print("  %d) %s" % (i, _describe(layout)))
    print()
    print("  mjerilo: %s   scalemode: profil=%d tlocrt=%d"
          % ((best.mjerilo,) + best.scalemodes))
    print("  profil  x=%.1f y=%.1f  %.1f x %.1f mm"
          % (best.profile.x, best.profile.y, best.profile.width, best.profile.height))
    print("  tlocrt  x=%.1f y=%.1f  %.1f x %.1f mm"
          % (best.plan.x, best.plan.y, best.plan.width, best.plan.height))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
