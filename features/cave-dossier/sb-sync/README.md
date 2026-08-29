# sb-sync — SB ↔ satellite difference lists

Output of `cavedossier sat sync`. One dated folder per run:

```text
sb-sync/<satellite>/<YYYY-MM-DD>/
    1-za-sb.tsv        new SB rows — paste below the last row of `Svi objekti`
    2-za-tablicu.txt   cells the satellite has wrong — fix by hand in the sheet
    3-za-odluku.txt    conflicts and ambiguities — nothing is decided by a rule
```

`sat sync` is **read-only on both sides**. It never writes to SB and never
writes to the satellite: it reads the workbook and a cached export, compares
them, and leaves these three lists for a person to carry out. That is the whole
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
