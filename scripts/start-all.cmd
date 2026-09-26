@echo off
setlocal
cd /d "%~dp0.."
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-all.ps1" %*
if errorlevel 1 (
  echo.
  echo Shinkou Insight startup failed. Review the message above and logs\.
)
pause
