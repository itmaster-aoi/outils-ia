<#
.SYNOPSIS
  Prépare un poste de l'atelier pour Claude Code et le plugin aoi, sans élévation.

.DESCRIPTION
  À lancer une fois par utilisateur et par poste, dans un PowerShell normal (pas en administrateur) :

    powershell -ExecutionPolicy Bypass -File .\installer-poste.ps1

  Étapes, chacune vérifiée et rejouable sans risque :
    1. Git for Windows (installation par utilisateur, avec winget installé au besoin) et chemin de Git Bash pour Claude Code
    2. Claude Code (installation par utilisateur)
    3. Absence de clé ANTHROPIC_API_KEY (sinon les règles de l'organisation ne s'appliquent pas)
    4. Connexion à claude.ai (ouverte ici à la première fois, sinon vérifiée)
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
#>
[CmdletBinding()]
param(
  [switch]$DryRun,
  [string]$RevitVersion = "2025",
  [switch]$SkipAddins
)

# Version de l'installeur (date, suffixe .N pour plusieurs versions le même jour) : à changer à
# chaque modification du script, dans le même commit. Comparée à celle du dépôt (branche main)
# pour signaler une copie dépassée sur un partage.
$VersionInstalleur = "2026-10-14.2"
$DepotInstalleur = "https://raw.githubusercontent.com/itmaster-aoi/outils-ia/main/installer-poste.ps1"

$ErrorActionPreference = "Stop"
# Affiche correctement les accents et les symboles de Claude Code dans la console
try { [Console]::OutputEncoding = [Text.Encoding]::UTF8 } catch { }
$bilan = [System.Collections.Generic.List[object]]::new()

# Affichage dans le style de la toolbox AOI : titres en jaune, lignes « .   », ✅ réussi,
# ██ à surveiller, ❌ échec, questions « >>> » en jaune.
function Etape($titre) { Write-Host ""; Write-Host $titre -ForegroundColor Yellow }
function Ok($msg)      { Write-Host "✅  $msg" -ForegroundColor Green }
function Info($msg)    { Write-Host ".   $msg" }
function Avert($msg)   { Write-Host "██  $msg" -ForegroundColor Yellow }
function Erreur($msg)  { Write-Host "❌  $msg" -ForegroundColor Red }
function Detail($msg)  { Write-Host ".       $msg" -ForegroundColor DarkGray }
function Question($q)  { Write-Host -NoNewline ">>> $q " -ForegroundColor Yellow }
function Encadre([string[]]$lignes) {
  $l = ($lignes | Measure-Object -Property Length -Maximum).Maximum
  Write-Host ""
  Write-Host ("╔" + ("═" * ($l + 2)) + "╗")
  foreach ($x in $lignes) { Write-Host ("║ " + $x.PadRight($l) + " ║") }
  Write-Host ("╚" + ("═" * ($l + 2)) + "╝")
}
function Noter($etape, $etat, $detail) { $bilan.Add([pscustomobject]@{ Etape = $etape; Etat = $etat; Detail = $detail }) }
function Faire($desc, [scriptblock]$action) {
  if ($DryRun) { Info "(diagnostic seul) $desc"; return $false }
  Info $desc; & $action | Out-Host; return $true
}
# Lance un programme en affichant une roue qui tourne tant qu'il travaille.
# Rend Ok (code de sortie 0) et Texte (sortie standard et erreurs, pour le diagnostic).
function AvecRoue([string]$desc, [string]$exe, [string[]]$arguments) {
  $psi = New-Object System.Diagnostics.ProcessStartInfo
  $psi.FileName = $exe
  $psi.Arguments = ($arguments | ForEach-Object { if ($_ -match '[\s"]') { '"' + ($_ -replace '"', '\"') + '"' } else { $_ } }) -join ' '
  $psi.UseShellExecute = $false
  $psi.CreateNoWindow = $true
  $psi.RedirectStandardOutput = $true
  $psi.RedirectStandardError = $true
  $psi.StandardOutputEncoding = [Text.Encoding]::UTF8
  $psi.StandardErrorEncoding = [Text.Encoding]::UTF8
  $p = [System.Diagnostics.Process]::Start($psi)
  $out = $p.StandardOutput.ReadToEndAsync()
  $err = $p.StandardError.ReadToEndAsync()
  $roue = '|', '/', '-', '\'
  $anime = -not [Console]::IsOutputRedirected
  $debut = Get-Date
  $i = 0
  while (-not $p.WaitForExit(120)) {
    if ($anime) {
      $s = [int]((Get-Date) - $debut).TotalSeconds
      Write-Host -NoNewline ("`r{0}   {1} ... {2} s" -f $roue[$i++ % 4], $desc, $s) -ForegroundColor Yellow
    }
  }
  $p.WaitForExit()
  if ($anime) { Write-Host -NoNewline ("`r" + (' ' * ([Console]::WindowWidth - 1)) + "`r") }
  Info $desc
  [pscustomobject]@{ Ok = ($p.ExitCode -eq 0); Texte = ($out.Result + "`n" + $err.Result).Trim() }
}
function VarUtilisateur($nom) { [Environment]::GetEnvironmentVariable($nom, "User") }
function DefinirVar($nom, $valeur) {
  [Environment]::SetEnvironmentVariable($nom, $valeur, "User")
  Set-Item -Path "Env:$nom" -Value $valeur   # aussi pour la suite de ce script
}
function RafraichirPath {
  $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
}
# winget (App Installer) pour cet utilisateur, sans élévation. Sur un poste où App Installer est
# présent mais pas enregistré pour ce compte, un réenregistrement suffit. Sinon, téléchargement
# depuis les versions officielles de microsoft/winget-cli : Add-AppxPackage refuse un paquet dont
# la signature n'est pas reconnue par Windows.
function InstallerWinget {
  $famille = "Microsoft.DesktopAppInstaller_8wekyb3d8bbwe"
  $apps = "$env:LOCALAPPDATA\Microsoft\WindowsApps"
  try { Add-AppxPackage -RegisterByFamilyName -MainPackage $famille -ErrorAction Stop } catch { }
  RafraichirPath
  if ($env:Path -notlike "*$apps*") { $env:Path += ";$apps" }
  if (Get-Command winget -ErrorAction SilentlyContinue) { return }

  $arch = switch ($env:PROCESSOR_ARCHITECTURE) { "ARM64" { "arm64" } "x86" { "x86" } default { "x64" } }
  $base = "https://github.com/microsoft/winget-cli/releases/latest/download"
  $dossier = Join-Path $env:TEMP ("aoi-winget-" + [IO.Path]::GetRandomFileName())
  New-Item -ItemType Directory -Path $dossier | Out-Null
  try {
    [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
    $progres = $ProgressPreference; $ProgressPreference = "SilentlyContinue"
    $bundle = Join-Path $dossier "$famille.msixbundle"
    $deps = Join-Path $dossier "dependances.zip"
    Info "Téléchargement de winget (github.com/microsoft/winget-cli, dernière version)"
    Invoke-WebRequest -UseBasicParsing "$base/$famille.msixbundle" -OutFile $bundle
    Invoke-WebRequest -UseBasicParsing "$base/DesktopAppInstaller_Dependencies.zip" -OutFile $deps
    $ProgressPreference = $progres
    Expand-Archive $deps -DestinationPath (Join-Path $dossier "dependances")
    $appx = Get-ChildItem (Join-Path $dossier "dependances") -Recurse -Include *.appx, *.msix |
      Where-Object { $_.FullName -match "[\\_]$arch[\\_.]" } | ForEach-Object { $_.FullName }
    Info "Installation de winget pour l'utilisateur ($arch, $(@($appx).Count) dépendances)"
    Add-AppxPackage -Path $bundle -DependencyPath $appx -ForceUpdateFromAnyVersion -ErrorAction Stop
  } catch {
    Detail $_.Exception.Message
  } finally {
    Remove-Item $dossier -Recurse -Force -ErrorAction SilentlyContinue
  }
}

# --- 0. Contexte -----------------------------------------------------------------------------
$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
  [Security.Principal.WindowsBuiltInRole]::Administrator)
$fr = [Globalization.CultureInfo]"fr-CH"
$maintenant = Get-Date
$jour = $fr.TextInfo.ToTitleCase($fr.DateTimeFormat.GetDayName($maintenant.DayOfWeek))
Encadre @(
  "INSTALLATION AOI$(if ($DryRun) { ' : diagnostic seul' })",
  "$jour $($maintenant.ToString('dd.MM.yyyy, HH:mm'))",
  "$($env:USERNAME.ToLower()) @ $env:COMPUTERNAME"
)
if ($admin) { Avert "Ce PowerShell tourne en administrateur. Relancez-le en utilisateur normal : tout s'installe dans votre profil." }

# Copie de l'installeur dépassée (partage réseau oublié) : avertir avant de toucher au poste.
try {
  [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
  $distant = (Invoke-WebRequest -UseBasicParsing -TimeoutSec 10 $DepotInstalleur).Content
  $versionDepot = if ($distant -match '\$VersionInstalleur\s*=\s*"([\d.-]+)"') { $Matches[1] }
} catch { $versionDepot = $null }
if (-not $versionDepot) {
  Info "Installeur $VersionInstalleur (version du dépôt non vérifiée : GitHub injoignable ou réponse illisible)"
} elseif ($versionDepot -gt $VersionInstalleur) {
  Avert "Cet installeur ($VersionInstalleur) est dépassé : le dépôt a la version $versionDepot."
  Detail "Copie lancée : $PSCommandPath"
  Detail "Version à jour : https://github.com/itmaster-aoi/outils-ia (installer-poste.ps1 et installer-poste.cmd)"
  $rep = if ($DryRun) { "o" } else { Question "Continuer quand même avec cette version ? (o/n)"; Read-Host }
  if ($rep -ne "o") { Info "Arrêt. Remplacez cette copie de l'installeur, puis relancez-la."; exit 1 }
  Noter "Installeur" "À METTRE À JOUR" "$VersionInstalleur, dépôt : $versionDepot"
} else {
  Ok "Installeur $VersionInstalleur (à jour)"
  Noter "Installeur" "ok" $VersionInstalleur
}

# --- 1. Git for Windows ----------------------------------------------------------------------
Etape "1. Git for Windows"
$candidats = @(
  "$env:LOCALAPPDATA\Programs\Git\bin\bash.exe",
  "$env:ProgramFiles\Git\bin\bash.exe"
)
$bash = $candidats | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $bash) {
  if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
    if ($DryRun) { Info "(diagnostic seul) Installation de winget pour l'utilisateur (github.com/microsoft/winget-cli)" }
    else { InstallerWinget }
  }
  if (Get-Command winget -ErrorAction SilentlyContinue) {
    if ($DryRun) { Info "(diagnostic seul) Installation de Git pour l'utilisateur (winget)" } else {
      $r = AvecRoue "Installation de Git pour l'utilisateur (winget)" (Get-Command winget).Source @(
        "install", "--id", "Git.Git", "-e", "--scope", "user", "--silent",
        "--accept-package-agreements", "--accept-source-agreements")
      if (-not $r.Ok) { $r.Texte -split "`r?`n" | Select-Object -Last 5 | ForEach-Object { Detail $_ } }
      RafraichirPath
    }
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
  if ($DryRun) { Info "(diagnostic seul) Installation de Claude Code pour l'utilisateur" } else {
    $r = AvecRoue "Installation de Claude Code pour l'utilisateur" (Get-Command powershell).Source @(
      "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", "irm https://claude.ai/install.ps1 | iex")
    if (-not $r.Ok) { $r.Texte -split "`r?`n" | Select-Object -Last 5 | ForEach-Object { Detail $_ } }
    RafraichirPath
    $env:Path += ";$HOME\.local\bin"
  }
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
  $rep = if ($DryRun) { "n" } else { Question "Supprimer la variable ANTHROPIC_API_KEY de votre compte ? (o/n)"; Read-Host }
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

# --- 4. Connexion à claude.ai ----------------------------------------------------------------
# Sans connexion, la console n'envoie pas ses règles (étiquette imposée) et le plugin ne peut pas
# s'installer. Première fois sur ce compte : connexion ouverte ici, puis l'installation continue.
Etape "4. Connexion à claude.ai"
function EtatConnexion {
  $r = AvecRoue "Vérification de la connexion" $claude.Source @("auth", "status", "--json")
  [pscustomobject]@{
    Connecte = $r.Texte -match '"loggedIn"\s*:\s*true'
    ClaudeAi = $r.Texte -match '"authMethod"\s*:\s*"claude\.ai"'
  }
}
if (-not $claude) {
  Noter "Connexion" "MANQUANT" "Claude Code absent"
} else {
  $cx = EtatConnexion
  if (-not $cx.Connecte -and -not $DryRun) {
    Info "Première connexion : un navigateur s'ouvre. Connectez-vous avec le compte claude.ai de l'atelier,"
    Info "puis revenez dans cette fenêtre (si un code est affiché dans le navigateur, collez-le ici)."
    $ErrorActionPreference = "Continue"
    & $claude.Source auth login --claudeai
    $ErrorActionPreference = "Stop"
    $cx = EtatConnexion
  }
  if (-not $cx.Connecte) {
    if ($DryRun) { Info "(diagnostic seul) Connexion à claude.ai à faire" }
    else { Avert "Pas connecté. Lancez « claude », connectez-vous avec le compte claude.ai de l'atelier, puis relancez ce script." }
    Noter "Connexion" "MANQUANT" "compte claude.ai de l'atelier"
  } elseif (-not $cx.ClaudeAi) {
    Avert "Connecté autrement qu'avec un compte claude.ai : les règles de l'organisation ne s'appliquent pas."
    Detail "Déconnectez-vous (claude auth logout), puis relancez ce script."
    Noter "Connexion" "À TRAITER" "pas un compte claude.ai"
  } else {
    Ok "Connecté avec un compte claude.ai"
    Noter "Connexion" "ok" "claude.ai"
  }
}

# --- 5. Anciennes déclarations MCP -----------------------------------------------------------
Etape "5. Anciennes déclarations MCP"
$claudeJson = Join-Path $HOME ".claude.json"
$ancien = $null
if (Test-Path $claudeJson) {
  try { $ancien = (Get-Content $claudeJson -Raw | ConvertFrom-Json).mcpServers } catch { }
}
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
function LireJson($chemin) {
  if (Test-Path $chemin) { try { return Get-Content $chemin -Raw | ConvertFrom-Json } catch { } }
  return $null
}
function RefImposee {
  $p = LireJson (Join-Path $HOME ".claude\remote-settings.json")
  if ($p -and $p.extraKnownMarketplaces.aoi) { return $p.extraKnownMarketplaces.aoi.source.ref }
}
function RefInscrite {
  $i = LireJson (Join-Path $HOME ".claude\plugins\known_marketplaces.json")
  if ($i -and $i.aoi) { return $i.aoi.source.ref }
}
function Installe($id) {
  $d = LireJson (Join-Path $HOME ".claude\plugins\installed_plugins.json")
  if ($d -and $d.plugins -and $d.plugins.$id) {
    $e = @($d.plugins.$id)[0]
    if ($e.installPath -and (Test-Path $e.installPath)) { return $e }
  }
}
# Lance claude, n'affiche sa sortie qu'en cas d'échec, rend $true si la commande a réussi.
function LancerClaude([string]$desc, [string[]]$arguments) {
  if ($DryRun) { Info "(diagnostic seul) $desc"; return $false }
  $r = AvecRoue $desc $claude.Source $arguments
  $sortie = $r.Texte
  $reussi = $r.Ok
  if (-not $reussi -and $sortie) { $sortie -split "`r?`n" | ForEach-Object { Detail $_ } }
  $script:derniereSortie = $sortie
  return $reussi
}

# Toute commande claude télécharge les règles de l'organisation : on part des règles du jour.
if ($claude -and -not $DryRun) { LancerClaude "Lecture des règles de l'organisation" @("plugin", "marketplace", "list") | Out-Null }

$essai = 0
do {
  $essai++
  $refImposee = RefImposee
  $refInscrite = RefInscrite
  if (-not $refImposee) {
    Avert "Les règles de l'organisation n'ont pas encore été reçues. Lancez « claude » une fois et connectez-vous avec le compte claude.ai de l'atelier, puis relancez ce script."
    break
  }
  Info "Étiquette imposée par la console : $refImposee ; inscrite sur ce poste : $(if ($refInscrite) { $refInscrite } else { 'aucune' })"
  if (-not $claude) { break }
  if ($refInscrite -ne $refImposee) {
    # Une inscription à une autre étiquette est refusée par la politique : on la remplace.
    if ($refInscrite) { LancerClaude "Retrait du catalogue aoi à l'étiquette $refInscrite" @("plugin", "marketplace", "remove", "aoi") | Out-Null }
    LancerClaude "Inscription du catalogue aoi à l'étiquette $refImposee" @("plugin", "marketplace", "add", "itmaster-aoi/outils-ia#$refImposee") | Out-Null
  }
  # Ancien nom du plugin (avant le 12.10.2026) : aoi-outils, serveurs plugin:aoi-outils:aoi-*
  if (Installe "aoi-outils@aoi") {
    LancerClaude "Désinstallation de l'ancien plugin aoi-outils (remplacé par aoi)" @("plugin", "uninstall", "aoi-outils@aoi") | Out-Null
  }
  if (Installe "aoi@aoi") {
    $ok = LancerClaude "Mise à jour du plugin aoi" @("plugin", "update", "aoi@aoi")
  } else {
    $ok = LancerClaude "Installation du plugin aoi (environ 350 Mo)" @("plugin", "install", "aoi@aoi")
  }
  # Règles reçues entre-temps (étiquette changée dans la console) : un seul nouvel essai.
  $relancer = (-not $ok) -and ($derniereSortie -match "blocked by your organization") -and ((RefImposee) -ne $refImposee)
  if ($relancer) { Info "La console impose une nouvelle étiquette : nouvel essai." }
} while ($relancer -and $essai -lt 2)

$plugin = Installe "aoi@aoi"
$refImposee = RefImposee
$refInscrite = RefInscrite
if (-not $plugin) {
  Avert "Plugin introuvable. Lancez « claude » une fois, connectez-vous avec le compte claude.ai de l'atelier, puis relancez ce script."
  Noter "Plugin aoi" "MANQUANT" "connexion à Claude Code requise"
} elseif (-not (Test-Path (Join-Path $plugin.installPath "skills\report\runtime\python.exe"))) {
  Avert "aoi $($plugin.version) est une version sans interpréteurs embarqués. Vérifiez que la console impose l'étiquette 2026-10-12.3 ou plus récente, puis relancez ce script."
  Noter "Plugin aoi" "À METTRE À JOUR" "$($plugin.version) : version antérieure à 2026.10.12.3"
} elseif ($refImposee -and $refInscrite -ne $refImposee) {
  Avert "aoi $($plugin.version) installé, mais le catalogue n'est pas à l'étiquette imposée ($refImposee). Relancez ce script ; si le message persiste, contactez l'IT."
  Noter "Plugin aoi" "À METTRE À JOUR" "$($plugin.version), console : $refImposee"
} else {
  Ok "aoi $($plugin.version) (étiquette $refInscrite)"
  Noter "Plugin aoi" "ok" "$($plugin.version)"
}
$plugin = if ($plugin) { Get-Item $plugin.installPath }

# Contrôle des imports Python : copie fixe que désigne env.PYTHONPATH dans la console
if ($plugin -and -not $DryRun) {
  $py = Join-Path $plugin.FullName "skills\report\runtime\python.exe"
  $ac = Join-Path $plugin.FullName "skills\report\scripts\activer_controle.py"
  if ((Test-Path $py) -and (Test-Path $ac)) {
    $ErrorActionPreference = "Continue"
    & $py $ac | Out-Host
    Noter "Contrôle des imports" $(if ($LASTEXITCODE -eq 0) { "ok" } else { "À TRAITER" }) "C:\ProgramData\aoi\guard"
    $ErrorActionPreference = "Stop"
  } else {
    Avert "Contrôle des imports non activé : $ac absent de aoi $($plugin.Name). Contactez l'IT."
    Noter "Contrôle des imports" "À TRAITER" "activer_controle.py absent du plugin"
  }
  # Python AOI et Node AOI : archives à part, téléchargées seulement si leur version change
  $pt = Join-Path $plugin.FullName "skills\regen\scripts\archives_aoi.py"
  if ((Test-Path $py) -and (Test-Path $pt)) {
    $r = AvecRoue "Python AOI et Node AOI (téléchargés seulement si leur version a changé)" $py @($pt)
    $r.Texte -split "`r?`n" | Where-Object { $_ -notmatch '^\s*\.\.\. ' } | ForEach-Object { Detail $_ }
    Noter "Python et Node AOI" $(if ($r.Ok) { "ok" } else { "À TRAITER" }) "$env:LOCALAPPDATA\aoi"
  }
}

# --- 7. Add-ins Rhino et Revit ---------------------------------------------------------------
Etape "7. Add-ins Rhino et Revit"
if ($SkipAddins) {
  Info "Ignoré (-SkipAddins)"
} elseif ($plugin) {
  # Même logique que /regen : chaque add-in est décrit par mcp/<serveur>/addin.json. Celui de
  # Revit est une archive publiée à part, téléchargée seulement si sa version manque sur le poste.
  # Seules les applications déjà lancées sur ce compte sont traitées, et seulement si elles sont fermées.
  $py = Join-Path $plugin.FullName "skills\report\runtime\python.exe"
  $maj = Join-Path $plugin.FullName "skills\regen\scripts\maj.py"
  if ($DryRun) {
    Info "Add-ins : non traités (-DryRun)"
    Noter "Add-ins" "À TRAITER" "-DryRun"
  } elseif ((Test-Path $py) -and (Test-Path $maj)) {
    $r = AvecRoue "Add-ins Rhino et Revit (Revit téléchargé seulement si sa version a changé)" $py @($maj, "--addins")
    $r.Texte -split "`r?`n" | Where-Object { $_ -notmatch '^\s*\.\.\. ' } | ForEach-Object { Detail $_ }
    Noter "Add-ins" $(if ($r.Ok) { "ok" } else { "À TRAITER" }) "voir le détail ci-dessus"
  } else {
    Avert "Add-ins non installés : $maj absent de aoi $($plugin.Name). Contactez l'IT."
    Noter "Add-ins" "À TRAITER" "maj.py absent du plugin"
  }
} else {
  Noter "Add-ins" "MANQUANT" "plugin absent"
}

# --- Bilan -----------------------------------------------------------------------------------
Etape "8. Bilan"
$largeur = ($bilan | ForEach-Object { $_.Etape.Length } | Measure-Object -Maximum).Maximum
foreach ($b in $bilan) {
  $ligne = "{0}   {1}   {2}" -f $b.Etape.PadRight($largeur), $b.Etat.PadRight(15), $b.Detail
  switch -Regex ($b.Etat) {
    '^ok$'                  { Ok $ligne }
    '^(non concerné|ignoré)$' { Info $ligne }
    'MANQUANT'              { Erreur $ligne }
    default                 { Avert $ligne }
  }
}
Etape "Ensuite"
Info "Fermez ce terminal, ouvrez-en un nouveau, lancez « claude » et vérifiez :"
Info "    /status   règles de l'organisation actives, connexion par compte claude.ai"
Info "    /plugin   catalogue aoi, plugin aoi activé"
Info "    /mcp      plugin:aoi:rhino et plugin:aoi:revit (Rhino et Revit ouverts)"
Info "    /report   rapport des serveurs et des librairies"
Info "Au premier lancement, acceptez les réglages de l'organisation si Claude Code le demande."
