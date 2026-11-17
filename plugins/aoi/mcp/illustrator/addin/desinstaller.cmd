@echo off
rem Retire le panneau Claude MCP d'Illustrator, sans droits administrateur.
set "CIBLE=%APPDATA%\Adobe\CEP\extensions\illustrator-mcp.claude-mcp"
if exist "%CIBLE%" (rmdir /s /q "%CIBLE%" & echo Retire.) else (echo Le panneau n'est pas installe.)
pause
