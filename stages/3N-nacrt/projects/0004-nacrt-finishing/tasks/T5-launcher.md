# T5 — the KORAK 3 launcher: `csurvey_3_dovrsi_nacrt.bat`, and the rescue becomes KORAK 9

Paste everything below the line into a fresh Claude Code session opened in
`SurveyScraper5`. Report the result back in the research session (project 0004). T4, T1, T2
and T3 are committed and validated end to end on SB 1103; this is the last task of the project.

---

You are working in the SurveyScraper5 repo (read `CLAUDE.md` first, then `prod/README.md` and
`prod/drive-layout.md`; sibling repos are read-only and not needed). This is task **T5** of
project 0004. Read: `stages/3N-nacrt/projects/0004-nacrt-finishing/brief.md` §3.2 and the T5
entry of §3.3, `tasks/T1-T3-handoff.md` §2, §3 and **§6** (paste-in facts — they are accurate),
`stages/3N-nacrt/production/tdx-processing-protocol.md`, `prod/build_csx_kit.py`,
`prod/csx_templates/*.template` (copy the shape of `csurvey_2_dovrsi_uvoz.bat.template`),
`prod/build_prod.py` (`PROD_COMMANDS`) and `prod/prod_templates/bootstrap.ps1.template`
(`switch ($Command)`), and `prod/tests/`. Follow the `/feature-dev` rules: Croatian operator
text, no diacritics in `.bat` files (real diacritics in `PROCITAJ_ME.txt`, UTF-8 BOM — both are
enforced at build time), fail-soft, dev/prod portability, docs are part of the work.

## The user's decisions (2026-09-20) — implement, do not re-litigate

1. **Numbering.** The finishing step is **KORAK 3**: `csurvey_3_dovrsi_nacrt.bat`. The rescue
   launcher moves **out of the running order** to **KORAK 9**: rename
   `csurvey_3_oporavi_iz_zipa.bat.template` → `csurvey_9_oporavi_iz_zipa.bat.template` and every
   mention (`build_csx_kit.py` lists, the `PROCITAJ_ME` guide, the protocol doc, the
   `tdx-processing-protocol.md` file table, `prod/README.md`, `prod/drive-layout.md`, the
   3N production README). The guide's wording: KORAK 9 is a repair used only when a csx is
   broken, not a step; keep it at the bottom of the guide.
2. **Plan placement** on the composed page stays as it is (ink-centred; the furniture balances
   the cave). Do not touch `compose.py`.
3. `/` cells stay as settled (Broj pločice, Ekipa).

## What to build

### 1. `prod/csx_templates/csurvey_3_dovrsi_nacrt.bat.template`

Same tokens and structure as `csurvey_2_dovrsi_uvoz.bat.template` (`@VERSION@ @DATE@ @COMMIT@
@PAYLOAD@ @TOOLS@`, the five-rung `set "TOOLS="` search, the header, the runtime footer). Flow:

1. Ask for the Redni broj (or accept dragged `_lt` files), resolve the leaf with `sb_select`
   and list candidate `*_lt.csx|csz` files (exclude `_lt_fin`), as KORAK 2 does for its inputs.
2. `python nacrt_finish.py <file> ` — **show the layout menu** (Enter = proposal), since the
   operator is at the keyboard in a double-clicked window; `--yes` only when files were
   dragged onto the launcher (unattended). Print its report.
3. `python csurvey_driver.py finish <file>_lt_fin.<ext> -o <leaf>` — on `DriverError` (cSurvey
   not installed, printer missing, calculate/print failure) print the one-line reason and the
   fallback in Croatian: open `<file>_lt_fin.<ext>` in cSurvey, File › Print, plan and profile,
   PDF printer — and **stop cleanly** (exit 0 with the message, not a stack trace).
4. `cavedossier nacrt <broj>` through the cavedossier bootstrap that already lives in the same
   Drive folder. Add `"nacrt": ("nacrt",)` to `PROD_COMMANDS` in `build_prod.py` **and** a
   `'nacrt'` branch in `bootstrap.ps1.template`'s `switch ($Command)` (label in Croatian:
   `Nacrt - slozi tlocrt i profil na sastavnicu (cSurvey ruta)`), so the prod bundle gains a
   `cavedossier_nacrt_v<X>.bat` like the other three. The csx launcher calls that launcher by
   name (find it beside itself: `cavedossier_nacrt_v*.bat`, newest version) and, when it is
   absent or fails, says so and stops with the PDFs already in the leaf.
5. Footer: what was written (`_lt_fin`, the two PDFs, `_dimenzije.json`, `SB_<broj>_nacrt.pdf`)
   and what to do next (check the page, then the archivist's steps).

### 2. `build_csx_kit.py`

Add the new template to the launcher list, rename the rescue, keep the five KORAK 3 tools in
`TOOLS`. Bump the kit version (`v1.1`) and the date. `--publish` is **not** to be run by you;
build to staging and show the tree.

### 3. Guide + docs

- `csurvey_0_PROCITAJ_ME.txt.template`: a KORAK 3 section in the same plain Croatian as the
  others (what it does, the menu, the fallback when cSurvey is missing, the files it leaves,
  that `SB_<broj>_nacrt.pdf` is the finished Nacrt), and the rescue section renumbered to 9 and
  moved to the end.
- `stages/3N-nacrt/production/tdx-processing-protocol.md`: promote step 5 from *in validation*
  to the standing protocol, drop the numbering-clash note, renumber the rescue.
- `prod/README.md`, `prod/drive-layout.md`, `stages/3N-nacrt/production/README.md`,
  `docs/commands.md`: the new launcher and the renamed rescue.
- `pipeline.yaml` if the doctor asks for it.

### 4. Tests

`prod/tests/`: extend the existing csx-kit tests (see how they render templates) — the new
template renders with every token replaced, contains no non-ASCII byte, the rescue template
is gone under its old name and present under the new one, `TOOLS` carries the five KORAK 3
files, `PROD_COMMANDS` has `nacrt` and the bootstrap template has its branch. Run
`python -m pytest -q` (whole repo, green) and `python tools/pipeline_doctor.py` (0 fail).

Then a **real dry run on this machine**: `python prod/build_csx_kit.py` (staging), then run the
staged `csurvey_3_dovrsi_nacrt.bat` on SB 1103 from a `cmd` window (drag the leaf's `_lt.csx`
onto it or type `1103`), and paste the console output. The leaf already holds KORAK 3 outputs
from earlier runs; the finisher skips what exists and warns, the driver reprints, `nacrt`
refuses to overwrite a file that is not ours — all expected, report what you see.

### 5. Close-out

Append a dated entry to `stages/3N-nacrt/projects/0004-nacrt-finishing/log.md`. Do **not**
flip the brief to `closed` and do **not** commit — the research session closes the project
after the second-machine and second-cave checks.

Finish by printing: the staged kit tree, the launcher's console output on SB 1103, the pytest
summary line, and the doctor's last line.
