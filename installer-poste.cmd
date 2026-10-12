@echo off
rem Lance installer-poste.ps1 sans elevation, en contournant la politique dexecution pour cette seule execution.
rem Les options sont transmises : installer-poste.cmd -DryRun
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0installer-poste.ps1" %*
echo.
pause
