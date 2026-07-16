param(
    [string]$ProjectRoot = ".",
    [string]$BackupRoot = ".\backups",
    [switch]$Zip,
    [switch]$KeepFolder,
    [switch]$WhatIf
)

$ErrorActionPreference = "Stop"

function New-Timestamp {
    return (Get-Date -Format "yyyyMMdd_HHmmss")
}

if (!(Test-Path $ProjectRoot)) {
    throw "Project root not found: $ProjectRoot"
}

if (!(Test-Path $BackupRoot)) {
    if ($WhatIf) {
        Write-Output "[WHATIF] Create backup root: $BackupRoot"
    } else {
        New-Item -ItemType Directory -Path $BackupRoot -Force | Out-Null
    }
}

$timestamp = New-Timestamp
$dest = Join-Path $BackupRoot ("project_backup_" + $timestamp)

if ($WhatIf) {
    Write-Output "[WHATIF] Create backup folder: $dest"
} else {
    New-Item -ItemType Directory -Path $dest -Force | Out-Null
}

# Exclude heavy/ephemeral dirs and caches
$excludeDirs = @(".venv", "__pycache__", ".git", "backups", ".pytest_cache")
$excludeFiles = @("*.pyc", "*.pyo")

$xdArgs = @()
foreach ($d in $excludeDirs) { $xdArgs += $d }

$xfArgs = @()
foreach ($f in $excludeFiles) { $xfArgs += $f }

# robocopy preserves structure and is resilient on Windows
$rcArgs = @(
    $ProjectRoot
    $dest
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
    Write-Output "[WHATIF] robocopy $ProjectRoot -> $dest (with exclusions)"
} else {
    & robocopy @rcArgs | Out-Null
    $rc = $LASTEXITCODE

    # robocopy exit codes: 0..7 => success-ish
    if ($rc -gt 7) {
        throw "Backup failed with robocopy exit code: $rc"
    }
}

if ($Zip) {
    $zipPath = "$dest.zip"

    if ($WhatIf) {
        Write-Output "[WHATIF] Create zip archive: $zipPath"
        if (-not $KeepFolder) {
            Write-Output "[WHATIF] Remove backup folder after zip: $dest"
        }
        Write-Output "Backup created (whatif): $dest"
        Write-Output "Backup zip (whatif): $zipPath"
        exit 0
    }

    if (Test-Path $zipPath) {
        Remove-Item $zipPath -Force
    }

    Compress-Archive -Path (Join-Path $dest "*") -DestinationPath $zipPath -Force

    if (!(Test-Path $zipPath)) {
        throw "Zip archive was not created: $zipPath"
    }

    if (-not $KeepFolder) {
        Remove-Item $dest -Recurse -Force
        Write-Output "Backup created (zip): $zipPath"
    } else {
        Write-Output "Backup created: $dest"
        Write-Output "Backup zip created: $zipPath"
    }
} else {
    Write-Output "Backup created: $dest"
}
