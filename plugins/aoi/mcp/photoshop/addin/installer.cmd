@echo off
rem Installe le plugin Claude MCP pour Photoshop, sans droits administrateur.
set __COMPAT_LAYER=RunAsInvoker
"%CommonProgramFiles%\Adobe\Adobe Desktop Common\RemoteComponents\UPI\UnifiedPluginInstallerAgent\UnifiedPluginInstallerAgent.exe" /install "%~dp0photoshop-mcp.claude-mcp_PS.ccx"
if errorlevel 1 (echo ECHEC de l'installation.) else (echo Installe. Redemarrez Photoshop, puis Modules externes ^> Claude MCP Photoshop ^> Claude MCP.)
pause
