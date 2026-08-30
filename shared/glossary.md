# Domain glossary (Croatian speleology terms)

Croatian terms are domain identity — keep them as-is in filenames, configs, and
conversation; the codebase around them is English. Pipeline part numbers refer to
[ARCHITECTURE.md](../ARCHITECTURE.md).

| Term | Meaning | Where in the pipeline |
|---|---|---|
| **OSZ** | *Osnovni speleološki zapisnik* — the basic cave record, a per-cave DOCX form aggregating all data | Final product of 2.1b; consumed downstream by crospeleo-automation's OSZ parser |
| **Nacrt** | The survey map / cave plan, delivered as vector PDF | Final product of 2.1a; archive dir `!!Nacrti/` |
| **SB / Speleo baza** | The society's cave registry — live Excel workbook `!Speleo_baza_SUE_v2.4.xlsm` (macro-heavy, shared, on Drive). Rows = every cave discovered + caves to be explored | Part 2.2: source of primary data (coordinates, year), target of write-back (dimensions) |
| **SUE** | *Katastarski broj SUE* — the society's internal cadastre number, the shared filename key across archive dirs (`<SUE>.docx`, `<SUE>.pdf`, `<SUE>*.jpg`) | Row identity in SB; file naming in delivery (M6) |
| **Isječak karte** | Map excerpt — marker-centered topo-map PNG + georeference record text, produced via georef.hr from HTRS96 coordinates | Part 2.1c; embedded in OSZ, attached in cadastre submission |
| **Izjava (za katastar)** | Author statement/consent file (`Izjava_<name>[_<scope>].pdf`), one per drawing/photo author, in its own Drive dir (`!!Izjave za katastar RH/`); linked to people via the **registar osoba** (`features/cave-dossier/data/people/registry.json`) | Dossier gating: missing/wrong-scope statement per author = gate-1 blocker; any named person without one = gate-2 warning |
| **TDX** | Shorthand for the TopoDroid export bundle/workflow | Input to 2.1a |
| **CSX / CSZ** | cSurvey file formats: `.csx` = bare survey XML (what TopoDroid exports), `.csz` = ZIP with `_data.xml` + binary assets | 2.1a interchange formats; never committed to git |
| **HTRS96** | Croatian terrestrial reference system — easting/northing meters (`X HTRS`/`Y HTRS` columns in SB) | Input to isječak karte (2.1c), GPS data in OSZ |
| **georef.hr** | External Croatian georeferencing web tool; mints the georef record + map excerpt | Automated via headed Playwright (2.1c) |
| **TopoDroid** | Android cave-survey app used on the survey phone | Source of `.csx`; part 1 receives its exports via bluetooth |
| **cSurvey** | Windows desktop cave-survey app (VB.NET) processing the survey into the finished map | Engine of 2.1a; read-only reference clone at `../cSurvey` |
| **CroSpeleo** | The national cave cadastre web system (`crospeleo.mingor.hr`) | Downstream only — crospeleo-automation submits there; SurveyScraper5 stops at the archive dirs |
| **Queue dirs** | Drive folders where part 1 (or the manual workflow) drops field data awaiting stage-2 processing | Part 1 → 2.1 handoff (intake contract settled at M2) |
