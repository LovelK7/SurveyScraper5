<!-- PR title: Keep the case of file paths (crash / file not found on case-sensitive file systems) -->
<!-- This file is the PR body as it is (gh pr create --body-file). Patch: fix.patch -->

## Problem

Our club keeps one cSurvey copy and all surveys in a Google Drive folder shared with every member. There
cSurvey fails in two places.

**1. Opening a survey with signs, or importing a TopoDroid file, crashes:**

```text
Ops...unhandled exception...sorry!
Could not find a part of the path 'g:\.shortcut-targets-by-id\1f1bng4lkqcp3bauwgcnwoqsnkdjqo3id\speleo baza sue\!!!digitalizacija\software\csurvey64\objects\cliparts\signs\acqua.svg'.
```

The file exists, at `G:\.shortcut-targets-by-id\1f1bNG4lkQcp3bAuWgcNWOqSnkDjqO3Id\Speleo baza SUE\…\Objects\Cliparts\Signs\acqua.svg`.

**2. Double-clicking a `.csx` in that folder** opens cSurvey, but cSurvey looks for the file under a
lowercased path, which doesn't exist.

## Cause

Both lowercase a full path and then open the file through it.

- `cClipartPlaceholder.New` (`cSurveyPC/cCliparts.vb`) stores the gallery file's path lowercased and loads
  it from there (`sFilename = Filename.ToLower` … `oXml.Load(sFilename)`). `cLayerSigns.CreateSign` also
  passes that lowercased `Filename` on as the new sign's SVG file.
- `cCommandLineParameters` (`cSurveyPC/cCommandLineParameters.vb`) stores a bare parameter, i.e. the file
  Windows passes on a double-click, as a *key*, and keys are lowercased (`sKey = sKey.ToLower`, and again in
  `Add`). `frmMain2` then loads `oCommandLine(0).Key`.

On NTFS this is harmless. Google Drive for desktop, however, mounts a folder shared with you (reached
through `G:\.shortcut-targets-by-id\<id>\`) with a **case-sensitive name**: `Speleo baza SUE` resolves,
`speleo baza sue` does not. Every folder below it is case-insensitive; we checked one path part at a time.

## Fix

**`cCliparts.vb`:** keep the path as given and lowercase only the folder name, as before:

```vb
sFilename = Filename
sFolder = IO.Path.GetFileName(IO.Path.GetDirectoryName(sFilename)).ToLower
```

`Folder` keeps its lowercase value. `Filename` now has the original case. Its only readers open the file
(`oXml.Load` here, `CreateSign` → an SVG-file sign), so they work on any file system, and on NTFS nothing
changes. `pLoadGallery` builds the folder as `objects\cliparts\signs` in lowercase too; that is fine on Drive
because only the shared folder's own name is case-sensitive, so it is left alone.

**`cCommandLineParameters.vb`:** a bare parameter becomes `filename=<path>`. Its value keeps its case,
and `frmMain2` already opens `filename=`:

```vb
If p < 0 Then
    sKey = "filename"
    sValue = sParam
```

The only keys cSurvey reads are `filename`, `debug` and `modernos`, all written as `key=value`, so
nothing else changes. Side effect: a bare file path together with other `key=value` parameters is now opened
too, where before it was ignored.

## How to reproduce

1. Put a copy of the cSurvey folder and a survey with signs inside a Google Drive folder that someone
   **else** shared with you (Drive for desktop, streaming mode). Your own *My Drive* is not affected.
2. Start `cSurveyPC.exe` from that folder (`G:\.shortcut-targets-by-id\…\csurvey64`) and open the survey
   → problem 1.
3. Associate `.csx` with any cSurvey (even one on `C:\`) and double-click the survey in the shared folder
   → problem 2.

The same copy works from `C:\`. Loading and printing through scripts (without the window) from the Drive
copy are not affected: they never load the sign gallery.

## Tested

- Path case on `G:`: only the shared folder's name is case-sensitive (checked one path part at a time).
- The patch applies cleanly to `master`. I could not build it (no DevExpress 24.2 here), so the change
  is reasoned from the code: I checked every reader of `cClipartPlaceholder.Filename` and of the
  command-line keys. Until a build with it is out, our members run cSurvey from a local copy.
