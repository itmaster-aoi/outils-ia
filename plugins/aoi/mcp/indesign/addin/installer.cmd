@echo off
rem Installe le plugin Claude MCP pour InDesign, sans droits administrateur.
set __COMPAT_LAYER=RunAsInvoker
"%CommonProgramFiles%\Adobe\Adobe Desktop Common\RemoteComponents\UPI\UnifiedPluginInstallerAgent\UnifiedPluginInstallerAgent.exe" /install "%~dp0indesign-mcp.claude-mcp_ID.ccx"
if errorlevel 1 (echo ECHEC de l'installation.) else (echo Installe. Redemarrez InDesign, puis Fenetre ^> Modules externes ^> Claude MCP.)
pause
