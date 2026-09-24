"""nacrt_layout — the scale + page-arrangement chooser for the Nacrt finishing step.

The rules under test are the user's (brief 3.4 of projects/0004-nacrt-finishing,
as amended on reviewing the drawn proposals): a scale per design out of
1:100 / 1:200 / 1:250 / 1:300 / 1:400 / 1:500, profile primary, the plan promoted
to a larger scale when the bboxes differ drastically but never more than one
rung of the ladder from the profile's, nothing ever rescaled to fit, and every drawing below the
4S sastavnica title block — never in the strip beside it.
"""

import re
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1] / "production" / "tools"
sys.path.insert(0, str(TOOLS))

import nacrt_layout  # noqa: E402
from nacrt_layout import BBox, choose_layout  # noqa: E402

MARGIN = 10.0
GAP = 10.0
# Placements are rounded to 0.1 mm, so a constraint may be missed by half a step.
TOL = 0.06

MJERILO = re.compile(r"^(?:1:(\d+)|profil/tlocrt: 1:(\d+)/1:(\d+))$")


# --- helpers -------------------------------------------------------------


def inside_margins(placement, page=nacrt_layout.A4_PORTRAIT_MM):
    return (placement.x >= MARGIN - TOL
            and placement.y >= MARGIN - TOL
            and placement.right <= page[0] - MARGIN + TOL
            and placement.bottom <= page[1] - MARGIN + TOL)


def clear_of_title_block(placement):
    """Below the title block by at least the gap — never in the strip beside it."""
    return placement.y >= nacrt_layout.TITLE_BLOCK_MM.bottom + GAP - TOL


def check_layout(layout):
    """Every invariant a proposal must satisfy, whatever the input."""
    assert layout.arrangement in ("vertical", "side_by_side")
    assert layout.plan_scale in nacrt_layout.SCALES
    assert layout.profile_scale in nacrt_layout.SCALES
    for placement in (layout.profile, layout.plan):
        assert inside_margins(placement), placement
        assert clear_of_title_block(placement), placement
    assert not layout.profile.overlaps(layout.plan, tol=TOL)
    # At most one rung apart, so the reader switches scale once per sheet.
    rungs = (nacrt_layout.SCALES.index(layout.profile_scale),
             nacrt_layout.SCALES.index(layout.plan_scale))
    assert abs(rungs[0] - rungs[1]) <= nacrt_layout.MAX_STEP
    match = MJERILO.match(layout.mjerilo)
    assert match, layout.mjerilo
    if layout.profile_scale == layout.plan_scale:
        assert int(match.group(1)) == layout.plan_scale
    else:
        assert (int(match.group(2)), int(match.group(3))) == (layout.profile_scale,
                                                              layout.plan_scale)
    assert layout.note and "\n" not in layout.note


def scale_of(bbox, scale):
    return bbox.width * 1000.0 / scale, bbox.height * 1000.0 / scale


# --- the derived page geometry ------------------------------------------


def test_title_block_derived_from_the_sastavnica_cell_table():
    # 39.85, 49.58 -> 291.43, 149.94 pt (outermost of the fifteen cells).
    block = nacrt_layout.TITLE_BLOCK_MM
    assert (block.x, block.y) == pytest.approx((14.06, 17.49), abs=0.01)
    assert (block.width, block.height) == pytest.approx((88.75, 35.40), abs=0.01)
    assert block.right == pytest.approx(102.81, abs=0.01)
    assert block.bottom == pytest.approx(52.90, abs=0.01)


def test_scalemode_is_the_print_dialog_combo_index():
    # 1:400 is not on the dialog's list -> custom (99) + scale="400".
    assert nacrt_layout.SCALEMODE == {100: 1, 200: 2, 250: 3, 300: 4, 400: 99, 500: 5}
    assert tuple(nacrt_layout.SCALEMODE) == nacrt_layout.SCALES


# --- the real cave -------------------------------------------------------


def test_sb_1103_both_at_1_100_stacked_vertically():
    # Golobreska: plan 4 x 9 m, profile 5 x 10 m -> 50 x 100 mm and 40 x 90 mm.
    best, alternatives, reason = choose_layout(BBox(4, 9), BBox(5, 10))

    assert reason == ""
    assert (best.profile_scale, best.plan_scale) == (100, 100)
    assert best.arrangement == "vertical"
    assert best.mjerilo == "1:100"
    assert best.scalemodes == (1, 1)
    check_layout(best)
    # Profile is primary: it sits on top, its top edge at the top of the band.
    assert best.profile.y == pytest.approx(nacrt_layout.TITLE_BLOCK_MM.bottom + GAP,
                                           abs=TOL)
    assert best.plan.y >= best.profile.bottom + GAP - TOL
    # Centred horizontally on the page.
    assert best.profile.x + best.profile.width / 2 == pytest.approx(105.0, abs=TOL)
    assert alternatives


# --- a long profile forces the two designs apart -------------------------


def test_long_profile_and_small_plan_get_different_scales():
    # Profile 36 x 12 m: 360 mm wide at 1:100 cannot fit the 190 mm of usable
    # width, 180 mm at 1:200 does. The plan (6 x 8 m) keeps 1:100 — rule 3, the
    # profile's larger dimension being > 1.6x the plan's.
    best, _, reason = choose_layout(BBox(6, 8), BBox(36, 12))

    assert reason == ""
    assert best.profile_scale == 200
    assert best.plan_scale == 100
    assert best.mjerilo == "profil/tlocrt: 1:200/1:100"
    assert best.scalemodes == (2, 1)
    assert best.arrangement == "vertical"
    check_layout(best)
    assert (best.profile.width, best.profile.height) == pytest.approx((180.0, 60.0))
    assert (best.plan.width, best.plan.height) == pytest.approx((60.0, 80.0))


def test_a_40_m_profile_lands_on_1_250():
    # The case named in the task brief. 40 m at 1:200 is 200 mm and the page
    # offers 210 - 2 x 10 = 190 mm, so it misses by 10 mm — which is why 1:250
    # (scalemode 3) was added to the ladder rather than dropping to 1:300.
    best, _, _ = choose_layout(BBox(6, 8), BBox(40, 12))

    assert best.profile_scale == 250
    assert best.scalemodes[0] == 3
    assert best.mjerilo == "profil/tlocrt: 1:250/1:200"
    assert best.profile.width == pytest.approx(160.0)
    check_layout(best)


# --- 1:300 earns its place ----------------------------------------------


def test_1_300_is_used_when_1_250_misses():
    # Profile 50 x 30 m: 200 x 120 mm at 1:250 (too wide), 166.7 x 100 at 1:300.
    plan, profile = BBox(6, 8), BBox(50, 30)
    assert scale_of(profile, 250)[0] > 190.0
    assert scale_of(profile, 300)[0] <= 190.0

    best, alternatives, _ = choose_layout(plan, profile)

    assert best.profile_scale == 300
    assert 250 not in [alt.profile_scale for alt in alternatives]
    check_layout(best)


def test_1_400_is_used_when_1_300_misses_and_goes_out_as_custom_scale():
    # Profile 58 x 20 m: 193.3 mm wide at 1:300 (misses 190 by a hair), 145 at 1:400.
    plan, profile = BBox(6, 8), BBox(58, 20)
    assert scale_of(profile, 300)[0] > 190.0
    assert scale_of(profile, 400)[0] <= 190.0

    best, _, _ = choose_layout(plan, profile)

    assert best.profile_scale == 400
    assert best.scalemodes[0] == 99                    # custom entry + scale="400"
    assert best.plan_scale == 300                      # one rung, not 1:200
    check_layout(best)


# --- one sheet, one rung -------------------------------------------------


def test_the_two_scales_never_differ_by_more_than_one_rung():
    # A tiny plan beside a long profile: the plan would be legible at 1:100, but
    # a 1:300 profile above a 1:100 (or 1:200) plan makes the reader jump rungs.
    best, alternatives, _ = choose_layout(BBox(3, 4), BBox(50, 30))

    assert best.profile_scale == 300
    assert best.plan_scale == 250                      # the adjacent rung, not 200
    for layout in [best] + alternatives:
        assert abs(nacrt_layout.SCALES.index(layout.profile_scale)
                   - nacrt_layout.SCALES.index(layout.plan_scale)) <= 1


def test_alternatives_carry_no_pointless_downscale():
    # SB 1103 fits at 1:100 both ways; a "plan at 1:200" alternative is noise.
    best, alternatives, _ = choose_layout(BBox(4, 9), BBox(5, 10))
    assert [alt.key for alt in alternatives] == [(100, 100, "side_by_side")]
    for alt in alternatives:
        assert alt.plan_scale <= best.plan_scale or alt.arrangement != best.arrangement


# --- tall and narrow ------------------------------------------------------


def test_two_tall_narrow_designs_go_side_by_side():
    # Profile 3 x 25 m, plan 2 x 12 m: stacked they are 255 mm tall and the band
    # holds 224.1, which would cost the plan a scale step; beside each other the
    # plan keeps 1:100 against the profile's 1:200.
    best, _, _ = choose_layout(BBox(2, 12), BBox(3, 25))

    assert best.arrangement == "side_by_side"
    assert (best.profile_scale, best.plan_scale) == (200, 100)
    assert best.profile.x < best.plan.x          # profile left, plan right
    assert best.plan.x >= best.profile.right + GAP - TOL
    assert best.profile.y == pytest.approx(best.plan.y, abs=TOL)
    check_layout(best)


def test_nothing_is_ever_placed_beside_the_title_block():
    # The strip right of the sastavnica buys a scale step for a narrow pair, and
    # the user rejected that sheet on sight (2026-09-20): half the page empty.
    band_top = nacrt_layout.TITLE_BLOCK_MM.bottom + GAP
    for plan, profile in [(BBox(2, 12), BBox(3, 25)),
                          (BBox(1.5, 20), BBox(2, 26)),
                          (BBox(3, 18), BBox(4, 30))]:
        best, alternatives, _ = choose_layout(plan, profile)
        for layout in [best] + alternatives:
            assert layout.profile.y >= band_top - TOL
            assert layout.plan.y >= band_top - TOL


def test_a_wide_pair_is_not_sent_side_by_side():
    best, _, _ = choose_layout(BBox(12, 5), BBox(14, 6))
    assert best.arrangement == "vertical"


# --- nothing fits ---------------------------------------------------------


def test_a_cave_too_big_for_a4_reports_why():
    best, alternatives, reason = choose_layout(BBox(50, 40), BBox(200, 120))

    assert best is None
    assert alternatives == []
    assert "1:500" in reason
    assert "400" in reason and "240" in reason      # the profile at 1:500, in mm


def test_a_zero_sized_bbox_is_a_programming_error():
    with pytest.raises(ValueError):
        choose_layout(BBox(0, 9), BBox(5, 10))


# --- invariants over a grid ----------------------------------------------


GRID = [BBox(w, h) for w in (2, 4, 7, 15, 30) for h in (3, 9, 20, 45)]


@pytest.mark.parametrize("plan", GRID, ids=lambda b: "plan%gx%g" % (b.width, b.height))
def test_every_proposal_over_a_grid_of_bboxes_is_well_formed(plan):
    for profile in GRID:
        best, alternatives, reason = choose_layout(plan, profile)
        if best is None:
            assert alternatives == []
            assert "1:500" in reason
            continue

        assert reason == ""
        check_layout(best)
        keys = [best.key]
        for alternative in alternatives:
            check_layout(alternative)
            assert alternative.key not in keys, (plan, profile, alternative.key)
            keys.append(alternative.key)
        assert len(alternatives) <= 3


def test_max_alternatives_is_honoured():
    _, alternatives, _ = choose_layout(BBox(4, 9), BBox(5, 10), max_alternatives=1)
    assert len(alternatives) == 1


def test_wider_margins_shrink_the_usable_area():
    # 36 m at 1:200 is 180 mm: it fits 10 mm margins but not 20 mm ones.
    tight, _, _ = choose_layout(BBox(6, 8), BBox(36, 12), margin_mm=20.0)
    assert tight.profile_scale == 250


# --- the console menu ----------------------------------------------------


def test_cli_prints_a_numbered_menu(capsys):
    assert nacrt_layout.main(["4", "9", "5", "10"]) == 0
    out = capsys.readouterr().out
    assert "1:100" in out
    assert "  1)" in out and "prijedlog" in out
    assert "scalemode: profil=1 tlocrt=1" in out


def test_cli_reports_a_cave_that_does_not_fit(capsys):
    assert nacrt_layout.main(["50", "40", "200", "120"]) == 1
    assert "1:500" in capsys.readouterr().out


def test_cli_rejects_junk(capsys):
    assert nacrt_layout.main(["4", "9", "spilja", "10"]) == 2
    assert "ERROR" in capsys.readouterr().out


def test_sketch_draws_the_sheet_in_plain_ascii():
    best, alternatives, _ = choose_layout(BBox(31.94, 11.23), BBox(20.41, 11.87))
    lines = nacrt_layout.sketch(best)
    assert len({len(l) for l in lines}) == 1            # a rectangle
    text = "\n".join(lines)
    assert text.isascii()                                # cp852 console
    for label in ("sastavnica", "profil 1:200", "tlocrt 1:200"):
        assert label in text
    # profile above plan in the stacked arrangement
    assert text.index("profil") < text.index("tlocrt")


def test_sketch_falls_back_to_a_shorter_label_in_a_small_box():
    _, alternatives, _ = choose_layout(BBox(6, 8), BBox(36, 12))
    side = [l for l in alternatives if l.arrangement == "side_by_side"][0]
    text = "\n".join(nacrt_layout.sketch(side))
    assert "tlocrt 1:" not in text and "tlo" in text


def test_sketch_row_puts_sheets_side_by_side():
    best, alternatives, _ = choose_layout(BBox(31.94, 11.23), BBox(20.41, 11.87))
    lines = nacrt_layout.sketch_row([best] + alternatives, ["1)", "2)"])
    assert lines[0].startswith("1)") and "2)" in lines[0]
    assert lines[1].count("+--") == 2
