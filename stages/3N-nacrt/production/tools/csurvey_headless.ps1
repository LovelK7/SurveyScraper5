# csurvey_headless.ps1 -- drive the INSTALLED cSurvey (cSurveyPC.exe) as a library from Windows
# PowerShell 5.1: recalculate a survey, read its speleometrics, and print plan/profile to PDF
# with no dialog, no compiler, no source build and no DevExpress licence.
#
# T2 of projects/0004-nacrt-finishing. Promoted from findings/csurvey_headless_probe.ps1, which
# proved every reflection poke below on cSurveyPC 2.0.0.0 (release binary 2025-12-10, x64)
# against a real TopoDroid-derived survey (SB 1103). The pokes are kept verbatim and each one is
# asserted by name, so a future cSurvey build fails loudly here instead of misbehaving later.
#
#   powershell -STA -NoProfile -ExecutionPolicy Bypass -File csurvey_headless.ps1 -Survey <f.csx|csz> -Command info
#   ... -Command recalc     -Out <saved.csx|csz>   re-run the calculation, save (refreshes <sms>)
#   ... -Command print      -Out <dir>             <name>_plan.pdf / <name>_profile.pdf in <dir>
#   ... -Command dimensions                        one JSON object on stdout, nothing else
#
# The normal caller is csurvey_driver.py next door, which also enforces the timeout: the
# calculation runs on this single-threaded apartment, so there is no in-script watchdog to
# interrupt it -- the parent kills the whole process instead (cSurvey's own sync ExecuteTherion
# pops a MsgBox after 120 s on very large surveys, which is exactly the hang to time out on).
#
# MUST run in an STA thread (-STA): frmPreview is a WinForms form. It is never shown.
#
# Exit codes: 0 ok * 2 usage * 3 bootstrap/reflection (the member is named) * 4 load *
#             5 calculate * 6 print. Every failure writes one line to stderr.
# Note that a clean run may still write to stderr: cSurvey shells out to therion's `cavern`, and
# a machine without it on PATH prints "'cavern' is not recognized" there while the calculation
# itself succeeds. Judge a run by its exit code, not by stderr being empty.

param(
    [string] $Survey = '',
    [string] $Command = 'info',
    [string] $Out = '',
    [string] $Design = 'Both',
    [string] $CSurveyDir = '',
    [string] $Printer = '',
    # Optional print overrides (brief sec. 3.3). They are applied to the in-memory
    # `_preview.*` options before the preview form reads them and are never saved
    # back to the survey -- the file's own options, written by nacrt_finish.py, are
    # the normal source. -ScaleMode is the print dialog's combo index (0 fit,
    # 1 1:100, 2 1:200, 3 1:250, 4 1:300, 5 1:500, 6 1:1000, 99 custom + -Scale).
    [int] $ScaleMode = -1,
    [int] $Scale = 0,
    [switch] $Landscape
)

$ErrorActionPreference = 'Stop'
$INV = [Globalization.CultureInfo]::InvariantCulture

# stdout must be UTF-8: the caller parses JSON straight out of the pipe and a
# Croatian cave name would come back mangled through the console's OEM codepage.
try { [Console]::OutputEncoding = New-Object Text.UTF8Encoding $false } catch { }

function Fail([int] $Code, [string] $Message) {
    [Console]::Error.WriteLine("csurvey_headless: $Message")
    exit $Code
}

# --- usage -----------------------------------------------------------------
# Validated by hand rather than with [ValidateSet] so that every usage error
# leaves exit code 2; a parameter-binding failure would exit 1.

$Command = $Command.ToLowerInvariant()
if ($Command -notin @('info', 'recalc', 'print', 'dimensions')) {
    Fail 2 "-Command must be info, recalc, print or dimensions (got '$Command')"
}
$Design = $Design.ToLowerInvariant()
if ($Design -notin @('plan', 'profile', 'both')) {
    Fail 2 "-Design must be Plan, Profile or Both (got '$Design')"
}
if ($Survey -eq '') { Fail 2 '-Survey <file.csx|.csz> required' }
if (-not (Test-Path -LiteralPath $Survey)) { Fail 2 "survey not found: $Survey" }
if ($Command -in @('recalc', 'print') -and $Out -eq '') {
    Fail 2 "-Out required for -Command $Command"
}
if ($ScaleMode -ne -1 -and $ScaleMode -notin @(0, 1, 2, 3, 4, 5, 6, 99)) {
    Fail 2 "-ScaleMode must be 0..6 or 99 (got $ScaleMode)"
}
if ([Threading.Thread]::CurrentThread.GetApartmentState() -ne 'STA') {
    Fail 2 'run with powershell -STA (frmPreview needs an STA thread)'
}

if ($CSurveyDir -eq '') {
    $CSurveyDir = if ($env:CSURVEY_DIR) { $env:CSURVEY_DIR } else { 'C:\csurvey64' }
}
if ($Printer -eq '') {
    $Printer = if ($env:CSURVEY_PRINTER) { $env:CSURVEY_PRINTER } else { 'Microsoft Print to PDF' }
}
$exe = Join-Path $CSurveyDir 'cSurveyPC.exe'
if (-not (Test-Path -LiteralPath $exe)) {
    Fail 2 "cSurveyPC.exe not found in '$CSurveyDir' (set CSURVEY_DIR or pass -CSurveyDir)"
}

# --- helpers ---------------------------------------------------------------

function Format-JsonNumber($Value) {
    # The host culture writes decimal commas; JSON needs dots. cSurvey rounds
    # lengths to whole metres and leaves quotas as raw singles, so "0.##" gives
    # 10 and 7.53 without inventing precision.
    if ($null -eq $Value) { return 'null' }
    return ([double] $Value).ToString('0.##', $INV)
}

function Format-JsonString($Value) {
    if ($null -eq $Value) { return 'null' }
    return '"' + (([string] $Value) -replace '\\', '\\' -replace '"', '\"') + '"'
}

function Get-SurveyBaseName([string] $Path) {
    # X_lt_fin.csx -> X: strip the whole pipeline's suffix chain, so the PDFs are
    # named after the cave and not after the step that produced them.
    $stem = [IO.Path]::GetFileNameWithoutExtension($Path)
    $name = $stem
    for ($changed = $true; $changed; ) {
        $changed = $false
        foreach ($suffix in @('_fin', '_lt', '_pp')) {
            if ($name.ToLowerInvariant().EndsWith($suffix)) {
                $name = $name.Substring(0, $name.Length - $suffix.Length)
                $changed = $true
            }
        }
    }
    if ($name -eq '') { return $stem }
    return $name
}

# --- bootstrap: the three things the WinForms startup normally does ---------
# (ApplicationEvents.vb:64-83). Reflection into non-public members is
# version-fragile, so every poke is asserted and named.

$BF = [Reflection.BindingFlags]'NonPublic,Public,Static,Instance'
$asm = $null

function Assert-NotNull($x, $what) {
    if ($null -eq $x) {
        $version = if ($asm) { $asm.GetName().Version } else { 'unknown' }
        throw "cSurvey internals changed: $what not found (binary $version)"
    }
    return $x
}

try {
    $asm = [Reflection.Assembly]::LoadFrom($exe)
    # 1. modMain.GetApplicationPath() derives from Process.MainModule -- that is
    #    powershell.exe here, so pre-seed its cache (modMain.vb:42-47) or
    #    resources/objects/cliparts resolve to the wrong folder.
    $modMain = Assert-NotNull $asm.GetType('cSurveyPC.modMain') 'modMain'
    (Assert-NotNull $modMain.GetField('sApplicationPath', $BF) 'modMain.sApplicationPath').SetValue($null, $CSurveyDir)
    # 2. localized strings (modMain.vb:414); cSurvey.New() reads them
    #    (cProperties.cHighlightsDetails.vb:31).
    (Assert-NotNull $modMain.GetMethod('LoadLocalizedStrings', $BF) 'modMain.LoadLocalizedStrings').Invoke($null, @('')) | Out-Null
    # 3. My.Application.Settings (HKCU\Software\Cepelabs\cSurvey) + an empty RuntimeSettings.
    $myProject = Assert-NotNull ($asm.GetTypes() | Where-Object { $_.FullName -eq 'cSurveyPC.My.MyProject' }) 'My.MyProject'
    $app = $myProject.GetProperty('Application', $BF).GetValue($null, $null)
    $app.GetType().GetMethod('ReloadSettings', $BF).Invoke($app, $null) | Out-Null
    $envType = Assert-NotNull ($asm.GetTypes() | Where-Object { $_.Name -eq 'cEnvironmentSettings' } | Select-Object -First 1) 'cEnvironmentSettings'
    (Assert-NotNull $app.GetType().GetField('oRuntimeSettings', $BF) 'MyApplication.oRuntimeSettings').SetValue($app, [Activator]::CreateInstance($envType))
    $therion = $app.Settings.GetSetting('therion.path', '')
    if ($therion -eq '') {
        [Console]::Error.WriteLine('csurvey_headless: therion.path is not set in the registry -- the calculation may be incomplete.')
    }
    $srvType = Assert-NotNull $asm.GetType('cSurveyPC.cSurvey.cSurvey') 'cSurvey'
} catch {
    Fail 3 "bootstrap failed: $($_.Exception.Message)"
}

# --- the survey (all Public API) -------------------------------------------

try {
    $srv = [Activator]::CreateInstance($srvType)
    $srv.Load((Resolve-Path -LiteralPath $Survey).Path) | Out-Null
} catch {
    Fail 4 "cannot load '$Survey': $($_.Exception.Message)"
}

function Get-SpeleometricRows {
    # <calculate><sms><sm ...>: whole-complex row (no cave), then one per cave,
    # then one per branch.
    return @($srv.Calculate.Speleometrics)
}

function Show-Speleometrics {
    foreach ($sm in (Get-SpeleometricRows)) {
        '{0,-30} {1,-8} l={2} pl={3} ml={4} pvr={5} nvr={6} vr={7} qmax={8} qmin={9} es={10}' -f `
            $sm.Cave, $sm.Branch, $sm.Length, $sm.PlanimetricLength, $sm.MeasuredLength, `
            $sm.PositiveVerticalRange, $sm.NegativeVerticalRange, $sm.VerticalRange, $sm.QuotaMax, $sm.QuotaMin, $sm.EntranceStation
    }
}

switch ($Command) {

    'info' {
        "file      : $Survey"
        "origin    : $($srv.Properties.Origin)   shots: $($srv.Segments.Count)   stations: $($srv.TrigPoints.Count)"
        "entrances : " + (($srv.TrigPoints | Where-Object { $_.Entrance -ne 'None' } | ForEach-Object { "$($_.Name)=$($_.Entrance)" }) -join ', ')
        Show-Speleometrics
    }

    'recalc' {
        try {
            # cCalculate.Calculate(PerformWarping) is Friend (Calculate/cCalculate.vb:576).
            $srv.Invalidate()
            $calc = $srv.Calculate
            $m = Assert-NotNull $calc.GetType().GetMethod('Calculate', $BF, $null, [type[]] @([bool]), $null) 'cCalculate.Calculate(Boolean)'
            $r = $m.Invoke($calc, @($true))
            if (-not $r.Result) { throw "cActionResult.Result = False: $($r.Exception)" }
        } catch {
            Fail 5 "calculation failed: $($_.Exception.Message)"
        }
        try {
            $outPath = if ([IO.Path]::IsPathRooted($Out)) { $Out } else { Join-Path (Get-Location) $Out }
            $parent = Split-Path -Parent $outPath
            if ($parent -ne '') { New-Item -ItemType Directory -Force -Path $parent | Out-Null }
            $srv.SaveTo($outPath)
        } catch {
            Fail 5 "cannot save '$Out': $($_.Exception.Message)"
        }
        "saved: $Out"
        Show-Speleometrics
    }

    'dimensions' {
        # One JSON object on stdout and nothing else, so the caller can parse it
        # straight out of the pipe. The numbers a Nacrt needs live on the
        # per-cave row: only there does cSurvey attribute the entrance, and so
        # only there do pvr/nvr/es exist (cCalculate.Plot.cSpeleometrics.vb:88-131).
        $rows = Get-SpeleometricRows
        $perCave = @($rows | Where-Object { $_.Cave -ne '' -and $_.Branch -eq '' })
        $row = $null
        if ($perCave.Count -eq 1) {
            $row = $perCave[0]
        } else {
            if ($perCave.Count -gt 1) {
                [Console]::Error.WriteLine("csurvey_headless: $($perCave.Count) caves in this survey -- reporting the whole-complex row; split them or read <sms> per cave.")
            }
            $row = $rows | Where-Object { $_.Cave -eq '' -and $_.Branch -eq '' } | Select-Object -First 1
        }

        $pvr = $null; $nvr = $null; $drop = $null
        $cave = ''; $es = ''; $l = $null; $pl = $null; $ml = $null
        $vr = $null; $qmx = $null; $qmn = $null
        $calculated = $false
        if ($null -ne $row) {
            $cave = $row.Cave
            $es = $row.EntranceStation
            $l = $row.Length; $pl = $row.PlanimetricLength; $ml = $row.MeasuredLength
            $pvr = $row.PositiveVerticalRange; $nvr = $row.NegativeVerticalRange
            # `vr` is cSurvey's own VerticalRange: pvr + nvr once an entrance
            # exists, the raw profile height before that (cSpeleometric.vb:166-225).
            # It is not written to <sms>, so it is a free cross-check on `drop`.
            $vr = $row.VerticalRange
            $qmx = $row.QuotaMax; $qmn = $row.QuotaMin
            if ($null -ne $pvr -and $null -ne $nvr) { $drop = [double] $pvr + [double] $nvr }
            $calculated = ($row.SegmentCount -gt 0)
        }

        $parts = @(
            '"cave": ' + (Format-JsonString $cave)
            '"l": ' + (Format-JsonNumber $l)
            '"pl": ' + (Format-JsonNumber $pl)
            '"ml": ' + (Format-JsonNumber $ml)
            '"pvr": ' + (Format-JsonNumber $pvr)
            '"nvr": ' + (Format-JsonNumber $nvr)
            '"drop": ' + (Format-JsonNumber $drop)
            '"vr": ' + (Format-JsonNumber $vr)
            '"qmx": ' + (Format-JsonNumber $qmx)
            '"qmn": ' + (Format-JsonNumber $qmn)
            '"es": ' + (Format-JsonString $es)
            '"caves": ' + (Format-JsonNumber $perCave.Count)
            '"calculated": ' + $(if ($calculated) { 'true' } else { 'false' })
        )
        '{' + ($parts -join ', ') + '}'
    }

    'print' {
        try {
            New-Item -ItemType Directory -Force -Path $Out | Out-Null
        } catch {
            Fail 6 "cannot create output directory '$Out': $($_.Exception.Message)"
        }
        $name = Get-SurveyBaseName $Survey
        $views = switch ($Design) {
            'plan' { @('Plan') }
            'profile' { @('Profile') }
            default { @('Plan', 'Profile') }
        }
        try {
            # frmPreview is Friend; its ctor is (Survey, PreviewModeEnum, ViewModeEnum).
            # Constructing it runs pProfileSelect -> pOptionsRestore, which pushes the
            # file's _preview.* options into the PrintDocument (printer, paper,
            # orientation, margins, scale...). The form is never shown.
            $fp = Assert-NotNull $asm.GetType('cSurveyPC.frmPreview') 'frmPreview'
            $ctor = $fp.GetConstructors($BF)[0]
            $modeT = $ctor.GetParameters()[1].ParameterType
            $viewT = $ctor.GetParameters()[2].ParameterType
            $docField = Assert-NotNull $fp.GetField('_oDoc', $BF) 'frmPreview._oDoc (WithEvents backing field)'
        } catch {
            Fail 3 "print bootstrap failed: $($_.Exception.Message)"
        }

        foreach ($view in $views) {
            $pdf = Join-Path $Out ("{0}_{1}.pdf" -f $name, $view.ToLowerInvariant())
            try {
                if ($ScaleMode -ne -1 -or $Scale -gt 0 -or $Landscape) {
                    # Public options object (cOptionsPreview): ScaleMode is the combo
                    # index the print handler reads back at frmPreview.vb:1159-1170,
                    # Scale the denominator behind the custom entry. In memory only.
                    $opt = $srv.Options.Item('_preview.' + $view.ToLowerInvariant())
                    if ($null -ne $opt) {
                        if ($ScaleMode -ne -1) { $opt.ScaleMode = $ScaleMode }
                        if ($Scale -gt 0) { $opt.Scale = $Scale }
                        if ($Landscape) { $opt.PageLandscape = $true }
                    }
                }
                $form = $ctor.Invoke(@($srv, [Enum]::Parse($modeT, 'Preview'), [Enum]::Parse($viewT, $view)))
            } catch {
                Fail 6 "cannot open the preview for $view : $($_.Exception.Message)"
            }
            try {
                $doc = $docField.GetValue($form)
                $doc.PrinterSettings.PrinterName = $Printer
                if (-not $doc.PrinterSettings.IsValid) { Fail 6 "printer '$Printer' is not installed" }
                $doc.PrinterSettings.PrintToFile = $true
                $doc.PrinterSettings.PrintFileName = $pdf
                if (Test-Path -LiteralPath $pdf) { Remove-Item -LiteralPath $pdf -Force }
                $doc.Print()   # fires the private oDoc_PrintPage handler (frmPreview.vb:1095) -- one page, no dialog
                if (-not (Test-Path -LiteralPath $pdf)) { Fail 6 "no file written for $view (printer '$Printer' wrote nothing)" }
                "{0,-8} {1} paper={2} landscape={3} -> {4} ({5} bytes)" -f $view, $doc.PrinterSettings.PrinterName, `
                    $doc.DefaultPageSettings.PaperSize.PaperName, $doc.DefaultPageSettings.Landscape, $pdf, (Get-Item -LiteralPath $pdf).Length
            } catch {
                Fail 6 "printing $view failed: $($_.Exception.Message)"
            } finally {
                $form.Dispose()
            }
        }
    }
}

exit 0
