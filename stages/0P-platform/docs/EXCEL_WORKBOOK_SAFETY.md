<!-- Copied 2026-08-16 from crospeleo-automation/docs/EXCEL_WORKBOOK_SAFETY.md (read-only reference repo).
     Module paths inside refer to that repo; the principles apply verbatim to our port
     src/cave_dossier/sb/safe_io.py. See docs/PORTING.md. -->
<!-- doctor:skip-links -->  <!-- verbatim copy — its links point at the source repo -->


# Excel Workbook Safety — Guideline for AI Agents

> **Read this before writing any code that touches `chp_portfolio_master_v1.2.xlsx`.**
> Several iterations of this pipeline broke either Stock Connector links or live formulas in the master workbook. Every breakage cost a manual rebuild of state that lives nowhere else (broker connections, hand-tuned formulas, linked data types). The patterns below are *the only patterns* that have survived production use — when in doubt, copy a working script verbatim rather than improvising.

---

## 1. The setup you are working against

| Thing | Value |
|---|---|
| **Workbook** | `chp_portfolio_master_v1.2.xlsx` |
| **Location** | `G:/My Drive/Financials/chp_portfolio_master_v1.2.xlsx` (Google Drive for Desktop on Windows; the `G:` drive is the Drive virtual mount) |
| **Why Google Drive Desktop** | We deliberately do not use the Google Drive *API* / `gspread` / OAuth. The workbook is treated as a local file that Drive transparently syncs. This avoids API auth, rate limits, and the loss of native Excel features that occurs when round-tripping through Google Sheets. |
| **Live add-ins inside the workbook** | **Stock Connector** (registers a webextension at `xl/webextensions/*` that pulls live broker positions), **linked data types** (Wolfram / Stocks data types in the header rows), and a large web of cell formulas that depend on Stock Connector output. |
| **Sheets the pipeline writes** | `Screener_Import` (05), `Rebalance` (06B), `Priority Queue` (06C). Everything else (`Portfolio`, `Portfolio Summary`, `Performance`, etc.) is **hand-curated by the user** and must be left alone. |
| **Sheets the pipeline reads** | `Portfolio` (06B/06C/06D) and `Portfolio Summary` (06D for cash). Read-only. Never re-saved. |

**Why this matters:** Every working sync script in this repo follows the same split-responsibility design — Python computes and styles into a *temporary* workbook, Excel itself performs the *final save* on the master file. Skipping that split is what destroys the workbook.

---

## 2. The two failure modes that prompted everything

### 2a. openpyxl strips `xl/webextensions/*` on every save → **Stock Connector dies**

`openpyxl` does not understand the webextension XML inside the `.xlsx` zip. On every `wb.save()` it silently drops the entire `xl/webextensions/` directory along with its `_rels` and `[Content_Types].xml` entries — and prints a `UserWarning` no one ever sees in CI logs. The next time the user opens the workbook, the Stock Connector add-in is gone, all linked positions go to `#REF!`, and the broker connection has to be reconfigured by hand.

**Things that look like fixes but aren't:**
- A zip-level regex patch to re-inject `xl/webextensions/` after `wb.save()` was tried in early 08B and 08C (see `implementations/2026_04_21_08C_entry_priority.md`). It is fragile because openpyxl also rewrites `_rels` and `[Content_Types].xml` in ways the regex cannot anticipate. **Do not revive this approach.**
- `keep_vba=True` does nothing for webextensions — that flag covers VBA only.
- A whitelisted `wb.save()` path does not exist. There is no openpyxl knob that preserves webextensions.

**The only fix:** never let `openpyxl` save the master workbook. See §3.

### 2b. `data_only=True` + `wb.save()` → **every formula becomes its cached value**

`openpyxl.load_workbook(path, data_only=True)` returns the *last cached result* of each formula instead of the formula string. If you then save that workbook, openpyxl writes back the cached numbers, permanently overwriting every formula. The workbook becomes a dead snapshot — every formula gone, every linked data type gone.

**The only safe rule:** a workbook opened with `data_only=True` is **read-only** for the rest of its lifetime. Never call `.save()` on it. Use it to extract numbers, then close it.

---

## 3. The architecture: split read/build/save across two libraries

Every working script in this repo follows the same three-phase pattern:

```
            ┌──────────────────────────────────────────────────────────┐
            │  Phase 1 — READ from master                              │
            │  openpyxl, data_only=True, read_only=True (when possible)│
            │  Extract values, never save.                             │
            └─────────────────────┬────────────────────────────────────┘
                                  │
                                  v
            ┌──────────────────────────────────────────────────────────┐
            │  Phase 2 — BUILD in temp file                            │
            │  openpyxl writes a styled sheet to a throw-away .xlsx in │
            │  the OS temp dir.  No add-ins exist in this temp file,   │
            │  so openpyxl can save it freely.                         │
            └─────────────────────┬────────────────────────────────────┘
                                  │
                                  v
            ┌──────────────────────────────────────────────────────────┐
            │  Phase 3 — INJECT + SAVE master                          │
            │  xlwings (Excel COM) opens BOTH master and temp,         │
            │  copies the sheet across, deletes the old version,       │
            │  calls master.save().  Excel itself performs the save,   │
            │  preserving Stock Connector, linked data types, formulas.│
            └──────────────────────────────────────────────────────────┘
```

Two valid variants of Phase 3:

- **Variant A — temp-build then inject** (used by [06B_rebalance_sync.py](../06_allocation_dashboard/06B_rebalance_sync.py) and [06C_entry_priority.py](../06_allocation_dashboard/06C_entry_priority.py)). Best when the sheet has heavy openpyxl-driven styling (color scales, conditional formats, complex borders). openpyxl's styling API is richer than xlwings'.
- **Variant B — direct COM write** (used by [05_run_screener_and_sync.py](../05_combined_screener/05_run_screener_and_sync.py)). Best when the sheet is mostly raw data with simple per-cell coloring. Uses `xlwings.Range(...).value = [headers] + rows` to bulk-write in one COM round-trip, then COM API for styling. Faster for large data tables.

**Both variants share the same critical rule: openpyxl never opens the master workbook for writing.**

---

## 4. The canonical code patterns — copy these verbatim

### 4.1 Read pattern (any script that needs values from the master)

```python
import openpyxl
from pathlib import Path

EXCEL_PATH = Path("G:/My Drive/Financials/chp_portfolio_master_v1.2.xlsx")

if not EXCEL_PATH.exists():
    print(f"  ERROR: Workbook not found: {EXCEL_PATH}", file=sys.stderr)
    print("  Check that Google Drive Desktop is running and the file is synced.")
    sys.exit(1)

# data_only=True returns cached values, NOT formula strings.
# read_only=True is even safer — it makes accidental saves impossible.
wb = openpyxl.load_workbook(EXCEL_PATH, data_only=True, read_only=True)
ws = wb["Portfolio"]
for row in ws.iter_rows(min_row=3, values_only=True):
    eu_ticker  = row[1]
    us_ticker  = row[2]
    weight_pct = row[13]
    # ... process values ...
wb.close()
# DO NOT call wb.save().  Ever.  Even an `if False: wb.save()` left in source
# is a footgun — delete it.
```

Working reference: [06B_rebalance_sync.py:239–265](../06_allocation_dashboard/06B_rebalance_sync.py#L239-L265) and [06D_ctolarsson_sync.py:184–192](../06_allocation_dashboard/06D_ctolarsson_sync.py#L184-L192).

### 4.2 Build-then-inject pattern (Variant A — recommended for styled sheets)

```python
import os, tempfile, shutil
import openpyxl

EXCEL_PATH = Path("G:/My Drive/Financials/chp_portfolio_master_v1.2.xlsx")
SHEET_NAME = "Rebalance"

# --- Phase 2: build into a temp file ---
fd, tmp_path = tempfile.mkstemp(suffix=".xlsx")
os.close(fd)

try:
    tmp_wb = openpyxl.Workbook()
    tmp_ws = tmp_wb.active
    tmp_ws.title = SHEET_NAME

    # Free to do whatever openpyxl can do here — no add-ins in this temp file.
    write_my_sheet(tmp_ws, ...)
    tmp_wb.save(tmp_path)

    # --- Phase 3: inject into master via Excel COM ---
    _inject_sheet_xlwings(tmp_path)
finally:
    if os.path.exists(tmp_path):
        os.unlink(tmp_path)


def _inject_sheet_xlwings(tmp_xlsx: str) -> None:
    """Copy the temp sheet into master via xlwings; Excel saves master."""
    import xlwings as xw

    app = xw.App(visible=False, add_book=False)
    wb_master = None
    wb_temp   = None
    try:
        wb_master = app.books.open(str(EXCEL_PATH))
        wb_temp   = app.books.open(tmp_xlsx)

        sheets_before = {s.name for s in wb_master.sheets}
        src = wb_temp.sheets[0]

        # Place after the existing sheet of the same name (or after a known
        # neighbour, or first if neither exists).
        if SHEET_NAME in sheets_before:
            src.api.Copy(After=wb_master.sheets[SHEET_NAME].api)
            wb_master.sheets[SHEET_NAME].delete()
        elif "Screener_Import" in sheets_before:
            src.api.Copy(After=wb_master.sheets["Screener_Import"].api)
        else:
            src.api.Copy(Before=wb_master.sheets[0].api)

        # Excel may rename a copied sheet to "Rebalance (2)" on conflict.
        # Find whichever sheet is NEW and rename it to the canonical name.
        for s in wb_master.sheets:
            if s.name not in sheets_before:
                s.name = SHEET_NAME
                break

        wb_temp.close()
        wb_temp = None
        wb_master.save()    # <-- Excel performs the save. Add-ins survive.
    finally:
        for book in (wb_temp, wb_master):
            if book is not None:
                try:
                    book.close()
                except Exception:
                    pass
        app.quit()
```

Working reference: [06B_rebalance_sync.py:163–223](../06_allocation_dashboard/06B_rebalance_sync.py#L163-L223). Identical shape in 06C.

### 4.3 Direct COM write pattern (Variant B — recommended for raw data tables)

```python
import xlwings as xw

app = xw.App(visible=False, add_book=False)
try:
    wb = app.books.open(EXCEL_PATH)

    sheet_names = [s.name for s in wb.sheets]
    if SHEET_NAME not in sheet_names:
        ws = wb.sheets.add(SHEET_NAME)
    else:
        ws = wb.sheets[SHEET_NAME]
        # CRITICAL: clear ONLY the range we owned last run, not the whole sheet.
        # `ws.clear()` would nuke any Stock Connector columns the user added
        # to the right of our data.
        try:
            last_row = ws.used_range.last_cell.row
            last_col = ws.used_range.last_cell.column
            clear_cols = max(last_col, n_cols)
            ws.range((1, 1), (last_row, clear_cols)).clear_contents()
            ws.range((1, 1), (last_row, clear_cols)).color = None
        except Exception:
            ws.clear_contents()

    # One bulk COM call is much faster than per-cell.
    ws.range("A1").value = [headers] + data

    # Style via the Excel COM API (ws.api), NOT openpyxl.
    _apply_sheet_style(ws.api, df_export)

    wb.save()
finally:
    try: wb.close()
    except Exception: pass
    app.quit()
```

Working reference: [05_run_screener_and_sync.py:271–361](../05_combined_screener/05_run_screener_and_sync.py#L271-L361).

---

## 5. The recurring sub-failures and how they were fixed

Each one of these caused a real breakage in production. Treat them as required reading.

### 5.1 `delete_rows()` leaves stale merge XML → "file is corrupt" recovery dialog

`openpyxl` does not clear the sheet's merge-cell registry when rows are deleted. The next time Excel opens the file it sees merge ranges that point to non-existent cells and shows the file-recovery dialog (which scares users into thinking the workbook is dying).

**Fix:** unmerge every range explicitly *before* `delete_rows()`.

```python
for merge_range in list(ws.merged_cells.ranges):
    try:
        ws.unmerge_cells(str(merge_range))
    except KeyError:
        pass  # data_only workbooks omit shadow cells; the registry entry is
              # cleared before the error fires, so this is safe to ignore.
ws.delete_rows(1, ws.max_row + 1)
```

Working reference: [06B_rebalance_sync.py:495–500](../06_allocation_dashboard/06B_rebalance_sync.py#L495-L500), [06C_entry_priority.py:627](../06_allocation_dashboard/06C_entry_priority.py#L627).

### 5.2 Numbers stored as formatted strings → cells unsortable, unfilterable, unusable in formulas

Writing `f"{val*100:.2f}%"` to a cell stores the **string** `"2.42%"`, not the number `0.0242`. The cell can no longer be sorted numerically, can't be filtered with `>`, and breaks every downstream formula that tries to multiply or sum it.

**Fix:** always write the raw numeric value and apply `number_format` to the cell.

```python
c.value         = fraction_value          # e.g. 0.0242
c.number_format = "0.00%"                 # Excel displays "2.42%"
```

Common formats actively used in this project:
| Use | Format |
|---|---|
| Weight fractions (`Current_Wt`, `Target_BW`, `weight_vol_adj`) | `"0.00%"` |
| ATR stop (store as fraction `atr_pct / 100`) | `"0%"` |
| Drift in percentage points | `'+0.00"pp";-0.00"pp";0"pp"'` |
| `COMPOSITE_SCORE` | `"0.0"` |

Working reference: [06B_rebalance_sync.py:64–76](../06_allocation_dashboard/06B_rebalance_sync.py#L64-L76).

### 5.3 `ws.clear_contents()` nukes Stock Connector columns the user added

`ws.clear()` and `ws.clear_contents()` wipe the **entire sheet**. Users routinely add Stock Connector columns to the right of our data. Wiping them silently destroys hours of broker-link configuration.

**Fix:** clear only the rectangular range your script owns. See the snippet in §4.3.

### 5.4 AutoFilter fails when xlwings runs `visible=False`

`ws.api.AutoFilter(...)` raises a COM exception when Excel is hidden. The previous workaround (toggle visibility on, run AutoFilter, toggle off) caused the Excel window to flash on the user's screen mid-pipeline-run.

**Fix:** skip AutoFilter from code. Tell the user to re-enable manually with `Ctrl+Shift+L` if needed.

```python
# AutoFilter: skipped — COM AutoFilter fails in visible=False mode.
# Re-enable manually in Excel with Ctrl+Shift+L if needed.
```

Working reference: [05_run_screener_and_sync.py:343–344](../05_combined_screener/05_run_screener_and_sync.py#L343-L344).

### 5.5 The `_DEBUG` mode pattern — your safety net during development

Every script that writes to the master defaults to `_DEBUG = True` for the first few iterations and writes to a `_DEBUG.xlsx` copy beside the master. Only flip to `False` (or pass `--live`) once the output has been visually verified. This pattern has saved the master workbook multiple times.

```python
_DEBUG      = True                                       # default while developing
_DEBUG_PATH = EXCEL_PATH.with_stem(EXCEL_PATH.stem + "_DEBUG")
save_path   = _DEBUG_PATH if _DEBUG else EXCEL_PATH

if _DEBUG:
    shutil.copy2(tmp_path, _DEBUG_PATH)   # bypass xlwings — just dump the temp
else:
    _inject_sheet_xlwings(tmp_path)       # production path
```

Working reference: [06B_rebalance_sync.py:32–36](../06_allocation_dashboard/06B_rebalance_sync.py#L32-L36), [06C_entry_priority.py:10–11](../06_allocation_dashboard/06C_entry_priority.py#L10-L11).

### 5.6 `read_only=True` makes Phase-1 reads doubly safe

Pair `data_only=True` with `read_only=True` whenever you can. The `read_only` mode physically prevents `wb.save()` from succeeding, so even a stray save call cannot damage the file. Used by 06D for exactly this reason: [06D_ctolarsson_sync.py:184](../06_allocation_dashboard/06D_ctolarsson_sync.py#L184).

---

## 6. Google Drive Desktop specifics

### 6.1 Path detection

The hardcoded path is `G:/My Drive/Financials/chp_portfolio_master_v1.2.xlsx`. If a script needs to be portable to other machines, follow the discovery pattern in 05:

```python
EXCEL_PATH = r'G:\My Drive\Financials\chp_portfolio_master_v1.2.xlsx'

_GDRIVE_CANDIDATES = [
    r'G:\My Drive',
    r'C:\Users\Lovel\Google Drive',
    r'C:\Users\Lovel\My Drive',
    os.path.expanduser(r'~\Google Drive'),
    os.path.expanduser(r'~\My Drive'),
]
```

Reference: [05_run_screener_and_sync.py:43–65](../05_combined_screener/05_run_screener_and_sync.py#L43-L65).

### 6.2 The pre-flight existence check

If the file does not exist, the most common cause is **Google Drive Desktop is not running** or the workbook is set to "online only" rather than "available offline". Always print a clear pointer rather than letting `openpyxl` raise a generic FileNotFoundError:

```python
if not EXCEL_PATH.exists():
    print(f"  ERROR: Workbook not found: {EXCEL_PATH}", file=sys.stderr)
    print("  Check that Google Drive Desktop is running and the file is synced.")
    sys.exit(1)
```

### 6.3 Conflict files

If two devices touch the file at once, Drive creates a sibling like `chp_portfolio_master_v1.2 (1).xlsx`. Our scripts only read/write the canonical name. Educate the user to merge any conflict file by hand before the next run; never auto-resolve.

### 6.4 The user must close Excel before xlwings runs

If Excel has the master open in the foreground, xlwings will either fail or attach to the user's session and surface visible UI flicker. Make this expectation explicit in any script's docstring, and consider checking for a lock file (`~$chp_portfolio_master_v1.2.xlsx`) before launching xlwings:

```python
lock = EXCEL_PATH.with_name("~$" + EXCEL_PATH.name)
if lock.exists():
    print("  ERROR: master workbook is open in Excel. Close it and retry.")
    sys.exit(1)
```

---

## 7. Pre-flight checklist for any new script that touches the workbook

Before writing the first line of code, confirm:

1. **Are you reading or writing?** Reads use openpyxl `data_only=True, read_only=True`. Writes follow §4.2 or §4.3 only.
2. **Which sheets?** If the sheet is one the user hand-edits (`Portfolio`, `Portfolio Summary`, `Performance`), reads only. New writes go to a sheet name the pipeline owns.
3. **Are you preserving Stock Connector?** If the answer involves `wb.save()` from openpyxl on the master path, stop and rewrite using §4.2.
4. **Are you clearing the right range?** Never `ws.clear()` on the master. Only clear the rectangle your script owns.
5. **Are values stored as numbers?** No `f"{x:.2f}%"` strings into cells.
6. **Is `_DEBUG = True` your default?** First N iterations write to `_DEBUG.xlsx`. Flip to `False` only after a visual check.
7. **Are merges unmerged before `delete_rows()`?**
8. **Does the script print a clear "Drive not running" hint when the file is missing?**
9. **Does the script require Excel to be closed?** State it in the docstring.
10. **xlwings is in `requirements.txt`?** It is — just confirm your script imports it inside the function (lazy import) so a non-Windows user can at least run the read-only paths.

---

## 8. Anti-patterns — never do these

- ❌ `openpyxl.load_workbook(EXCEL_PATH).save(EXCEL_PATH)` — destroys Stock Connector immediately.
- ❌ `wb = openpyxl.load_workbook(EXCEL_PATH, data_only=True); wb.save(...)` — converts every formula to its cached value, permanently.
- ❌ Re-injecting `xl/webextensions/` via a zip-level regex patch after `wb.save()` — fragile, breaks on any openpyxl version bump.
- ❌ `ws.clear()` on the master sheet — wipes user-added Stock Connector columns to the right.
- ❌ `ws.delete_rows(1, ws.max_row + 1)` without first unmerging — file-recovery dialog on next open.
- ❌ Writing percent strings (`"2.42%"`) instead of fractions + number_format.
- ❌ Calling `xw.App(visible=False)` and then `AutoFilter(...)` — fails silently or noisily.
- ❌ Pushing the workbook through Google Sheets / `gspread` / Drive API — loses Stock Connector, linked data types, conditional formats, and every native Excel feature this workbook depends on.
- ❌ Auto-resolving Drive conflict files (`... (1).xlsx`) from code — let the user merge by hand.
- ❌ Defaulting a new development script to write to the live master. Always start `_DEBUG = True`.

---

## 9. Reference implementations (pick one and copy its shape)

| Pattern needed | Read this file |
|---|---|
| Heavy openpyxl styling, then save to master | [06_allocation_dashboard/06B_rebalance_sync.py](../06_allocation_dashboard/06B_rebalance_sync.py) |
| Same shape, slightly different sheet content | [06_allocation_dashboard/06C_entry_priority.py](../06_allocation_dashboard/06C_entry_priority.py) |
| Bulk data dump, light per-cell coloring | [05_combined_screener/05_run_screener_and_sync.py](../05_combined_screener/05_run_screener_and_sync.py) |
| Pure read pattern (no writes ever) | [06_allocation_dashboard/06D_ctolarsson_sync.py](../06_allocation_dashboard/06D_ctolarsson_sync.py) |

The session logs that explain *why* each pattern landed:

- [implementations/2026_04_21_08C_entry_priority.md](../implementations/2026_04_21_08C_entry_priority.md) — first time the zip-patch approach was abandoned in favour of xlwings.
- [implementations/2026_05_07_06D_ctolarsson_sync.md](../implementations/2026_05_07_06D_ctolarsson_sync.md) — read-only path and Drive cash discovery.
- [implementations/2026_05_08_06D_sync_stabilization.md](../implementations/2026_05_08_06D_sync_stabilization.md) — Portfolio Summary EUR cash, EU ticker fallbacks, Notes column auto-discovery.

---

## 10. When to update this document

Update this file whenever:

- A new failure mode of the master workbook is discovered and worked around.
- A new sheet name becomes pipeline-owned (so other agents know it's safe to overwrite).
- The Google Drive path or the workbook filename changes.
- A new helper for the inject pattern is added (so future scripts can import it instead of copy-pasting).

Then add a one-line dated entry to `PIPELINE_AGENT.md → Recent Changes` noting that this guideline was updated.
