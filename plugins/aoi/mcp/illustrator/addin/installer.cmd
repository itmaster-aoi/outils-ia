@echo off
rem Installe le panneau Claude MCP pour Illustrator, sans droits administrateur.
set "CIBLE=%APPDATA%\Adobe\CEP\extensions\illustrator-mcp.claude-mcp"
if exist "%CIBLE%" rmdir /s /q "%CIBLE%"
robocopy "%~dp0illustrator-mcp.claude-mcp" "%CIBLE%" /e /njh /njs /ndl /nfl >nul
if errorlevel 8 (echo ECHEC de la copie.) else (echo Installe. Redemarrez Illustrator, puis Fenetre ^> Extensions ^> Claude MCP.)
pause
