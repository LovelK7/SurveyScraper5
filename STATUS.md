# STATUS

Updated: 2026-08-25 (maintained by `/wrap-up` at the end of each session)


Part numbering per [ARCHITECTURE.md](ARCHITECTURE.md).

## Part status

| Part | Status |
|---|---|
| 1 — field mobile app | PARKED (manual workflow; revisit after stage 2 works) |
| 2.1a — csx-to-survey | OPERATIONAL (own feature, semi-manual 4-step pipeline) |
| 2.1b — OSZ builder | NOT STARTED — **OSZ v10 template finalised 2026-08-23** (content controls + 9 checkbox groups); reading it needs a `w:sdt`-aware parser |
| 2.1c — isječak karte | NOT STARTED (port planned, M3) |
| 2.1 — dossier builder | NOT STARTED (M2) |
| 2.2 — SB communication | **M1 IN PROGRESS** |

## Current milestone — M1: SB read-only communication

- [x] Feature scaffold `features/cave-dossier/` (pyproject, config, docs, sessions)
- [x] Port normalization + sb_safe_io + trimmed SB reader (see docs/PORTING.md)
- [x] CLI: `cavedossier sb columns` / `sb inspect --cave` / `sb stats` with SANDBOX/LIVE banner
- [x] Unit tests on synthetic fixture (header autodetect, find_cave)
- [x] Sandbox copy of the live workbook in `example/sb-sandbox/` (refreshed 2026-08-25 → v3.0)
- [x] One read-only run against the LIVE workbook; stats identical to sandbox
- [ ] User eyeballs 2–3 known caves via `sb inspect` against Excel
- [x] "Caves to be explored" source confirmed: **"Za istražit"** table. Decision
      2026-08-22: SB gets restructured — Za istražit rows merge into Svi objekti
      (by year), flagged by a `za istražit, <old broj>, <note>` prefix in
      **Napomena**; Za istražit becomes a Power Query view (like
      Istraženi/Nesređeni). Prompt for Claude in Excel:
      [features/cave-dossier/docs/sb-restructure-excel-prompt.md](features/cave-dossier/docs/sb-restructure-excel-prompt.md)
- [x] User executed the SB restructure in Excel → **`!Speleo_baza_SUE_v3.0.xlsm`**
      (2026-08-25). Single master `Svi objekti` (table `SO_v2_1`, header row 2,
      1301 rows, 24 cols — GK columns dropped); Istraženi / Nesređeni / **Za
      istražit** are all Power Query views now (`IO_v2_1`, `NO_v2_1`, `ZI_v2_1`);
      old sheet kept as `Za istražit ARHIVA v2.4`. 185 rows carry the
      `za istražit, …` flag in Napomena. Config + sandbox + `safe_io` repointed;
      7 tests green.

## Waiting on user

- Refresh the **Za istražit** Power Query view (Data → Refresh All): the view has 184
  rows but 185 are flagged in the master — `Ponor Gotovž` (Redni broj 1294) is missing.
  Its Napomena is `za istražit, detalji u literaturi`, i.e. no old-Broj number in the
  second field; if a refresh doesn't fix it, the query filters on that number and new
  queue rows will keep vanishing from the view.
- Eyeball check: `cavedossier sb inspect --cave "<a cave you know>"` vs Excel (2–3 caves)
- ~~Society's blank OSZ template DOCX~~ → delivered 2026-08-23:
  [features/cave-dossier/osz-template/templates/Zapisnik_OSZ_v10.docx](features/cave-dossier/osz-template/templates/Zapisnik_OSZ_v10.docx)
- Distribute the finalised OSZ v10 to recorders (template-side work is done;
  two cosmetic leftovers noted in [audit-v10.2.md](features/cave-dossier/osz-template/docs/audit-v10.2.md) §"Sitnice")
- Field-data intake dir layout on Drive (needed at M2 start; proposal will be drafted then)
- Mobile-app context material (parked with part 1)

## Recent sessions

- 2026-08-23 — project renamed SurveyScraper4 → SurveyScraper5 (complete: folder, Claude key, venv re-verified) → [features/cave-dossier/sessions/SESSIONS.md](features/cave-dossier/sessions/SESSIONS.md)
- 2026-08-23 — OSZ v10 template finalised: placeholders, checkbox vocabularies, workbench + conformance tooling → [features/cave-dossier/sessions/SESSIONS.md](features/cave-dossier/sessions/SESSIONS.md)
- 2026-08-22 — SB restructure decision: single master table, Za istražit as PQ view → [features/cave-dossier/sessions/SESSIONS.md](features/cave-dossier/sessions/SESSIONS.md)
