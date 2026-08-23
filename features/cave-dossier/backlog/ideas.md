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

