# csurvey_headless_probe.ps1 — drive the INSTALLED cSurvey (C:\csurvey64\cSurveyPC.exe) as a
# library from Windows PowerShell 5.1, with no compiler, no source build, no DevExpress licence.
#
# Verified 2026-09-20 on cSurveyPC 2.0.0.0 (release binary 2025-12-10, x64) against a real
# TopoDroid-derived survey (SB 1103). See ../brief.md §2 for what each poke is for.
#
#   powershell -STA -ExecutionPolicy Bypass -File csurvey_headless_probe.ps1 -Survey <file.csx|csz> -Command info
#   ... -Command recalc  -Out <saved.csx>           re-runs the therion calculation, saves
#   ... -Command print   -Out <dir>                 prints plan + profile to <dir>\<name>_plan.pdf / _profile.pdf
#                                                   using the _preview.plan/_preview.profile settings IN THE FILE
#
# MUST run in an STA thread (-STA): frmPreview is a WinForms form. It is never shown.
# Reflection into non-public members is version-fragile: every poke is asserted and named below.

param(
    [Parameter(Mandatory = $true)] [string] $Survey,
    [ValidateSet('info', 'recalc', 'print')] [string] $Command = 'info',
    [string] $Out = '',
    [string] $CSurveyDir = 'C:\csurvey64',
    [string] $Printer = 'Microsoft Print to PDF'
)

$ErrorActionPreference = 'Stop'
if ([Threading.Thread]::CurrentThread.GetApartmentState() -ne 'STA') { throw 'Run with powershell -STA (frmPreview needs an STA thread).' }

$BF = [Reflection.BindingFlags]'NonPublic,Public,Static,Instance'
$asm = [Reflection.Assembly]::LoadFrom((Join-Path $CSurveyDir 'cSurveyPC.exe'))

function Assert-NotNull($x, $what) { if ($null -eq $x) { throw "cSurvey internals changed: $what not found (binary $($asm.GetName().Version))" }; $x }

# --- bootstrap: the three things the WinForms startup normally does (ApplicationEvents.vb:64-83) ---
# 1. modMain.GetApplicationPath() derives from Process.MainModule — that is powershell.exe here, so
#    pre-seed its cache (modMain.vb:42-47) or resources/objects/cliparts resolve to the wrong folder.
$modMain = Assert-NotNull $asm.GetType('cSurveyPC.modMain') 'modMain'
(Assert-NotNull $modMain.GetField('sApplicationPath', $BF) 'modMain.sApplicationPath').SetValue($null, $CSurveyDir)
# 2. localized strings (modMain.vb:414); cSurvey.New() reads them (cProperties.cHighlightsDetails.vb:31).
(Assert-NotNull $modMain.GetMethod('LoadLocalizedStrings', $BF) 'modMain.LoadLocalizedStrings').Invoke($null, @('')) | Out-Null
# 3. My.Application.Settings (registry HKCU\Software\Cepelabs\cSurvey) + an empty RuntimeSettings.
$myProject = Assert-NotNull ($asm.GetTypes() | Where-Object { $_.FullName -eq 'cSurveyPC.My.MyProject' }) 'My.MyProject'
$app = $myProject.GetProperty('Application', $BF).GetValue($null, $null)
$app.GetType().GetMethod('ReloadSettings', $BF).Invoke($app, $null) | Out-Null
$envType = Assert-NotNull ($asm.GetTypes() | Where-Object { $_.Name -eq 'cEnvironmentSettings' } | Select-Object -First 1) 'cEnvironmentSettings'
(Assert-NotNull $app.GetType().GetField('oRuntimeSettings', $BF) 'MyApplication.oRuntimeSettings').SetValue($app, [Activator]::CreateInstance($envType))
$therion = $app.Settings.GetSetting('therion.path', '')
if ($therion -eq '') { Write-Warning 'therion.path is not set in the registry — recalculation will fail.' }

# --- the survey (all Public API) ---
$srv = [Activator]::CreateInstance((Assert-NotNull $asm.GetType('cSurveyPC.cSurvey.cSurvey') 'cSurvey'))
$srv.Load((Resolve-Path $Survey).Path) | Out-Null
$name = [IO.Path]::GetFileNameWithoutExtension($Survey)

function Show-Speleometrics {
    # <calculate><sms><sm …> in the file; whole-complex row first, then per cave, then per branch.
    foreach ($sm in $srv.Calculate.Speleometrics) {
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
        if ($Out -eq '') { throw '-Out <saved.csx|csz> required' }
        # cCalculate.Calculate(PerformWarping) is Friend (Calculate/cCalculate.vb:576) — reflection.
        $srv.Invalidate()
        $calc = $srv.Calculate
        $m = Assert-NotNull $calc.GetType().GetMethod('Calculate', $BF, $null, [type[]]@([bool]), $null) 'cCalculate.Calculate(Boolean)'
        $r = $m.Invoke($calc, @($true))
        if (-not $r.Result) { throw "Calculate failed: $($r.Exception)" }
        $outPath = if ([IO.Path]::IsPathRooted($Out)) { $Out } else { Join-Path (Get-Location) $Out }
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $outPath) | Out-Null
        $srv.SaveTo($outPath)
        "saved: $Out"
        Show-Speleometrics
    }
    'print' {
        if ($Out -eq '') { throw '-Out <dir> required' }
        New-Item -ItemType Directory -Force -Path $Out | Out-Null
        # frmPreview is Friend; its ctor is (Survey, PreviewModeEnum, ViewModeEnum). Constructing it runs
        # pProfileSelect → pOptionsRestore, which pushes the file's _preview.* options into the
        # PrintDocument (printer, paper, orientation, margins, scale…). The form is never shown.
        $fp = Assert-NotNull $asm.GetType('cSurveyPC.frmPreview') 'frmPreview'
        $ctor = $fp.GetConstructors($BF)[0]
        $modeT = $ctor.GetParameters()[1].ParameterType; $viewT = $ctor.GetParameters()[2].ParameterType
        $docField = Assert-NotNull $fp.GetField('_oDoc', $BF) 'frmPreview._oDoc (WithEvents backing field)'
        foreach ($view in 'Plan', 'Profile') {
            $form = $ctor.Invoke(@($srv, [Enum]::Parse($modeT, 'Preview'), [Enum]::Parse($viewT, $view)))
            try {
                $doc = $docField.GetValue($form)
                $pdf = Join-Path $Out ("{0}_{1}.pdf" -f $name, $view.ToLower())
                $doc.PrinterSettings.PrinterName = $Printer
                if (-not $doc.PrinterSettings.IsValid) { throw "printer '$Printer' is not installed" }
                $doc.PrinterSettings.PrintToFile = $true
                $doc.PrinterSettings.PrintFileName = $pdf
                $doc.Print()      # fires the private oDoc_PrintPage handler (frmPreview.vb:1095) — one page, no dialog
                "{0,-8} {1} paper={2} landscape={3} -> {4} ({5} bytes)" -f $view, $doc.PrinterSettings.PrinterName, `
                    $doc.DefaultPageSettings.PaperSize.PaperName, $doc.DefaultPageSettings.Landscape, $pdf, (Get-Item $pdf).Length
            } finally { $form.Dispose() }
        }
    }
}
