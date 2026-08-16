# STATUS

Updated: 2026-08-16 (maintained by `/wrap-up` at the end of each session)

Part numbering per [ARCHITECTURE.md](ARCHITECTURE.md).

## Part status

| Part | Status |
|---|---|
| 1 — field mobile app | PARKED (manual workflow; revisit after stage 2 works) |
| 2.1a — csx-to-survey | OPERATIONAL (own feature, semi-manual 4-step pipeline) |
| 2.1b — OSZ builder | NOT STARTED (waiting on template) |
| 2.1c — isječak karte | NOT STARTED (port planned, M3) |
| 2.1 — dossier builder | NOT STARTED (M2) |
| 2.2 — SB communication | **M1 IN PROGRESS** |

## Current milestone — M1: SB read-only communication

- [x] Feature scaffold `features/cave-dossier/` (pyproject, config, docs, sessions)
- [x] Port normalization + sb_safe_io + trimmed SB reader (see docs/PORTING.md)
- [x] CLI: `cavedossier sb columns` / `sb inspect --cave` / `sb stats` with SANDBOX/LIVE banner
- [x] Unit tests on synthetic fixture (header autodetect, find_cave)
- [x] Sandbox copy of the live workbook in `example/sb-sandbox/` (taken 2026-08-16)
- [x] One read-only run against the LIVE workbook; stats identical to sandbox
- [ ] User eyeballs 2–3 known caves via `sb inspect` against Excel
- [ ] Confirm the "caves to be explored" source — discovery: the workbook has a
      **"Za istražit"** sheet (likely exactly this); also found `Duljina`/`Dubina`
      dimension columns (recorded in docs/sb-write-back-design.md)

## Waiting on user

- Eyeball check: `cavedossier sb inspect --cave "<a cave you know>"` vs Excel (2–3 caves)
- Confirm "Za istražit" sheet is the to-explore queue (and whether M2 should read it)
- Society's blank OSZ template DOCX (gates M4 / part 2.1b)
- Field-data intake dir layout on Drive (needed at M2 start; proposal will be drafted then)
- Mobile-app context material (parked with part 1)

## Recent sessions

- 2026-08-16 — M0+M1: docs scaffold, cave-dossier feature, SB reader + CLI → [features/cave-dossier/sessions/SESSIONS.md](features/cave-dossier/sessions/SESSIONS.md)
- 2026-08-16 — repo setup: csx-to-survey-pipeline migrated from cSurvey/dev → [features/csx-to-survey-pipeline/sessions/SESSIONS.md](features/csx-to-survey-pipeline/sessions/SESSIONS.md)
