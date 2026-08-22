# Ideas backlog — cave-dossier

Implementation log for new ideas: one dated line per idea that surfaced during
development but isn't scheduled. `/wrap-up` appends here; promote to a milestone
when an idea's time comes. Nothing here is a commitment.

- 2026-08-16 — `sb inspect` could optionally emit JSON (`--json`) so later stages
  (OSZ builder) consume SB rows mechanically instead of re-reading the workbook.
- 2026-08-16 — a `sb diff-sandbox` command comparing sandbox vs live workbook row
  counts/headers would make the M1 live-vs-sandbox verification repeatable.
- 2026-08-16 — the workbook's **"Za istražit"** sheet (spotted via `sb stats`) is
  probably the caves-to-be-explored queue → a `sb next` / `sb za-istrazit` reader
  once the user confirms its semantics.
- 2026-08-16 — `Link Nacrt` / `Link Zapisnik` columns carry SUE-keyed references;
  could drive archive-file resolution cross-checks in the M2 dossier gathering.
- 2026-08-22 — after the SB restructure, SBReader gains a queue API: za-istražit
  rows = Napomena starts with "za istražit" (case-insensitive); parse the embedded
  old Broj (`za istražit, <broj>, <note>`) as a secondary handle. `cavedossier sb
  za-istrazit` lists the queue for M2.
