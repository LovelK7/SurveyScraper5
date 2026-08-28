# SB Power Query views — current filters and proposed edits

The four views over the master table `SO_v2_1` (*Svi objekti*) are the workbook's
own definition of a cave's lifecycle, so `cave_dossier` derives
`LifecycleState` from **these exact filters** rather than from a guess. Extracted
from the live workbook's `Formulas/Section1.m` (2026-08-28); re-extract with:

```powershell
# reads customXml/item1.xml → base64 DataMashup → Formulas/Section1.m
python - <<'PY'
import base64, io, re, struct, zipfile
z = zipfile.ZipFile(r"<path to !Speleo_baza_SUE_v3.0.xlsm>")
raw = z.read("customXml/item1.xml").decode("utf-16")
blob = base64.b64decode(re.search(r">([A-Za-z0-9+/=]{200,})<", raw).group(1))
_, plen = struct.unpack("<II", blob[:8])
print(zipfile.ZipFile(io.BytesIO(blob[8:8 + plen])).read("Formulas/Section1.m").decode("utf-8"))
PY
```

| View | Query | Filter | Rows (live, 2026-08-28) |
|---|---|---|---|
| Istraženi | `IO_v2_1` | `[Katastarski broj SUE] <> null and <> ""` | 885 |
| Za istražit | `ZI_v2_1` | Napomena contains `za istražit` | 185 |
| Nesređeni | `NO_v2_1` | Napomena contains any of 9 keywords | 221 |
| Sudjelovanje | `S_v2_1` | Napomena contains `sudjelovanje` | 77 |

## Proposed: exclude *za istražit* rows from Nesređeni

**Why.** 13 rows carry both markers — `za istražit, 593, istražio SU Ri, treba
ponoviti` matches `ponoviti`, so a cave nobody has explored yet shows up on the
"explored but unfinished" list. `cave_dossier` already resolves this by
precedence (queue flag beats Nesređeni keywords), so after this edit the view
and the tool agree row for row.

**Effect:** Nesređeni 221 → 208.

### Option A — minimal edit

Wrap the existing OR-chain and add one condition in front:

```m
= Table.SelectRows(#"Changed Type", each
    not Text.Contains([Napomena] ?? "", "za istražit")
    and (
        Text.Contains([Napomena], "neistraženo") or Text.Contains([Napomena], "fali nacrt") or Text.Contains([Napomena], "fali zapisnik") or Text.Contains([Napomena], "<5 m") or Text.Contains([Napomena], "puhalica") or Text.Contains([Napomena], "ponor") or Text.Contains([Napomena], "ponoviti") or Text.Contains([Napomena], "nastaviti") or Text.Contains([Napomena], "umjetan objekt")
    ))
```

The `?? ""` guards empty Napomena cells: `Text.Contains(null, …)` returns `null`,
and `not null` is `null`, which would drop the row — harmless here (those rows
were excluded anyway) but the guard makes the intent explicit.

### Option B — same result, easier to maintain

The keyword list becomes data instead of nine repeated calls, and the comparison
is case-insensitive, which matches how `cave_dossier` reads the column:

```m
= Table.SelectRows(#"Changed Type", each
    let
        napomena = Text.Lower([Napomena] ?? ""),
        kljucne  = {"neistraženo", "fali nacrt", "fali zapisnik", "<5 m", "puhalica",
                    "ponor", "ponoviti", "nastaviti", "umjetan objekt"}
    in
        not Text.Contains(napomena, "za istražit")
        and List.AnyTrue(List.Transform(kljucne, each Text.Contains(napomena, _))))
```

Adding or removing a keyword is then a one-word edit to `kljucne`. Note the
`Text.Lower` makes it catch `Neistraženo` too — today no row is spelled that
way, so the result set is identical; it just stops depending on capitalisation.

## Not proposed: word-boundary matching on "ponor"

An earlier note here suggested that `ponor` was over-matching. Checked against
the live workbook: **it is not.** All 5 rows kept in Nesređeni by that keyword
alone use it as a deliberate tag at the start of the Napomena —
`ponor, možda kopati`, `ponor, HGI (IGI), trasiranje`, `ponor`. The keyword is
working as intended; no change needed.
