# sb-sync — SB ↔ satellite difference lists

Output of `cavedossier sat sync`. One dated folder per run:

```text
sb-sync/<satellite>/<YYYY-MM-DD>/
    1-za-sb.csv        new SB rows — paste below the last row of `Svi objekti`
    2-dopune-sb.txt    cells to ADD to existing SB rows (the LiDAR Kristal synonym)
    3-za-tablicu.txt   cells the satellite has wrong — fix by hand in the sheet
    4-za-odluku.txt    conflicts and ambiguities — nothing is decided by a rule
```

`1-za-sb.csv` carries **all 24 columns of `Svi objekti`, in the workbook's own
order**, with empties where the satellite has nothing — a subset cannot be pasted
into a table. It is real CSV — Napomena is full of commas, so values are quoted
where they must be. Every file is written UTF-8 **with a BOM**, because Windows
Excel reads a UTF-8 file as the local codepage without one and turns every č/š/ž
into mojibake. Excel takes the field separator from the machine's list separator
(`sList`, a comma here), not from the file.

`sat sync` is **read-only on both sides**. It never writes to SB and never
writes to the satellite: it reads the workbook and a cached export, compares
them, and leaves these lists for a person to carry out. That is the whole
point — the field sheet is a live Google Sheet people type into, and SB is a
macro-heavy shared workbook. See
[docs/sb-liburnija-hub.md](../docs/sb-liburnija-hub.md) for the design and
[docs/EXCEL_WORKBOOK_SAFETY.md](../docs/EXCEL_WORKBOOK_SAFETY.md) for why.

```bash
cavedossier sat sync --coords --out          # → sb-sync/liburnija/<today>/
cavedossier sat sync --coords --out <dir>    # → somewhere else
```

**The runs themselves are gitignored** — they carry real society data (cave
names, field comments, coordinates). Only this README is tracked. A run is a
snapshot of two moving sources, so it goes stale: re-run rather than reuse an
old folder, and refresh the cached satellite export first if the run will be
used to decide that something is *missing* from SB.
