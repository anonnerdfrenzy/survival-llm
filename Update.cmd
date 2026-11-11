@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0local-tools\windows.ps1" -Action Update %*
set "result=%errorlevel%"
if not "%result%"=="0" pause
exit /b %result%
