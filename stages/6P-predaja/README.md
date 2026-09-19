# 6P — Predaja

**Delivery and SB write-back.** Designed, not built.

There is no code here yet — and that is the point of giving it a folder now.
The stage exists as its two design records, so the shape of the only WRITE
milestone is written down and reviewable before anything touches the workbook.

## What it will do

When a cave passes gate 1, `cavedossier deliver <broj>` will:

1. Allocate its **katastarski broj SUE**.
2. File every artifact under that number into the archive Drive dirs —
   the Nacrt, the OSZ, the entrance photos.
3. Write the gathered data back into SB and move the row into *Istraženi*.

The [4F-fotografije](../4F-fotografije/README.md) **mover** rides along: the
downsizing and `SB_<broj>_…` naming are already done, but filing photos under
`<padded SUE>_…` can only happen once that number exists.

## Why it is the only WRITE milestone

Everything before this point produces **review lists** that a person carries out
in Excel. SB is a live, macro-heavy, shared workbook and the satellite sheets are
typed into in the field; neither tolerates an automatic write. Reads are
openpyxl, where a save is physically impossible. The only safe write path is
xlwings / Excel COM — Excel itself does the saving — which is why write-back is
deferred to one deliberate milestone with its own rehearsal protocol rather than
being sprinkled across the stages that discovered the data.

See [`EXCEL_WORKBOOK_SAFETY.md`](../0P-platform/docs/EXCEL_WORKBOOK_SAFETY.md).

## Where things are

- Delivery design: [`docs/m6-delivery-design.md`](docs/m6-delivery-design.md) —
  the last gate, katastarski-broj allocation, the rename-and-file rules
- Write-back mechanics: [`docs/sb-write-back-design.md`](docs/sb-write-back-design.md)
- The Drive dirs it will write into: [`prod/drive-layout.md`](../../prod/drive-layout.md)

## Status

**Not started.** Designed only. Five open questions in the delivery design are
still waiting on the user.
