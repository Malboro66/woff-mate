# Window-scoped native UIA delta; no desktop enumeration or campaign access.
param(
    [Parameter(Mandatory=$true)][string]$Bundle,
    [Parameter(Mandatory=$true)][string]$Inventory,
    [Parameter(Mandatory=$true)][string]$Output,
    [switch]$PhysicalWindows10
)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type -AssemblyName System.Windows.Forms
Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class AdoptionKeyboardWindow {
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr handle);
    [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
}
'@
function Send-AdoptionKey([string]$Key) {
    if ([AdoptionKeyboardWindow]::GetForegroundWindow() -ne $adoptionHandle) {
        throw 'Refusing keyboard input outside candidate foreground window'
    }
    [System.Windows.Forms.SendKeys]::SendWait($Key)
    Start-Sleep -Milliseconds 200
}
function Get-AdoptionControl([string]$Name) {
    $condition = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::NameProperty, $Name)
    return $adoptionRoot.FindFirst([System.Windows.Automation.TreeScope]::Descendants, $condition)
}
function Assert-AdoptionKeyboardFocus($Control) {
    for ($attempt = 0; $attempt -lt 20; $attempt++) {
        $focused = [System.Windows.Automation.AutomationElement]::FocusedElement
        if ([System.Windows.Automation.Automation]::Compare($focused, $Control) -and $Control.Current.HasKeyboardFocus) { return }
        Start-Sleep -Milliseconds 100
    }
    throw "Native keyboard/UIA focus mismatch: $($Control.Current.Name); observed $($focused.Current.Name)"
}
$adoptionBundle = (Resolve-Path -LiteralPath $Bundle).Path
$adoptionInventory = Get-Content -Raw -LiteralPath $Inventory | ConvertFrom-Json
$adoptionBuild = Get-Content -Raw -LiteralPath (Join-Path $adoptionBundle '_internal/adoption-build.json') | ConvertFrom-Json
$adoptionOS = Get-CimInstance Win32_OperatingSystem
if ($PhysicalWindows10 -and ($adoptionOS.Caption -notmatch 'Windows 10' -or [int]$adoptionOS.BuildNumber -ge 22000)) {
    throw 'PhysicalWindows10 requires an actual Windows 10 reference system'
}
$adoptionExpected = @($adoptionInventory.files | ForEach-Object { $_.path } | Sort-Object)
$adoptionActual = @(Get-ChildItem -LiteralPath $adoptionBundle -File -Recurse | ForEach-Object {
    $_.FullName.Substring($adoptionBundle.Length + 1).Replace('\', '/')
} | Sort-Object)
if (Compare-Object $adoptionExpected $adoptionActual) { throw 'Bundle file set differs from inventory' }
foreach ($adoptionFile in $adoptionInventory.files) {
    $adoptionHash = (Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $adoptionBundle $adoptionFile.path)).Hash.ToLowerInvariant()
    if ($adoptionHash -ne $adoptionFile.sha256) { throw "Bundle hash mismatch: $($adoptionFile.path)" }
}
$adoptionExecutable = Join-Path $adoptionBundle 'WoFFMateAdoption.exe'
$adoptionProcess = Start-Process -FilePath $adoptionExecutable -PassThru
try {
    $adoptionHandle = [IntPtr]::Zero
    for ($adoptionAttempt = 0; $adoptionAttempt -lt 200; $adoptionAttempt++) {
        $adoptionProcess.Refresh()
        if ($adoptionProcess.HasExited) { throw 'Candidate exited before UIA capture' }
        $adoptionHandle = $adoptionProcess.MainWindowHandle
        if ($adoptionHandle -ne [IntPtr]::Zero) { break }
        Start-Sleep -Milliseconds 100
    }
    if ($adoptionHandle -eq [IntPtr]::Zero) { throw 'No candidate window within 20 seconds' }
    $adoptionRoot = [System.Windows.Automation.AutomationElement]::FromHandle($adoptionHandle)
    $adoptionNames = @{
        'Skip to content' = 'ControlType.Button'
        'Select synthetic career' = 'ControlType.ComboBox'
        'Operations' = 'ControlType.CheckBox'
        'Pilot Dossier' = 'ControlType.CheckBox'
        'Missions' = 'ControlType.CheckBox'
        'Squadron' = 'ControlType.CheckBox'
        'War Diary' = 'ControlType.CheckBox'
        'Reports' = 'ControlType.CheckBox'
        'Data & System Status' = 'ControlType.CheckBox'
        'P0 fixture state' = 'ControlType.ComboBox'
    }
    $adoptionElements = @()
    $adoptionFocusWarnings = @()
    foreach ($adoptionName in ($adoptionNames.Keys | Sort-Object)) {
        $adoptionCondition = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::NameProperty, $adoptionName)
        $adoptionMatches = $adoptionRoot.FindAll([System.Windows.Automation.TreeScope]::Descendants, $adoptionCondition)
        $adoptionControl = $null
        foreach ($adoptionMatch in $adoptionMatches) {
            if ($adoptionMatch.Current.ControlType.ProgrammaticName -eq $adoptionNames[$adoptionName]) { $adoptionControl = $adoptionMatch; break }
        }
        if ($null -eq $adoptionControl) { throw "Missing UIA name/role: $adoptionName" }
        $adoptionCurrent = $adoptionControl.Current
        if (-not $adoptionCurrent.IsKeyboardFocusable -or -not $adoptionCurrent.IsEnabled -or $adoptionCurrent.IsOffscreen) {
            throw "UIA control unavailable: $adoptionName"
        }
        $adoptionControl.SetFocus()
        $adoptionFocused = $null
        $adoptionFocusVerified = $false
        # UIA focus notifications are asynchronous; composite controls may focus
        # a child. Accept only the requested element or one of its descendants.
        for ($adoptionFocusAttempt = 0; $adoptionFocusAttempt -lt 20; $adoptionFocusAttempt++) {
            Start-Sleep -Milliseconds 100
            $adoptionFocused = [System.Windows.Automation.AutomationElement]::FocusedElement
            $adoptionAncestor = $adoptionFocused
            for ($adoptionDepth = 0; $null -ne $adoptionAncestor -and $adoptionDepth -lt 12; $adoptionDepth++) {
                if ([System.Windows.Automation.Automation]::Compare($adoptionAncestor, $adoptionControl)) {
                    $adoptionFocusVerified = $true; break
                }
                if ([System.Windows.Automation.Automation]::Compare($adoptionAncestor, $adoptionRoot)) { break }
                $adoptionAncestor = [System.Windows.Automation.TreeWalker]::ControlViewWalker.GetParent($adoptionAncestor)
            }
            if ($adoptionFocusVerified) { break }
        }
        if (-not $adoptionFocusVerified) {
            if ($adoptionNames[$adoptionName] -eq 'ControlType.ComboBox') {
                # Required basic exposure is name/role/focusability. Preserve
                # this additional programmatic-focus limitation explicitly.
                $adoptionFocusWarnings += @{name=$adoptionName; requested='UIA SetFocus'; observed_name=$adoptionFocused.Current.Name; observed_role=$adoptionFocused.Current.ControlType.ProgrammaticName}
            } else {
            $adoptionDiagnostic = @{status='failed'; requested=$adoptionName; focused_name=$adoptionFocused.Current.Name; focused_role=$adoptionFocused.Current.ControlType.ProgrammaticName; controls=$adoptionElements; provenance=$adoptionBuild}
            $adoptionDiagnostic | ConvertTo-Json -Depth 12 | Set-Content -Encoding UTF8 -LiteralPath $Output
            throw "UIA focus failed: $adoptionName; observed $($adoptionFocused.Current.Name) / $($adoptionFocused.Current.ControlType.ProgrammaticName)"
            }
        }
        $adoptionElements += @{ name=$adoptionName; role=$adoptionCurrent.ControlType.ProgrammaticName; focusable=$true; focus_verified=$adoptionFocusVerified; focused_role=$adoptionFocused.Current.ControlType.ProgrammaticName }
    }
    # UIA SetFocus is not implemented by native QAccessibleComboBox 6.11.2.
    # Independently exercise real keyboard input and observe focus/value via UIA.
    [void][AdoptionKeyboardWindow]::SetForegroundWindow($adoptionHandle)
    Start-Sleep -Milliseconds 200
    $adoptionKeyboard = @()
    foreach ($selector in @(
        @{name='Select synthetic career'; predecessor='Skip to content'},
        @{name='P0 fixture state'; predecessor='Data & System Status'}
    )) {
        $control = Get-AdoptionControl $selector.name
        $predecessor = Get-AdoptionControl $selector.predecessor
        $predecessor.SetFocus()
        Assert-AdoptionKeyboardFocus $predecessor
        Send-AdoptionKey '{TAB}'
        Assert-AdoptionKeyboardFocus $control
        $valuePattern = $control.GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern)
        $before = $valuePattern.Current.Value
        Send-AdoptionKey '{DOWN}'
        $after = $valuePattern.Current.Value
        if ($after -eq $before) { throw "Selector Down key did not change UIA value: $($selector.name)" }
        # Career changes intentionally transfer focus to the content heading.
        # Re-enter by the documented tab path before reversing the selection.
        $predecessor.SetFocus()
        Assert-AdoptionKeyboardFocus $predecessor
        Send-AdoptionKey '{TAB}'
        Assert-AdoptionKeyboardFocus $control
        Send-AdoptionKey '{UP}'
        if ($valuePattern.Current.Value -ne $before) { throw "Selector Up key did not restore value: $($selector.name)" }
        $predecessor.SetFocus()
        Assert-AdoptionKeyboardFocus $predecessor
        Send-AdoptionKey '{TAB}'
        Assert-AdoptionKeyboardFocus $control
        Send-AdoptionKey '+{TAB}'
        Assert-AdoptionKeyboardFocus $predecessor
        $adoptionKeyboard += @{name=$selector.name; tab_focus_verified=$true; has_keyboard_focus_observed=$true;
            shift_tab_verified=$true; before=$before; after_down=$after; up_restored=$true}
    }
    $adoptionResult = @{
        schema=2; eval='EVAL-UI-ADOPTION-PACKAGE-001'; status='passed';
        physical_windows10=[bool]$PhysicalWindows10;
        physical_attestation='The PhysicalWindows10 switch is a maintainer assertion; OS checks alone cannot prove physical hardware';
        os=@{caption=$adoptionOS.Caption; version=$adoptionOS.Version; build=$adoptionOS.BuildNumber};
        provenance=$adoptionBuild; executable_sha256=(Get-FileHash -Algorithm SHA256 -LiteralPath $adoptionExecutable).Hash.ToLowerInvariant();
        inventory_sha256=(Get-FileHash -Algorithm SHA256 -LiteralPath $Inventory).Hash.ToLowerInvariant();
        selector_keyboard=$adoptionKeyboard; controls=$adoptionElements; programmatic_combo_focus_warnings=$adoptionFocusWarnings;
        acceptance_scope='native UIA names/roles/focusability; button SetFocus; selector Tab/Shift+Tab focus and Up/Down values; native combo SetFocus limitation retained';
        visible_focus_manual='pending maintainer observation';
        speech_certification='out of scope'; physical_layout_delta='pending: metric-sized brand rail at compact/200% and maintainer normal scale; no full page/state suite'
    }
    $adoptionResult | ConvertTo-Json -Depth 12 | Set-Content -Encoding UTF8 -LiteralPath $Output
} finally {
    if (-not $adoptionProcess.HasExited) {
        [void]$adoptionProcess.CloseMainWindow()
        if (-not $adoptionProcess.WaitForExit(5000)) { $adoptionProcess.Kill(); throw 'Candidate did not close normally' }
    }
}
