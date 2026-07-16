Param(
    [int]$Port = 8501
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $projectRoot

$logsDir = Join-Path $projectRoot "logs"
if (!(Test-Path $logsDir)) {
    New-Item -Path $logsDir -ItemType Directory | Out-Null
}

$launcherLog = Join-Path $logsDir "launcher.log"
$ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

"[$ts] Launcher start requested. Port=$Port" | Out-File -FilePath $launcherLog -Append -Encoding utf8

$pythonPath = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (!(Test-Path $pythonPath)) {
    $msg = "[$(Get-Date -Format "yyyy-MM-dd HH:mm:ss")] ERROR: .venv python not found at $pythonPath"
    $msg | Out-File -FilePath $launcherLog -Append -Encoding utf8
    Write-Error $msg
    exit 1
}

try {
    & $pythonPath -m streamlit run src/gui/dashboard.py --server.headless true --server.port $Port
}
catch {
    $err = "[$(Get-Date -Format "yyyy-MM-dd HH:mm:ss")] ERROR: Launcher crashed - $($_.Exception.Message)"
    $err | Out-File -FilePath $launcherLog -Append -Encoding utf8
    throw
}
finally {
    "[$(Get-Date -Format "yyyy-MM-dd HH:mm:ss")] Launcher terminated." | Out-File -FilePath $launcherLog -Append -Encoding utf8
}
