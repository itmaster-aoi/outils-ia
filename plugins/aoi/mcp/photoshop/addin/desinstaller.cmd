@echo off
rem Retire le plugin Claude MCP de Photoshop, sans droits administrateur.
set __COMPAT_LAYER=RunAsInvoker
"%CommonProgramFiles%\Adobe\Adobe Desktop Common\RemoteComponents\UPI\UnifiedPluginInstallerAgent\UnifiedPluginInstallerAgent.exe" /remove "Claude MCP Photoshop"
pause
