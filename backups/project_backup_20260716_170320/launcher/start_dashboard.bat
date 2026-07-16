@echo off
setlocal

set "PROJECT_ROOT=%~dp0.."
set "PS1=%PROJECT_ROOT%\launcher\start_dashboard.ps1"

if not exist "%PS1%" (
  echo [ERROR] Launcher script not found: %PS1%
  exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%PS1%" %*
