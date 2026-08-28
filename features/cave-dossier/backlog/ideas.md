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
