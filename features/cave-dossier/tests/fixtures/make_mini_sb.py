"""Regenerate tests/fixtures/mini_sb.xlsx — a tiny synthetic SB workbook.

Mimics the live workbook's structural quirks: a metadata row ABOVE the real
header row, Croatian diacritics in names, a second (irrelevant) sheet, and
header spellings that differ in case/whitespace from config.yaml (exercising
diacritic-insensitive canonicalization). All content is fake.

Column set follows SB **v3.0** (single master "Svi objekti" table), including
the columns the M2 dossier reads and the ``za istražit`` queue flag that lives
in Napomena. Row 4 is the queue row: no SUE number, no coordinates.

Run from the feature root:  python tests/fixtures/make_mini_sb.py
"""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook

HERE = Path(__file__).resolve().parent

ROWS = [
    # metadata junk row (Excel row 1) — must NOT be detected as header
    ["Speleo baza TEST", None, None, "v0.0"],
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
        "Sinonimi",
        "Lokalitet",
        "Najbliže mjesto",
        "Duljina",
        "Dubina",
        "Z",
        "Napomena",
        "Fotografija ulaza",
        "Zagađenost",
        "Ledenica",
        "Godina zadnjeg istraživanja",
    ],
    # data rows (Excel rows 3-7) — all synthetic
    # 3: modern, complete-as-SB-can-be
    ["Špilja Testovka", "001", "1. krug", "unesen", "T-01", "Ana Anić", "2015",
     450123.0, 5023456.0, "Testovka mala", "Testni kras", "Testno Selo",
     40, 12, 500, "ok", "DA", "NE", "NE", "2015"],
    # 4: two drawing authors, semicolon-separated
    ["Jama Čavlić", "002", "1. krug", None, "T-02", "Ivo Ivić; Ana Anić", "2018-2019",
     451000.5, 5024000.5, None, "Testni kras", "Testno Selo",
     15, 30, 610, None, "NE", "NE", "NE", "2019"],
    # 5: modern exploration with NO plaque → §5.1 blocker
    ["Ponor pod Kukom", "003", "2. krug", None, None, "Ivo Ivić", "2021",
     452222.0, 5025555.0, None, "Kuk", "Gornje Testno",
     25, 8, 300, None, None, None, None, "2021"],
    # 6: still in the queue — no SUE, no plaque, no coordinates, "/" author
    ["Đulin ponor mali", None, None, None, None, "/", None,
     None, None, None, None, None,
     None, None, None, "za istražit, 268, treba ponoviti", None, None, None, None],
    # 7: pre-2015 exploration, surname-first author form
    ["Pećina žedna", "005", "2. krug", "fali izjava", "T-05", "Malez, M. (1960)", "1960",
     453333.0, 5026666.0, None, "Žedno", "Donje Testno",
     12, 4, 200, "stari zapis", "NE", "NE", "NE", "1960"],
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
