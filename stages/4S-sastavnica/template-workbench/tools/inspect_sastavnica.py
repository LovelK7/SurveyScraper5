"""Dump a sastavnica PDF's geometry — how `sastavnica/addresses.py` is re-derived.

    python sastavnica-template/tools/inspect_sastavnica.py [PDF] [--mode all|text|rules|cells]

`addresses.py` is hand-maintained (the same convention as `osz/addresses.py`).
When the drafter revises `!SUE_sastavnica.ai`, run this against the new export
and update that module from the `cells` table, then re-run `build_blank.py`.

Modes:
  text   every span: bbox, baseline, size, colour — labels are the small grey
         ones, values the larger near-black ones
  rules  the stroked grid lines and the outer frame, which is where the cell
         boundaries actually come from
  cells  the grid lines reduced to row bands and, per band, the label/value
         spans that fall inside them — the table to paste into addresses.py
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pymupdf

DEFAULT_PDF = Path(__file__).resolve().parents[1] / "templates" / "!SUE_sastavnica.pdf"


def _spans(page: pymupdf.Page) -> list[dict]:
    raw = page.get_text("rawdict")
    out = []
    for block in raw["blocks"]:
        if block["type"] != 0:
            continue
        for line in block["lines"]:
            for span in line["spans"]:
                # rawdict gives chars, not a joined string — build both.
                span["baseline"] = span["chars"][0]["origin"][1] if span["chars"] else None
                span["text"] = "".join(c["c"] for c in span["chars"])
                out.append(span)
    return sorted(out, key=lambda s: (round(s["bbox"][1], 1), round(s["bbox"][0], 1)))


def dump_text(page: pymupdf.Page) -> None:
    print("kind   x0      y0      x1      y1      base    size  colour    text")
    for span in _spans(page):
        x0, y0, x1, y1 = span["bbox"]
        kind = "label" if span["size"] < 6 else "VALUE"
        print(f"{kind}  {x0:7.2f} {y0:7.2f} {x1:7.2f} {y1:7.2f} "
              f"{span['baseline']:7.2f} {span['size']:5.2f} #{span['color']:06x}  "
              f"{span['text']!r}")


def _rules(page: pymupdf.Page) -> tuple[list[float], list[float], pymupdf.Rect | None]:
    """Distinct x of vertical rules, y of horizontal rules, and the frame."""
    xs, ys, frame = set(), set(), None
    for drawing in page.get_drawings():
        if drawing["type"] != "s":            # stroked only
            continue
        rect = drawing["rect"]
        if rect.width > 200 and rect.height > 50:
            frame = rect                      # the rounded outer frame
            continue
        if rect.width < 0.2 and rect.height > 5:
            xs.add(round(rect.x0, 2))
        elif rect.height < 0.2 and rect.width > 5:
            ys.add(round(rect.y0, 2))
    return sorted(xs), sorted(ys), frame


def dump_rules(page: pymupdf.Page) -> None:
    xs, ys, frame = _rules(page)
    print(f"frame        {frame}")
    print(f"vertical  x  {['%.2f' % x for x in xs]}")
    print(f"horizontal y {['%.2f' % y for y in ys]}")


def dump_cells(page: pymupdf.Page) -> None:
    xs, ys, frame = _rules(page)
    if frame is None:
        print("no outer frame found — cannot derive bands")
        return
    bands = sorted({round(frame.y0, 2), *ys, round(frame.y1, 2)})
    spans = _spans(page)
    print(f"block {frame.x0:.2f},{frame.y0:.2f} -> {frame.x1:.2f},{frame.y1:.2f}  "
          f"({frame.width:.2f} x {frame.height:.2f} pt)")
    for top, bottom in zip(bands, bands[1:]):
        print(f"\nrow {top:.2f} .. {bottom:.2f}")
        edges = sorted({round(frame.x0, 2), round(frame.x1, 2),
                        *[x for x in xs if _rule_spans(page, x, top, bottom)]})
        for left, right in zip(edges, edges[1:]):
            label = value = None
            for span in spans:
                mid_x = (span["bbox"][0] + span["bbox"][2]) / 2
                if not (left <= mid_x <= right and top <= span["baseline"] <= bottom):
                    continue
                if span["size"] < 6:
                    label = span["text"]
                else:
                    value = span
            if label is None and value is None:
                continue
            note = ""
            if value is not None:
                centred = abs((value["bbox"][0] + value["bbox"][2]) / 2
                              - (left + right) / 2)
                note = (f" value={value['text']!r} size={value['size']:.0f} "
                        f"base={value['baseline']:.2f} (bottom-{bottom - value['baseline']:.2f}) "
                        f"off-centre={centred:.2f}")
            print(f"  ({left:7.2f}, {top:7.2f}, {right:7.2f}, {bottom:7.2f})  "
                  f"{(label or '-'):<30}{note}")


def _rule_spans(page: pymupdf.Page, x: float, top: float, bottom: float) -> bool:
    """Does a vertical rule at x actually divide this row band?"""
    for drawing in page.get_drawings():
        rect = drawing["rect"]
        if drawing["type"] != "s" or rect.width >= 0.2:
            continue
        if abs(rect.x0 - x) < 0.2 and rect.y0 <= top + 0.5 and rect.y1 >= bottom - 0.5:
            return True
    return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("pdf", nargs="?", default=str(DEFAULT_PDF))
    parser.add_argument("--mode", default="cells",
                        choices=["all", "text", "rules", "cells"])
    args = parser.parse_args(argv)

    doc = pymupdf.open(args.pdf)
    page = doc[0]
    print(f"{args.pdf}\npage {page.rect}  fonts={[f[3] for f in page.get_fonts()]}  "
          f"widgets={len(list(page.widgets()))}  drawings={len(page.get_drawings())}\n")
    if args.mode in ("all", "text"):
        dump_text(page)
        print()
    if args.mode in ("all", "rules"):
        dump_rules(page)
        print()
    if args.mode in ("all", "cells"):
        dump_cells(page)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
