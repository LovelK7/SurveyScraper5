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
- 2026-08-23 — OSZ fetcher: read Word content controls directly (`w:sdtContent//w:t`,
  skip `w:showingPlcHdr`, checkbox state from `w14:checkbox/w14:checked`); python-docx
  returns nothing for them. `osz-template/tools/inspect_osz.py` is a working reference.
- 2026-08-23 — put a `w:tag` on every OSZ control equal to the parser's canonical field
  name (`expert_hazards`, `location_access_text`, …) so the fetcher stops matching on
  heading text; 23 of 50 headings in v10 have no alias today.
- 2026-08-23 — snow/ice: the two presence checkboxes can retire
  `infer_snow_ice_negative` — unticked + filled Mikroklimatski section means an explicit
  `snijeg - ne` / `led - ne`, no regional guessing.
- 2026-08-23 — `onečišćenje otpadom` must also tick Opasnosti `otpad u objektu` (568
  caves in the registry — the most frequent hazard label); MES ticks two CroSpeleo
  controls at once.
- 2026-08-23 — still unstructured in the OSZ and therefore still heuristic-fed:
  Izvor koordinata (8-value vocab), Strujanje zraka + smjer, Mjerne točke as numbers,
  CO₂ method/value, Stanje otpada / Zapremnina otpada / Recentni ljudski ostaci.
- 2026-08-23 — derive **Otok** from `Lokalitet` using crospeleo-automation's ~125k-place
  gazetteer (protocol wants it whenever the object is on an island; the template
  deliberately has no field).
- 2026-08-23 — `osz-template/tools/make_mockup.py` is a working OSZ writer (controls,
  checkboxes, plain cells) — reuse it as the base for the `cave_dossier` OSZ builder in
  part 2.1b instead of starting from scratch.
- 2026-08-23 — run `check_conformance.py` as a pre-commit hook or CI step so a template
  edit that breaks a CroSpeleo vocabulary is caught the moment it lands.
- 2026-08-25 — the OSZ fetcher needs TWO readers: `w:sdt` + `w14:checkbox` for
  zapisnici filled in Word, and a text reader for the Google-Docs variant (`[x]` vs
  `[ ]`, values wrapped in `⟨ ⟩` treated as empty). Join a paragraph's `w:t` runs
  before matching either — Word and Docs split runs differently.
- 2026-08-25 — queue reader: the old Broj in `za istražit, [<broj>,] <note>` is
  optional (`Ponor Gotovž`), so parse it as a hint, never as a required key.
- 2026-08-25 — wrapping the 27 plain value cells (IME OBJEKTA, koordinate, dimenzije,
  ekipa…) in plain-text controls would unlock two things at once: `w:tag` keys for the
  fetcher and `documentProtection edit="forms"` for the distributed template.
- 2026-08-25 — trim the fixed row heights on Biospeleološki / Arheološki: the filled
  form runs to 5 pages purely on white space, and the un-floated table costs the rest.
- 2026-08-25 — set Literatura and Napomene controls to Arial 10 pt; they still fall
  back to the 11 pt document default.
- 2026-08-25 — run `check_gdocs_roundtrip.py` against a real Google Docs export once
  the first Docs-filled zapisnik comes back, and keep that file as a parser fixture.
- 2026-08-25 — `flatten_for_gdocs.py` must be re-run after every Word save of the
  `_gdocs` variant: Word re-embeds ~3 MB of fonts unless *Embed fonts in the file* is
  off in the source document.
- 2026-08-25 — SB v3.0 has **7 trailing blank rows** inside the `SO_v2_1` table (Excel
  rows 1297-1303): `sb stats` counts 1301 data rows where only 1294 are caves. A
  "drop rows with neither name nor SUE" filter in `SBReader._read_sheet` would fix the
  count everywhere at once (touches the M1 numbers recorded in STATUS/SESSIONS).
- 2026-08-25 — `cavedossier report` currently resolves one cave at a time; a
  `--queue` / `report --all` sweep over the 185 `za istražit` rows would turn the
  gating table into a worklist ("what is missing across the whole society archive").
- 2026-08-25 — 416 rows have no SUE number and 152 no `Autori nacrta`; the gating run
  over the whole sandbox (see the M2 session) is a cheap data-quality report for the
  user, independent of any single cave's dossier.
- 2026-08-26 — ~~SB's Nesređeni view over-matches "ponor"~~ → **retracted 2026-08-28**: all 5
  ponor-only rows use it as a deliberate tag ("ponor, možda kopati"). The real overlap was
  `za istražit` rows matching "ponoviti"/"neistraženo" — M fix in docs/sb-powerquery.md.
- 2026-08-26 — `cavedossier sb audit-authors`: list every `Autori nacrta` cell the splitter
  finds suspicious (placeholders, single-word entries, brackets that are not societies) so the
  column can be cleaned in one Excel pass. 108 rows carry an outside-society bracket today.
- 2026-08-26 — 47 named rows have neither a SUE number nor a Napomena flag, so they appear in
  none of SB's three views. A `report --unclassified` listing would let the user flag them.
- 2026-08-26 — 2.1d mover: at SUE assignment, propose renaming the cave's photos in
  `!!Fotografije ulaza za istražit` to `<padded SUE>_…` and moving them into the main folder.
  The staging folder is free-form named (59 files, cave-name based), so the match has to be by
  cave name, not by number.
- 2026-08-26 — ~~give **sudjelovanje** its own Power Query view~~ → done by the user
  2026-08-28 (`S_v2_1`, sheet *Sudjelovanje*, same keyword the tool matches). Still open from
  that idea: tighten the Nesređeni filter to a word-boundary match on "ponor", which today
  drags in 8 unrelated rows.
- 2026-08-26 — the 2.1d processor itself (downsize to ~1920 px / ~1.5 MB) is still to be
  written; `photos match-queued --apply` only renames. Pillow is already an optional extra.
- 2026-08-26 — once intake lands, wire `archive/izjave.py` scope rules into gating: a
  locality-scoped izjava must not satisfy a cave outside that Lokalitet.
- 2026-08-26 — ~~two staged photos match no SB row~~ → resolved 2026-08-28: `rubinija` is a
  transposition of *Rubijina jama* (1214, now in `photos.manual_matches`), `kostrčani` was
  removed by the user as unidentifiable. The folder now matches 52 of 52.
- 2026-08-29 — `cavedossier intake sheet-gaps`: list Liburnija sheet rows that are caves,
  explored, carry a plaque and have no SB row — i.e. what to add to SB. Run ad hoc on
  2026-08-29 and it found exactly one (Jamorinke, added as 1311); worth a command once
  people keep adding rows to that sheet. Needs an out-of-scope list so another society's
  caves (sheet 89, Jama na Patuhovcu) are not re-raised every run.
- 2026-08-29 — five intake leaves are empty placeholders; a "leaf with no files" flag in
  `intake map` would make that visible at a glance instead of only in the file count.
- 2026-08-29 — **satellite hub** (`cave_dossier/satellites/`): a committed crosswalk
  file per satellite table + a ranked resolver, replacing the per-table bespoke bridge.
  First payoff is `sat gaps liburnija` — 117 confirmed caves the sheet has and SB does
  not. Designed in [docs/sb-liburnija-hub.md](../docs/sb-liburnija-hub.md); unscheduled.
- 2026-08-29 — SB naming convention worth enforcing at row creation: a cave born from
  Liburnija row N always carries `LiDAR Kristal N` (as `Ime objekta` if unnamed, else in
  `Sinonimi`). Turns the sheet's local number into a legitimate key instead of a trap.
- 2026-08-29 — `Najbliže mjesto` could be a `row_defaults` entry like `Lokalitet`
  (*Veprinac* on 53 of the 55 existing LiDAR Kristal rows) — left empty deliberately
  because the sheet does not carry it; ask before guessing.
- 2026-08-29 — the ambiguity radius is flat (15 m). A *relative* rule — a rival only
  counts if it is comparably close — would be better reasoning than the absolute one;
  `EXACT_MATCH_M` covers today's cases so it was not needed yet.
- 2026-08-29 — `sat sync` reads a cached CSV export of the Google Sheet; a
  `sat refresh liburnija` that re-exports via the Drive MCP would close the staleness
  hole the README warns about.
- 2026-08-29 — promote the crosswalk from derived-per-run to a committed file once
  human overrides outgrow `config.yaml` (`confirmed_new`, `manual_matches`,
  `out_of_scope`). Types in `satellites/model.py` are already shaped for it.
- 2026-08-29 — `Literatura` (45 rows) is the cheap second satellite: same protocol,
  its own coordinate calibration run before its tolerances are trusted.
- 2026-08-30 — `karta --missing`: sweep SB for rows that have coordinates but no
  `SB_<broj>.png` in `!!Isječci karte` and fetch them one by one (rate-limited —
  each run is a server-side save on georef.hr).
- 2026-08-30 — wire 2.1c outputs into gating: the CroSpeleo-gate rules for
  `Isječak karte` / `Georef zapis` can now check `!!Isječci karte` +
  `!georef_zapisi.csv` instead of reporting *not checked yet*.
- 2026-08-30 — every georef.hr save allocates a new point ID (`--force` re-runs
  litter the registry); investigate whether the flow can detect and validate an
  existing point at the same coordinates instead of re-saving.
- 2026-08-30 — downstream adapter: crospeleo-automation discovers
  `georef_record.txt` + `map_screenshot.png` in its own run dirs; a small shim
  reading `!!Isječci karte`/`!georef_zapisi.csv` would let it skip its own
  (headed) georef run for caves this tool already covered.
- 2026-08-30 — `Jama Petrci` intake leaf is unresolved (closest: *Jama kod
  Petrci*, Redni broj 1043 at 0.87) — user says leave as is; revisit when the
  folder's cave gets its SB row or the match is confirmed.
- 2026-08-30 — headed `--debug` runs clamp the capture window to the physical
  display, so their excerpts are lower-res than headless ones; if a verified-by-eye
  full-res capture is ever needed, verify headed first, then re-run headless.
- 2026-08-30 — `osz prefill --missing`: sweep SB (analogous to the `karta --missing`
  idea above) for rows that have coordinates but no `SB_<broj>_OSZ.docx` in the
  prefill Drive dir and generate them in a batch.
- 2026-08-30 — elevation source upgrade (user): the 2.1b Z-finder samples the open
  25 m-class DMV (INSPIRE EL-COV); the user will eventually look for a **DEM10-class
  layer** for local fetching of better-resolution elevations — `geo/elevation.py`
  only needs a new tile source + `geo.elevation_source_label` when it appears.
- 2026-08-30 — converge `osz-template/tools/make_mockup.py` onto
  `cave_dossier.osz.writer` (the maintained copy of its fill primitives) the next
  time the workbench is touched, so the two cannot drift.
- 2026-08-30 — `geo locate`'s settlement screening flagged SB 651's `Lokalitet =
  Breza` as a naselje (it IS the nearest settlement, 1.26 km away) — a
  `sb audit-lokalitet` sweep over all rows would list every Lokalitet cell holding
  a settlement name, for one cleaning pass in Excel.
- 2026-08-30 — promote the session's scratch sweep harness (loads SB once, runs
  both geo finders over a stratified cave sample, prints a compact table + notes)
  into a real `cavedossier geo sweep [--limit N]` command — it found three real
  bugs in one run and is the natural data-quality report for the finders.
- 2026-08-30 — the three karta re-runs this session each allocated a fresh
  georef.hr point ID for the same caves (format migration) — the
  detect-existing-point idea above (2026-08-30, `--force` litter) got more urgent.
