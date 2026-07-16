param(
    [string]$ProjectRoot = ".",
    [string]$BackupRoot = ".\backups"
)

$ErrorActionPreference = "Stop"

function New-Timestamp {
    return (Get-Date -Format "yyyyMMdd_HHmmss")
}

if (!(Test-Path $ProjectRoot)) {
    throw "Project root not found: $ProjectRoot"
}

if (!(Test-Path $BackupRoot)) {
    New-Item -ItemType Directory -Path $BackupRoot -Force | Out-Null
}

$timestamp = New-Timestamp
$dest = Join-Path $BackupRoot ("project_backup_" + $timestamp)

New-Item -ItemType Directory -Path $dest -Force | Out-Null

# Exclude heavy/ephemeral dirs and caches
$excludeDirs = @(".venv", "__pycache__", ".git", "backups", ".pytest_cache")
$excludeFiles = @("*.pyc", "*.pyo")

$xdArgs = @()
foreach ($d in $excludeDirs) { $xdArgs += $d }

$xfArgs = @()
foreach ($f in $excludeFiles) { $xfArgs += $f }

# robocopy preserves structure and is resilient on Windows
$rcArgs = @(
    $ProjectRoot,
    $dest,
    "/E",
    "/R:1",
    "/W:1",
    "/NFL",
    "/NDL",
    "/NJH",
    "/NJS",
    "/NP",
    "/XD"
) + $xdArgs + @("/XF") + $xfArgs

robocopy @rcArgs | Out-Null
$rc = $LASTEXITCODE

# robocopy exit codes: 0..7 => success-ish
if ($rc -gt 7) {
    throw "Backup failed with robocopy exit code: $rc"
}

Write-Output "Backup created: $dest"
