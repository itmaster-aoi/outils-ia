<#
.SYNOPSIS
  Prépare un poste de l'atelier pour Claude Code et le plugin aoi, sans élévation.

.DESCRIPTION
  À lancer une fois par utilisateur et par poste, dans un PowerShell normal (pas en administrateur) :

    powershell -ExecutionPolicy Bypass -File .\installer-poste.ps1

  Étapes, chacune vérifiée et rejouable sans risque :
    1. Git for Windows (installation par utilisateur) et chemin de Git Bash pour Claude Code
    2. Claude Code (installation par utilisateur)
    3. Absence de clé ANTHROPIC_API_KEY (sinon les règles de l'organisation ne s'appliquent pas)
    4. Jeton personnel du service de veille (AOI_VEILLE_TOKEN), facultatif
    5. Retrait des anciennes déclarations MCP rhino / revit / veille
    6. Plugin aoi (catalogue imposé par l'organisation)
    7. Add-ins Rhino 8 et Revit, copiés depuis le plugin
  Puis un bilan.

  Python et Node.js ne sont pas nécessaires : ils sont fournis dans le plugin.

.PARAMETER DryRun
  N'affiche que le diagnostic, sans rien installer ni modifier.

.PARAMETER RevitVersion
  Version de Revit pour l'add-in (défaut : 2025).

.PARAMETER SkipAddins
  Ne copie pas les add-ins Rhino et Revit.

.PARAMETER SansVeille
  Passe l'étape du jeton de veille sans rien demander (personnes sans accès au service).
#>
[CmdletBinding()]
param(
  [switch]$DryRun,
  [string]$RevitVersion = "2025",
  [switch]$SkipAddins,
  [switch]$SansVeille
)

$ErrorActionPreference = "Stop"
# Affiche correctement les accents et les symboles de Claude Code dans la console
try { [Console]::OutputEncoding = [Text.Encoding]::UTF8 } catch { }
$bilan = [System.Collections.Generic.List[object]]::new()

function Etape($titre) { Write-Host ""; Write-Host "== $titre" -ForegroundColor Cyan }
function Ok($msg)      { Write-Host "   OK  $msg" -ForegroundColor Green }
function Info($msg)    { Write-Host "   ..  $msg" }
function Avert($msg)   { Write-Host "   !!  $msg" -ForegroundColor Yellow }
function Noter($etape, $etat, $detail) { $bilan.Add([pscustomobject]@{ Etape = $etape; Etat = $etat; Detail = $detail }) }
function Faire($desc, [scriptblock]$action) {
  if ($DryRun) { Info "(diagnostic seul) $desc"; return $false }
  Info $desc; & $action | Out-Host; return $true
}
function VarUtilisateur($nom) { [Environment]::GetEnvironmentVariable($nom, "User") }
function DefinirVar($nom, $valeur) {
  [Environment]::SetEnvironmentVariable($nom, $valeur, "User")
  Set-Item -Path "Env:$nom" -Value $valeur   # aussi pour la suite de ce script
}
function RafraichirPath {
  $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
}

# --- 0. Contexte -----------------------------------------------------------------------------
$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
  [Security.Principal.WindowsBuiltInRole]::Administrator)
Write-Host "Poste $env:COMPUTERNAME, utilisateur $env:USERNAME$(if ($DryRun) { ' : diagnostic seul' })"
if ($admin) { Avert "Ce PowerShell tourne en administrateur. Relancez-le en utilisateur normal : tout s'installe dans votre profil." }

# --- 1. Git for Windows ----------------------------------------------------------------------
Etape "1. Git for Windows"
$candidats = @(
  "$env:LOCALAPPDATA\Programs\Git\bin\bash.exe",
  "$env:ProgramFiles\Git\bin\bash.exe"
)
$bash = $candidats | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $bash) {
  if (Get-Command winget -ErrorAction SilentlyContinue) {
    Faire "Installation de Git pour l'utilisateur (winget)" {
      winget install --id Git.Git -e --scope user --silent --accept-package-agreements --accept-source-agreements
      RafraichirPath
    } | Out-Null
    $bash = $candidats | Where-Object { Test-Path $_ } | Select-Object -First 1
  } else {
    Avert "winget est indisponible. Installez PortableGit dans $env:LOCALAPPDATA\Programs\Git (voir le README), puis relancez ce script."
  }
}
if ($bash) {
  Ok "Git Bash : $bash"
  if ((VarUtilisateur "CLAUDE_CODE_GIT_BASH_PATH") -ne $bash) {
    Faire "CLAUDE_CODE_GIT_BASH_PATH = $bash" { DefinirVar "CLAUDE_CODE_GIT_BASH_PATH" $bash } | Out-Null
  }
  $git = Join-Path (Split-Path (Split-Path $bash)) "cmd\git.exe"
  if (Test-Path $git) { Ok (& $git --version) }
  Noter "Git for Windows" "ok" $bash
} else {
  Noter "Git for Windows" "MANQUANT" "nécessaire pour récupérer le plugin et activer le contrôle des imports"
}

# --- 2. Claude Code --------------------------------------------------------------------------
Etape "2. Claude Code"
RafraichirPath
$claude = Get-Command claude -ErrorAction SilentlyContinue
if (-not $claude) {
  Faire "Installation de Claude Code pour l'utilisateur" {
    Invoke-RestMethod https://claude.ai/install.ps1 | Invoke-Expression
    RafraichirPath
    $env:Path += ";$HOME\.local\bin"
  } | Out-Null
  $claude = Get-Command claude -ErrorAction SilentlyContinue
}
if ($claude) {
  Ok ("Claude Code " + (& claude --version))
  Noter "Claude Code" "ok" $claude.Source
} else {
  Noter "Claude Code" "MANQUANT" "installer puis relancer ce script"
}

# --- 3. Pas de clé API -----------------------------------------------------------------------
Etape "3. Clé ANTHROPIC_API_KEY"
if (VarUtilisateur "ANTHROPIC_API_KEY") {
  Avert "Une clé API est définie : les sessions qui l'utilisent échappent aux règles de l'organisation."
  $rep = if ($DryRun) { "n" } else { Read-Host "   Supprimer la variable ANTHROPIC_API_KEY de votre compte ? (o/n)" }
  if ($rep -eq "o") {
    [Environment]::SetEnvironmentVariable("ANTHROPIC_API_KEY", $null, "User")
    Remove-Item Env:ANTHROPIC_API_KEY -ErrorAction SilentlyContinue
    Ok "Variable supprimée"
    Noter "Clé API" "ok" "supprimée"
  } else {
    Noter "Clé API" "À TRAITER" "ANTHROPIC_API_KEY encore définie"
  }
} else {
  Ok "Aucune clé API définie"
  Noter "Clé API" "ok" "absente"
}

# --- 4. Jeton du service de veille (facultatif) ---------------------------------------------
Etape "4. Jeton du service de veille (facultatif)"
$claudeJson = Join-Path $HOME ".claude.json"
$ancien = $null
if (Test-Path $claudeJson) {
  try { $ancien = (Get-Content $claudeJson -Raw | ConvertFrom-Json).mcpServers } catch { }
}
$sansJeton = "facultatif : plugin:aoi:veille restera inactif sur ce poste, les autres outils fonctionnent"
if (VarUtilisateur "AOI_VEILLE_TOKEN") {
  Ok "Jeton déjà défini"
  Noter "Jeton de veille" "ok" "défini"
} elseif ($ancien -and $ancien.veille -and $ancien.veille.headers.Authorization) {
  $jeton = $ancien.veille.headers.Authorization -replace '^Bearer\s+', ''
  $fait = Faire "Reprise du jeton de l'ancienne déclaration « veille »" { DefinirVar "AOI_VEILLE_TOKEN" $jeton }
  Noter "Jeton de veille" $(if ($fait) { "ok" } else { "à reprendre" }) "depuis l'ancienne configuration"
} elseif ($SansVeille -or $DryRun) {
  Info "Pas de jeton : $sansJeton."
  Noter "Jeton de veille" "non concerné" $sansJeton
} else {
  Info "Seules les personnes qui ont accès au service de veille ont un jeton."
  $sec = Read-Host "   Collez votre jeton, ou appuyez sur Entrée si vous n'êtes pas concerné" -AsSecureString
  $jeton = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec))
  if ($jeton) {
    DefinirVar "AOI_VEILLE_TOKEN" $jeton; Ok "Jeton enregistré"
    Noter "Jeton de veille" "ok" "saisi"
  } else {
    Info "Pas de jeton : $sansJeton. Pour masquer le serveur, désactivez-le dans /mcp ; relancez ce script le jour où vous recevez un jeton."
    Noter "Jeton de veille" "non concerné" $sansJeton
  }
}
Remove-Variable jeton -ErrorAction SilentlyContinue

# --- 5. Anciennes déclarations MCP -----------------------------------------------------------
Etape "5. Anciennes déclarations MCP"
$vieux = @("rhino", "revit", "veille") | Where-Object { $ancien -and $ancien.PSObject.Properties.Name -contains $_ }
if ($vieux -and $claude) {
  foreach ($n in $vieux) { Faire "Retrait de « $n »" { & claude mcp remove $n -s user | Out-Null } | Out-Null }
  Noter "Anciennes déclarations" $(if ($DryRun) { "À TRAITER" } else { "ok" }) ($vieux -join ", ")
} else {
  Ok "Aucune"
  Noter "Anciennes déclarations" "ok" "aucune"
}

# --- 6. Plugin aoi --------------------------------------------------------------------
Etape "6. Plugin aoi"
$env:CLAUDE_CODE_PLUGIN_PREFER_HTTPS = "1"
$cache = Join-Path $HOME ".claude\plugins\cache\aoi\aoi"
function DossierPlugin {
  if (Test-Path $cache) {
    Get-ChildItem $cache -Directory | Where-Object { -not (Test-Path (Join-Path $_.FullName ".orphaned_at")) } |
      Sort-Object LastWriteTime -Descending | Select-Object -First 1
  }
}
function LireJson($chemin) {
  if (Test-Path $chemin) { try { return Get-Content $chemin -Raw | ConvertFrom-Json } catch { } }
  return $null
}
# Étiquette imposée par la console (managed settings reçus par Claude Code)
$politique = LireJson (Join-Path $HOME ".claude\remote-settings.json")
$refImposee = $null
if ($politique -and $politique.extraKnownMarketplaces.aoi) { $refImposee = $politique.extraKnownMarketplaces.aoi.source.ref }
# Étiquette du catalogue inscrit sur ce poste
$inscrits = LireJson (Join-Path $HOME ".claude\plugins\known_marketplaces.json")
$refInscrite = $null
if ($inscrits -and $inscrits.aoi) { $refInscrite = $inscrits.aoi.source.ref }

if (-not $refImposee) {
  Avert "Les règles de l'organisation n'ont pas encore été reçues. Lancez « claude » une fois et connectez-vous avec le compte claude.ai de l'atelier, puis relancez ce script."
} else {
  Info "Étiquette imposée par la console : $refImposee ; inscrite sur ce poste : $(if ($refInscrite) { $refInscrite } else { 'aucune' })"
  if ($claude -and $refInscrite -ne $refImposee) {
    # Une inscription à une autre étiquette est refusée par la politique : on la remplace.
    Faire "Inscription du catalogue aoi à l'étiquette $refImposee" {
      if ($refInscrite) { & claude plugin marketplace remove aoi }
      & claude plugin marketplace add "itmaster-aoi/outils-ia#$refImposee"
    } | Out-Null
  }
  # Ancien nom du plugin (avant le 12.10.2026) : aoi-outils, serveurs plugin:aoi-outils:aoi-*
  if ($claude -and (Test-Path (Join-Path $HOME ".claude\plugins\cache\aoi\aoi-outils"))) {
    Faire "Désinstallation de l'ancien plugin aoi-outils (remplacé par aoi)" {
      & claude plugin uninstall aoi-outils@aoi
    } | Out-Null
  }
  if ($claude) {
    Faire "Installation ou mise à jour du plugin aoi (environ 350 Mo au premier passage)" {
      & claude plugin install aoi@aoi
      & claude plugin update aoi@aoi
    } | Out-Null
  }
}
$plugin = DossierPlugin
if ($plugin -and -not (Test-Path (Join-Path $plugin.FullName "mcp\rhino\runtime\python.exe"))) {
  Avert "aoi $($plugin.Name) est une version sans interpréteurs embarqués. Vérifiez que la console impose l'étiquette 2026-10-12.3 ou plus récente, puis relancez ce script."
  Noter "Plugin aoi" "À METTRE À JOUR" "$($plugin.Name) : version antérieure à 2026.10.12.3"
} elseif ($plugin) {
  Ok "aoi $($plugin.Name)"
  Noter "Plugin aoi" "ok" $plugin.Name
} else {
  Avert "Plugin introuvable. Lancez « claude » une fois, connectez-vous avec le compte claude.ai de l'atelier, puis relancez ce script."
  Noter "Plugin aoi" "MANQUANT" "connexion à Claude Code requise"
}

# --- 7. Add-ins Rhino et Revit ---------------------------------------------------------------
Etape "7. Add-ins Rhino et Revit"
if ($SkipAddins) {
  Info "Ignoré (-SkipAddins)"
} elseif ($plugin) {
  $src = $plugin.FullName
  # Rhino 8
  $rhinoDst = "$env:APPDATA\McNeel\Rhinoceros\packages\8.0"
  if (Test-Path "$env:APPDATA\McNeel\Rhinoceros") {
    Faire "Copie du plugin Rhino vers $rhinoDst" {
      New-Item -ItemType Directory -Force $rhinoDst | Out-Null
      Copy-Item "$src\mcp\rhino\addin\rhinomcp" $rhinoDst -Recurse -Force
    } | Out-Null
    Noter "Add-in Rhino 8" $(if ($DryRun) { "À TRAITER" } else { "ok" }) $rhinoDst
  } else {
    Info "Rhino n'a jamais été lancé sur ce compte : add-in non copié."
    Noter "Add-in Rhino 8" "ignoré" "Rhino absent"
  }
  # Revit
  $revitDst = "$env:APPDATA\Autodesk\Revit\Addins\$RevitVersion"
  if (Test-Path "$env:APPDATA\Autodesk\Revit") {
    Faire "Copie de l'add-in Revit $RevitVersion vers $revitDst" {
      New-Item -ItemType Directory -Force $revitDst | Out-Null
      $reg = "$revitDst\revit_mcp_plugin\Commands\commandRegistry.json"
      if (Test-Path $reg) { Copy-Item $reg "$reg.avant-aoi-$(Get-Date -Format yyyyMMdd-HHmmss)" }
      Copy-Item "$src\mcp\revit\addin\2025\*" $revitDst -Recurse -Force
    } | Out-Null
    Noter "Add-in Revit $RevitVersion" $(if ($DryRun) { "À TRAITER" } else { "ok" }) $revitDst
  } else {
    Info "Revit n'a jamais été lancé sur ce compte : add-in non copié."
    Noter "Add-in Revit" "ignoré" "Revit absent"
  }
} else {
  Noter "Add-ins" "MANQUANT" "plugin absent"
}

# --- Bilan -----------------------------------------------------------------------------------
Etape "Bilan"
$bilan | Format-Table -AutoSize | Out-String | Write-Host
Write-Host "Ensuite : fermez ce terminal, ouvrez-en un nouveau, lancez « claude » et vérifiez :"
Write-Host "  /status   règles de l'organisation actives, connexion par compte claude.ai"
Write-Host "  /plugin   catalogue aoi, plugin aoi activé"
Write-Host "  /mcp      plugin:aoi:rhino et plugin:aoi:revit (Rhino et Revit ouverts), plugin:aoi:veille si vous avez un jeton"
Write-Host "  /report   rapport des serveurs et des librairies"
Write-Host "Au premier lancement, acceptez les réglages de l'organisation si Claude Code le demande."
