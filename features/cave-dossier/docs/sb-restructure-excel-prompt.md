# SB restructure — Claude in Excel prompt

Goal: merge the hand-maintained "Za istražit" table into "Svi objekti" (single
master table) and rebuild "Za istražit" as a Power Query view, mirroring how
Istraženi/Nesređeni already work. Designed 2026-08-22 against the 2026-08-16
sandbox snapshot (Svi objekti: table `SO_v2_1`, 1117 rows; Za istražit: table
`Table_4`, 189 rows) — the prompt tells Claude to verify live structure first,
so drift since the snapshot is safe.

Design decisions (user, 2026-08-22):
- **Flag lives in Napomena**, not a dedicated column: migrated rows get
  `za istražit, <old Broj>, <original napomena>` (e.g. `za istražit, 123, ide
  duboko treba opremit`). The keyword at the START of Napomena IS the flag; the
  old Za istražit number stays embedded for traceability.
- **Merge by year**: each migrated row is inserted at its year's position in
  Svi objekti (not appended at the end). Redni broj is disposable — renumbered
  wholesale afterwards. Durable cave identity = Katastarski broj SUE (and, for
  queued caves until explored, the old Broj inside Napomena).
- One new column only: `Poveznica fotografija ulaza`.

After executing in Excel: if the filename changes (e.g. v3.0), update
`SB_WORKBOOK_PATH`/`workbook_filename` in this feature's `.env`/`config.yaml`
AND crospeleo-automation's `.env`. Then refresh our sandbox copy.

---

Paste everything below into Claude in Excel with the SB workbook open:

```
You are working in my caving society's registry workbook (!Speleo_baza_SUE_v2.4.xlsm).
Restructure it so that all caves live in ONE master table, with derived views — the
pattern the workbook already uses for its Istraženi and Nesređeni Power Query sheets.

CONTEXT
- Sheet "Svi objekti" holds the master Excel Table SO_v2_1 (title in row 1, header in
  row 2, columns A:Z, ~1117 data rows). "Redni broj" is a running number with no
  lasting meaning; "Katastarski broj SUE" is assigned once a cave is explored. Rows
  are ordered roughly chronologically by exploration year.
- Sheet "Za istražit" holds Excel Table Table_4 (title+counter in row 1, header in
  row 2, columns A:M, ~189 data rows): caves observed but not yet explored. Columns:
  Broj | Radno ime objekta | X GK | Y GK | X HTRS | Y HTRS | Z | Lokalitet |
  Najbliže mjesto | Godina ili datum opažanja | Napomena | Izvor |
  Poveznica fotografija ulaza
- Today these rows must be manually copied into Svi objekti (and deleted from
  Za istražit) when exploration starts — error-prone. We are eliminating that.

VERIFY FIRST (before changing anything)
1. Confirm the two tables exist with the described header rows and record their exact
   data-row counts. If the structure differs from the above, STOP and tell me.
2. Confirm with me that a backup copy of the file exists. Do not proceed without it.

STEP 1 — extend the master table
Add ONE new column at the RIGHT END of SO_v2_1 (do not reorder existing columns):
- "Poveznica fotografija ulaza"  (photo link, migrated from Za istražit)

STEP 2 — migrate every Za istražit data row into SO_v2_1, MERGED BY YEAR
Insert each migrated row among the Svi objekti rows of its corresponding year:
after the LAST existing row whose year (the first 4-digit year found in
"Godina ili period istraživanja") equals the migrated row's year (first 4-digit
year in "Godina ili datum opažanja"). If no existing row has that year, insert
after the last row with the nearest earlier year. Migrated rows with no year go
at the END of the table. Keep the relative order of existing rows untouched —
insert, never re-sort the existing data. If the year ordering of Svi objekti
turns out too inconsistent for this placement rule to make sense, pause and ask
me instead of guessing.

Column mapping (Za istražit → Svi objekti):
- Radno ime objekta            → Ime objekta
- X HTRS                       → X HTRS
- Y HTRS                       → Y HTRS
- Z                            → Z
- Lokalitet                    → Lokalitet
- Najbliže mjesto              → Najbliže mjesto
- Godina ili datum opažanja    → Godina ili period istraživanja
- Izvor                        → Autori nacrta
- Poveznica fotografija ulaza  → Poveznica fotografija ulaza
- Napomena                     → Napomena, REWRITTEN as the flag format below
- DO NOT copy: X GK, Y GK (dropped by design; HTRS is kept)

Napomena flag format (this is the lifecycle flag — exact format matters):
  za istražit, <old Broj>, <original Napomena text>
- with original napomena:  "za istražit, 123, ide duboko treba opremit"
- without one:             "za istražit, 123"
The keyword "za istražit" must be at the very START of the cell.

STEP 3 — renumber
After all insertions, overwrite the ENTIRE "Redni broj" column of SO_v2_1 with a
fresh running sequence 1..N (top to bottom). Redni broj carries no meaning, so
this is safe; do not touch any other column while renumbering.

STEP 4 — audit
Report:
- SO_v2_1 data-row count before vs after (must differ by exactly the Za istražit count)
- count of rows whose Napomena starts with "za istražit" (case-insensitive; must
  equal the same number)
- a spot-check of the first, a middle, and the last migrated row (all mapped fields,
  including the rewritten Napomena and their position relative to same-year rows).

STEP 5 — retire the old table
Rename the sheet "Za istražit" to "Za istražit ARHIVA v2.4". Do not delete it —
it stays as rollback until I confirm everything, then I delete it myself.

STEP 6 — the new Power Query view (I will do the clicks; you provide exact code)
Give me the exact Power Query M code and step-by-step instructions (Data → Get Data →
From Other Sources → Blank Query → Advanced Editor) to create a query named
"Za istražit" that:
- sources Excel.CurrentWorkbook(){[Name="SO_v2_1"]}[Content]
- keeps only rows where the Napomena text starts with "za istražit",
  case-insensitive (Text.StartsWith with Comparer.OrdinalIgnoreCase), treating
  null Napomena as not matching
- keeps only these columns, in this order: Redni broj, Ime objekta, X HTRS, Y HTRS,
  Z, Lokalitet, Najbliže mjesto, Godina ili period istraživanja, Napomena,
  Autori nacrta, Poveznica fotografija ulaza
- loads to a new sheet named "Za istražit" as a table
Model the load settings on the existing Istraženi query so the workbook stays
consistent.

FROM NOW ON (leave this as a note where I can see it on the new Za istražit sheet):
new cave observations are entered DIRECTLY into Svi objekti with Napomena starting
with "za istražit, " (keyword first, then any note). When a cave gets explored:
fill in its data, assign Katastarski broj SUE, and remove the "za istražit, <broj>,"
prefix from Napomena — the row automatically leaves this view and appears in
Istraženi on refresh. No more copying between tables.

CONSTRAINTS
- Touch nothing else: no other sheets, no existing queries, no VBA, no data
  validations, no conditional formats.
- Preserve cell values exactly (text stays text, numbers stay numbers, Croatian
  diacritics untouched).
- If anything unexpected appears (duplicate names between the two tables, rows
  without a name, a structure mismatch), pause and ask me instead of guessing.
```
