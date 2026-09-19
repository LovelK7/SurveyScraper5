"""Cell addresses of the OSZ v10 template — table[t].row[r].cell[c].

Positional by necessity: no control in v10 carries a ``w:tag`` (tagging is
a standing backlog item), so fields are addressed by table coordinates the
way the workbench's make_mockup.py does. Verified against the committed
``osz-template/templates/Zapisnik_OSZ_v10.docx`` with
``inspect_osz.py --mode index`` on 2026-08-30 — regenerate that dump and
update THIS module whenever the template layout changes; a new template
version gets its own address map beside this one.
"""

from __future__ import annotations

from dataclasses import dataclass

TEMPLATE_VERSION = "v10"


@dataclass(frozen=True)
class CellAddr:
    table: int
    row: int
    cell: int
    # "plain" table cell · "sdt_cell" cell-level control · "sdt_inline"
    # a text control INSIDE a plain cell (the narrative sections whose
    # heading shares the cell).
    kind: str = "plain"


# Field key -> address. Keys match osz/models.PrefillValues field names.
# This maps every machine-addressable identity/location cell; which of them
# PREFILL actually fills is decided in osz/prefill.py (user, 2026-08-30:
# Katastarski broj is the archivist's manual final step, Duljina/Dubina and
# the exact Datum come from other processes — prefill never touches those).
V10: dict[str, CellAddr] = {
    "katastarski_broj": CellAddr(0, 0, 1),
    "broj_plocice": CellAddr(0, 1, 1),
    "ime_objekta": CellAddr(1, 0, 1),
    "sinonimi": CellAddr(1, 1, 1),
    "zupanija": CellAddr(1, 3, 1),
    "grad_opcina": CellAddr(1, 4, 1),
    "najblize_mjesto": CellAddr(1, 5, 1),
    "lokalitet": CellAddr(1, 6, 1),
    "x_htrs": CellAddr(2, 2, 2, kind="sdt_cell"),
    "y_htrs": CellAddr(2, 2, 4, kind="sdt_cell"),
    "kota_ulaza": CellAddr(2, 4, 2),
    "izvor_kote": CellAddr(2, 4, 4),
    "izvor_koordinata": CellAddr(2, 5, 4),
    "duljina": CellAddr(4, 3, 0),
    "dubina": CellAddr(4, 3, 2),
    "datum_istrazivanja": CellAddr(6, 8, 1),
    # The "Položaj i pristup objektu" narrative — a cell-level content
    # control; prefilled from config/pristupi.yaml when a rule matches.
    "polozaj_pristup": CellAddr(3, 0, 1, kind="sdt_cell"),
    # Entrance details.
    "broj_ulaza": CellAddr(2, 5, 2),
    "sirina_ulaza": CellAddr(2, 6, 2),
    "visina_duljina_ulaza": CellAddr(2, 6, 4),
    "sporedni_ulazi": CellAddr(2, 9, 2, kind="sdt_cell"),
    "horizontalna_duljina": CellAddr(4, 3, 1),
    "visinska_razlika": CellAddr(4, 3, 3),
    # Narrative sections (coordinates proven by the workbench's
    # make_mockup.py fill of the 811 example).
    "opis": CellAddr(4, 7, 0, kind="sdt_cell"),
    "perspektiva": CellAddr(4, 9, 0, kind="sdt_cell"),
    "geologija": CellAddr(5, 2, 0, kind="sdt_cell"),
    "mikroklima": CellAddr(5, 5, 0, kind="sdt_cell"),
    "biospeleologija": CellAddr(5, 7, 0, kind="sdt_cell"),
    "arheologija": CellAddr(5, 9, 0, kind="sdt_inline"),
    "opasnosti": CellAddr(5, 11, 0, kind="sdt_inline"),
    "zagadenost": CellAddr(6, 2, 0, kind="sdt_inline"),
    "povijest": CellAddr(6, 4, 0, kind="sdt_inline"),
    "literatura": CellAddr(6, 6, 0, kind="sdt_inline"),
    "napomene": CellAddr(6, 21, 1, kind="sdt_cell"),
    # Survey/team metadata. The fetcher (osz/reader.py) reads these for the
    # SB backfill; prefill writes them only when MIGRATING an older filled
    # OSZ forward (osz/prefill.py) — never from SB.
    "istrazile_udruge": CellAddr(6, 9, 1),
    "istrazile_udruge_2": CellAddr(6, 10, 1),
    "clanovi_ekipe": CellAddr(6, 11, 1),
    "clanovi_ekipe_2": CellAddr(6, 12, 1),
    "clanovi_ekipe_3": CellAddr(6, 13, 1),
    "crtali": CellAddr(6, 14, 1),
    "mjerili": CellAddr(6, 15, 1),
    "mjerili_2": CellAddr(6, 16, 1),
    "nacrt_uredio": CellAddr(6, 17, 1),
    "fotografirali": CellAddr(6, 18, 1),
    "autor_fotografije_ulaza": CellAddr(6, 19, 1),
    "mjesto_zapisnika": CellAddr(6, 23, 1),
    "datum_zapisnika": CellAddr(6, 23, 3),
    "zapisnicar": CellAddr(6, 23, 5),
}

# The isječak-karte frame: table 2's first column is one vertically merged
# cell whose merge START is row 1 (row 0 is the heading row) — the drawing
# goes there.
KARTA_FRAME = CellAddr(2, 1, 0)
