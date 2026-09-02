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
  cave name, not by number. **Widened 2026-09-01**: `photos process` now also produces
  `SB_<broj>_…` copies inside the intake leaves, so the mover has two sources and one job —
  move into `!!Fotografije ulaza` and swap the `SB_<Redni broj>` prefix for the katastarski
  broj. That is the last step of 2.1d.
- 2026-08-26 — ~~give **sudjelovanje** its own Power Query view~~ → done by the user
  2026-08-28 (`S_v2_1`, sheet *Sudjelovanje*, same keyword the tool matches). Still open from
  that idea: tighten the Nesređeni filter to a word-boundary match on "ponor", which today
  drags in 8 unrelated rows.
- 2026-08-26 — ~~the 2.1d processor itself (downsize to ~1920 px / ~1.5 MB) is still to be
  written~~ → done 2026-09-01: `cavedossier photos process <Redni broj>` works per cave off
  its intake leaf and writes downsized `SB_<broj>_<Ime>_<Autor>_<n>.jpg` COPIES (Pillow, the
  `karta` extra). Still open from it: settle the **optimal output resolution** — the command
  writes copies precisely so 1920 px can be revisited (`--long-edge N --overwrite` re-cuts),
  and once it is settled the copies can replace the originals instead.
- 2026-08-26 — ~~once intake lands, wire `archive/izjave.py` scope rules into gating: a
  locality-scoped izjava must not satisfy a cave outside that Lokalitet~~ → done
  2026-08-30, without waiting on intake: the izjave dir got its own gather step
  (`Source.STATEMENTS`) and the scope rule blocks gate 1 via the new people
  registry (`people/`, `data/people/registry.json`).
- 2026-08-30 — upgrade token-form registry entries (`ABahović`) to full `First Last`
  names as they are learned — full names are what match an OSZ's spelling. `people
  check` section 3 (SB autori izvan registra) is the standing worklist: 28 real
  `N.Surname` authors after the author-vs-finder criterion landed (finders — bare
  first names, full names — are exempt from izjave and not swept). Top candidates:
  `S.Antolič` 21× (curated alias for `SKapidžić-Antolič`?), `Z.Gal` 6×,
  `B.Tadić` 2× (the SUE 575 case).
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
- 2026-08-30 — **Pristup prefill, the smart successor** (user): today's
  `config/pristupi.yaml` matches on a hardcoded (Najbliže mjesto, Lokalitet)
  pair (first rule: Veprinac/Ćićarija). The real solution is geographic —
  e.g. cluster the archive's existing OSZ approach texts by entrance
  coordinates (geoclustering model over parsed `Položaj i pristup` sections)
  so a new cave inherits the shared approach of its cluster automatically,
  with the last-turns part left to the recorder.
- 2026-08-30 — promote the session's scratch sweep harness (loads SB once, runs
  both geo finders over a stratified cave sample, prints a compact table + notes)
  into a real `cavedossier geo sweep [--limit N]` command — it found three real
  bugs in one run and is the natural data-quality report for the finders.
- 2026-08-30 — the three karta re-runs this session each allocated a fresh
  georef.hr point ID for the same caves (format migration) — the
  detect-existing-point idea above (2026-08-30, `--force` litter) got more urgent.
- 2026-08-30 — extend the documentation audience split (agent `_INDEX.md` /
  operator `README.md` / `docs/design-decisions.md`) to
  `features/csx-to-survey-pipeline` — done for cave-dossier this session; the
  csx feature's README + reference/ tree grew the same way and would benefit
  from the same operator-vs-agent separation.
- 2026-08-30 — **productionization** (user): dev is this repo on the personal
  PC, prod is the registry Drive where non-developer users work — eventually
  the tools must run FROM the prod side: distributable entry points (scripts /
  bundled runtime), cloud copies on the Drive of `data/geo/` + the OSZ template,
  and a non-developer setup guide. Consideration documented in ARCHITECTURE.md
  §"Dev vs prod" (with the portability rules to keep NOW); promote to a real
  work item when its time comes.
- 2026-09-01 — **Zaštićena područja layer → Lokalitet from protected-area
  containment** (user): add Croatian protected-area polygons (nacionalni
  parkovi, parkovi prirode, regionalni parkovi, značajni krajobrazi, park-šume,
  posebni rezervati, spomenici prirode + Natura 2000 if useful) to
  `data/geo/` as a `zasticena_podrucja.gpkg` (EPSG:3765 like every other vector
  layer), and let `geo locate` do a point-in-polygon of the entrance against it.
  When the entrance falls **inside** a protected area, that area's name becomes
  (or annotates) `Lokalitet` — e.g. an entrance inside PP Učka yields
  `Lokalitet = Park prirode Učka` — so `cavedossier osz prefill` writes it
  instead of falling back to the nearest RGI toponym.
  Open points to settle when this is picked up:
  * **Source + licence.** Bioportal / Zavod za zaštitu okoliša i prirode
    (Ministarstvo) publishes the registry of protected areas + Natura 2000 as
    WFS/SHP; needs the same provenance + attribution row in `data/README.md`
    that DGU layers have, and a branch in `geo/provision.py::fetch_data`
    (local copy → download → skip fail-soft), since it is a **different
    publisher than DGU** and cannot ride the existing AU/RGI paths.
  * **Precedence.** Must respect the standing 2.1b rule (design-decisions):
    **SB wins** — never overwrite a filled `Lokalitet`, only annotate when the
    containment disagrees. For an empty cell, decide the order between the
    protected area (containment, 0 m) and today's `geo-rgi` nearest-toponym
    fill (`_LOCALITY_APPEND_RADIUS_M = 1500`); containment is the stronger
    evidence and should probably win, with a new source label (`geo-zasticeno`)
    so `osz prefill` can show provenance the way it does for `geo-rgi`.
  * **Overlaps.** Protected areas nest (a spomenik prirode inside a park
    prirode; Natura 2000 sites overlap everything) — pick a category ranking
    or emit the most specific hit and list the rest as a note.
  * **Beyond Lokalitet.** Containment is also directly useful for the OSZ /
    CroSpeleo `Zaštita` question and for the dossier gating (a cave in a
    national park implies permit/reporting obligations) — worth exposing on
    `LocalityFinding` as its own field rather than only folding it into the
    Lokalitet string.

- 2026-09-01 — **settle the entrance-photo output resolution.** `photos process` ships at
  1920 px / 1.5 MB and writes copies precisely so this stays open; `--long-edge N
  --overwrite` re-cuts a cave for comparison. Once settled, decide whether the copies
  replace the originals in the intake leaf instead of sitting beside them.
- 2026-09-01 — **`photos process --all` / batch sweep**: process every cave whose intake
  leaf holds unprocessed photos, and every cave with something still in the za-istražit
  queue. Today it is one Redni broj at a time; the queue check already knows how to spot
  the second group.
- 2026-09-01 — **HEIC support** (`pillow-heif`): `.heic` sources are reported and skipped
  today. Not a dependency on purpose — add it if phone photos start arriving that way.
- 2026-09-01 — `locate_filled_osz` says "nema (jednoznačan) OSZ .docx" even when the leaf
  has NO .docx at all (seen on SB 811). Harmless but reads oddly next to the ambiguity
  note — split the two messages.
- 2026-09-01 — the entrance-photo author currently comes only from the OSZ. When a cave has
  no zapisnik, `Fotografirali` in a legacy zapisnik and the intake folder's own author
  suffix (`SB_1220_…_Flavio`) are both plausible fallbacks — but both are guesses, so this
  needs the user's rule before it is wired.

- 2026-09-02 - **prod: bundled Python runtime** (Windows embeddable + get-pip, or a frozen
  build): removes the one-time "install Python 3.11+" step the launchers now guide the
  operator through. Weigh against the maintenance cost per Python bump; today the guided
  path is the deliberate choice.
- 2026-09-02 - **prod: wheel cache on the Drive** so first-run setup works without PyPI
  (fully offline machines). `pip download` per release into the version dir; setup falls
  back to PyPI when absent.
- 2026-09-02 - **prod: update notice in the launcher** - an old-version launcher (or a
  desktop shortcut to one) could detect a newer `cavedossier_*_v*.bat` in its folder and
  say so before running. Today the only signal is the filename in the folder.
- 2026-09-02 - **prod: cleanup of superseded local installs** - each version installs to
  its own `%LOCALAPPDATA%\CaveDossier\v<X>` and old ones linger (~1 GB each with venv +
  geo data). A new version's setup could offer to delete older v-dirs.
- 2026-09-02 - ~~**prod: karta on operator machines?**~~ DONE the same day (v1.2,
  user decision): setup installs [karta] + Chromium, .env gets the shared login;
  see design-decisions "Prod launchers".
