"""Regenerate tests/fixtures/mini_sb.xlsx — a tiny synthetic SB workbook.

Mimics the live workbook's structural quirks: a metadata row ABOVE the real
header row, Croatian diacritics in names, a second (irrelevant) sheet, and
header spellings that differ in case/whitespace from config.yaml (exercising
diacritic-insensitive canonicalization). All content is fake.

Run from the feature root:  python tests/fixtures/make_mini_sb.py
"""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook

HERE = Path(__file__).resolve().parent

ROWS = [
    # metadata junk row (Excel row 1) — must NOT be detected as header
    ["Speleo baza TEST", None, None, "v0.0", None, None, None, None, None],
    # header row (Excel row 2) — case/spacing variants on purpose
    [
        "IME OBJEKTA",            # config: "Ime objekta"
        "Katastarski broj SUE",
        "CroSpeleo unos",
        "Katastarski broj RH",
        "Broj pločice",
        "Autori nacrta",
        "Godina ili period istraživanja",
        "x htrs",                 # config: "X HTRS"
        "Y HTRS",
    ],
    # data rows (Excel rows 3-7) — all synthetic
    ["Špilja Testovka", "001", "1. krug", "unesen", "T-01", "Ana Anić", "2015", 450123.0, 5023456.0],
    ["Jama Čavlić", "002", "1. krug", None, "T-02", "Ivo Ivić; Ana Anić", "2018-2019", 451000.5, 5024000.5],
    ["Ponor pod Kukom", "003", "2. krug", None, None, "Ivo Ivić", "2021", 452222.0, 5025555.0],
    ["Đulin ponor mali", "004", None, None, "T-04", None, None, None, None],
    ["Pećina žedna", "005", "2. krug", "fali izjava", "T-05", "Ana Anić", "2023", 453333.0, 5026666.0],
]


def main() -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Svi objekti"
    for row in ROWS:
        ws.append(row)
    meta = wb.create_sheet("Bilješke")
    meta.append(["Ovo je testni radni list — nije dio podataka."])
    out = HERE / "mini_sb.xlsx"
    wb.save(out)
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
