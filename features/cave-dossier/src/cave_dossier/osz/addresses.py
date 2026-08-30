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
    kind: str = "plain"  # "plain" | "sdt_cell"


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
    # Read-only for the fetcher (osz/reader.py) — prefill never writes them:
    "crtali": CellAddr(6, 14, 1),
    "mjerili": CellAddr(6, 15, 1),
}

# The isječak-karte frame: table 2's first column is one vertically merged
# cell whose merge START is row 1 (row 0 is the heading row) — the drawing
# goes there.
KARTA_FRAME = CellAddr(2, 1, 0)
