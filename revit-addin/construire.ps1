<#
.SYNOPSIS
  Construit l'archive de l'add-in Revit de l'atelier et met à jour sa fiche dans le plugin.

.DESCRIPTION
  L'add-in Revit (environ 90 Mo) n'est plus dans le plugin : il est publié comme version GitHub
  du dépôt, et /regen ou l'installeur ne le téléchargent que si sa version change.

    revit-addin\build\2025\        contenu de %APPDATA%\Autodesk\Revit\Addins\2025 (non publié)
    revit-addin\dist\revit-addin-<version>.zip

  La fiche (version, adresse, SHA-256, taille) est écrite dans plugins\aoi\mcp\revit\addin.json.
  Ensuite : publier l'archive (commande affichée), puis committer et créer l'étiquette du plugin.

.EXAMPLE
  .\revit-addin\construire.ps1 -Version 2026-10-12
#>
param([Parameter(Mandatory)][string]$Version)
$ErrorActionPreference = "Stop"

$ici = $PSScriptRoot
$racine = Split-Path $ici
$depot = "itmaster-aoi/outils-ia"
$etiquette = "revit-addin-$Version"
$source = Join-Path $ici "build\2025"
$dist = Join-Path $ici "dist"
$archive = Join-Path $dist "revit-addin-$Version.zip"
$fichePath = Join-Path $racine "plugins\aoi\mcp\revit\addin.json"
$runtime = Join-Path $racine "plugins\aoi\skills\report\runtime"

if (-not (Test-Path (Join-Path $source "mcp-servers-for-revit.addin"))) {
  throw "Add-in introuvable : $source doit contenir mcp-servers-for-revit.addin et revit_mcp_plugin\."
}
New-Item -ItemType Directory -Force $dist | Out-Null
if (Test-Path $archive) { Remove-Item $archive }

# Compress-Archive de PowerShell 5.1 écrit des chemins avec « \ » : l'archive est faite par Python.
& (Join-Path $runtime "python.exe") -c "import shutil, sys; shutil.make_archive(sys.argv[1], 'zip', sys.argv[2])" ($archive -replace '\.zip$', '') $source
if ($LASTEXITCODE -ne 0) { throw "Échec de la création de l'archive." }
$sha = (Get-FileHash $archive -Algorithm SHA256).Hash.ToLower()
$taille = (Get-Item $archive).Length

$fiche = Get-Content $fichePath -Raw -Encoding UTF8 | ConvertFrom-Json
$revit = $fiche.'add-ins' | Where-Object { $_.nom -eq "Revit 2025" }
$revit.archive = [ordered]@{
  version = $Version
  url     = "https://github.com/$depot/releases/download/$etiquette/revit-addin-$Version.zip"
  sha256  = $sha
  taille  = $taille
}
$json = ($fiche | ConvertTo-Json -Depth 5) + "`n"
[IO.File]::WriteAllText($fichePath, $json, (New-Object Text.UTF8Encoding $false))

Write-Host ""
Write-Host "Archive : $archive ($([math]::Round($taille / 1MB)) Mo)"
Write-Host "SHA-256 : $sha"
Write-Host "Fiche   : $fichePath"
Write-Host "Publier : gh release create $etiquette `"$archive`" --repo $depot --title `"Add-in Revit $Version`" --notes `"Add-in Revit 2025 de l'atelier (voir VERSIONS.md).`""
