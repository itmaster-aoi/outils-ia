@echo off
rem Retire le plugin Claude MCP d'InDesign, sans droits administrateur.
set __COMPAT_LAYER=RunAsInvoker
"%CommonProgramFiles%\Adobe\Adobe Desktop Common\RemoteComponents\UPI\UnifiedPluginInstallerAgent\UnifiedPluginInstallerAgent.exe" /remove "Claude MCP"
pause
