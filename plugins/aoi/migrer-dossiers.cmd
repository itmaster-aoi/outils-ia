@echo off
rem Passe les outils de l'atelier a la nouvelle organisation des dossiers (docs/organisation-dossiers.md).
rem Fermez Claude Code avant. Sans option : simulation, puis question. Options : --simuler, --appliquer, --annuler
"%~dp0controle\runtime\python.exe" "%~dp0skills\regen\scripts\migrer_dossiers.py" %*
echo.
pause
