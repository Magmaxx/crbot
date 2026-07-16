param(
    [Parameter(Mandatory = $true)]
    [string]$Source,
    [string]$ProjectRoot = ".",
    [switch]$NoConfirm,
    [switch]$WhatIf
)

$ErrorActionPreference = "Stop"

function Confirm-Action {
    param([string]$Message)
    if ($NoConfirm) { return $true }
    $ans = Read-Host "$Message (yes/no)"
    return ($ans -eq "yes")
}

if (!(Test-Path $ProjectRoot)) {
    throw "Project root not found: $ProjectRoot"
}

if (!(Test-Path $Source)) {
    throw "Restore source not found: $Source"
}

if (-not $WhatIf) {
    if (-not (Confirm-Action "This will overwrite files under '$ProjectRoot'. Continue?")) {
        Write-Output "Restore cancelled."
        exit 0
    }
} else {
    Write-Output "[WHATIF] Confirmation bypassed (dry-run)."
}

$sourcePath = (Resolve-Path $Source).Path
$projectPath = (Resolve-Path $ProjectRoot).Path

$tempExtract = $null
$restoreFrom = $sourcePath

if ($sourcePath.ToLower().EndsWith(".zip")) {
    $tempExtract = Join-Path ([System.IO.Path]::GetTempPath()) ("telegram_bot_restore_" + (Get-Date -Format "yyyyMMdd_HHmmss"))
    if ($WhatIf) {
        Write-Output "[WHATIF] Extract zip: $sourcePath -> $tempExtract"
    } else {
        New-Item -ItemType Directory -Path $tempExtract -Force | Out-Null
        Expand-Archive -Path $sourcePath -DestinationPath $tempExtract -Force
    }
    $restoreFrom = $tempExtract
}

$excludeDirs = @(".venv", "__pycache__", ".git", "backups", ".pytest_cache")
$excludeFiles = @("*.pyc", "*.pyo")

$xdArgs = @()
foreach ($d in $excludeDirs) { $xdArgs += $d }

$xfArgs = @()
foreach ($f in $excludeFiles) { $xfArgs += $f }

$rcArgs = @(
    $restoreFrom
    $projectPath
    "/E"
    "/R:1"
    "/W:1"
    "/NFL"
    "/NDL"
    "/NJH"
    "/NJS"
    "/NP"
    "/XD"
) + $xdArgs + @("/XF") + $xfArgs

if ($WhatIf) {
    Write-Output "[WHATIF] robocopy $restoreFrom -> $projectPath (with exclusions)"
} else {
    & robocopy @rcArgs | Out-Null
    $rc = $LASTEXITCODE
    if ($rc -gt 7) {
        throw "Restore failed with robocopy exit code: $rc"
    }
}

if ($tempExtract -and (Test-Path $tempExtract)) {
    if ($WhatIf) {
        Write-Output "[WHATIF] Remove temp extract folder: $tempExtract"
    } else {
        Remove-Item $tempExtract -Recurse -Force
    }
}

if ($WhatIf) {
    Write-Output "Restore completed (whatif) from: $Source"
} else {
    Write-Output "Restore completed from: $Source"
}
Write-Output "Project root: $ProjectRoot"
