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
        Start-Sleep -Milliseconds 100
        if (-not $adoptionControl.Current.HasKeyboardFocus) { throw "UIA focus failed: $adoptionName" }
        $adoptionElements += @{ name=$adoptionName; role=$adoptionCurrent.ControlType.ProgrammaticName; focusable=$true; focus_verified=$true }
    }
    $adoptionResult = @{
        schema=1; eval='EVAL-UI-ADOPTION-PACKAGE-001'; status='passed';
        physical_windows10=[bool]$PhysicalWindows10;
        physical_attestation='The PhysicalWindows10 switch is a maintainer assertion; OS checks alone cannot prove physical hardware';
        os=@{caption=$adoptionOS.Caption; version=$adoptionOS.Version; build=$adoptionOS.BuildNumber};
        provenance=$adoptionBuild; executable_sha256=(Get-FileHash -Algorithm SHA256 -LiteralPath $adoptionExecutable).Hash.ToLowerInvariant();
        inventory_sha256=(Get-FileHash -Algorithm SHA256 -LiteralPath $Inventory).Hash.ToLowerInvariant();
        controls=$adoptionElements; visible_focus_manual='pending maintainer observation';
        speech_certification='out of scope'; full_dpi_repeat='not required: unchanged rendering inputs'
    }
    $adoptionResult | ConvertTo-Json -Depth 12 | Set-Content -Encoding UTF8 -LiteralPath $Output
} finally {
    if (-not $adoptionProcess.HasExited) {
        [void]$adoptionProcess.CloseMainWindow()
        if (-not $adoptionProcess.WaitForExit(5000)) { $adoptionProcess.Kill(); throw 'Candidate did not close normally' }
    }
}
