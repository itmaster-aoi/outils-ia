<#
.SYNOPSIS
  Construit l'archive du Python AOI de l'atelier (réservé à l'IT).

.DESCRIPTION
  Python 3.12 portable (celui du plugin, controle/runtime) + les paquets de paquets.txt,
  en roues binaires pour Windows 64 bits, sans pip. Le contrôle des imports est branché d'office :
  le fichier python312._pth ajoute C:\ProgramData\aoi\guard au chemin de recherche.
  graphify (Graphify-Labs/graphify) vient d'un clone GitHub relu par l'IT, python-aoi\build\graphify,
  installé sans ses dépendances (elles sont dans paquets.txt). La skill /graphify du plugin est
  générée du même clone (adapter_skill_graphify.py) : skill et librairie ont le même commit.

  Produit :
    python-aoi\dist\python-aoi-<version>.zip
    python-aoi\verrou.txt                        versions exactes des paquets, commit de graphify
    plugins\aoi\python-aoi.json                  version, adresse et empreinte SHA-256
    plugins\aoi\skills\graphify\                 skill /graphify, générée du clone

  Ensuite : publier l'archive comme fichier de la version GitHub « python-aoi-<version> »,
  créer une étiquette du plugin, la reporter dans la console. Les postes l'installent avec
  /regen ou installer-poste.cmd, seulement si la version a changé.

.PARAMETER Version
  Version de l'archive, par défaut la date du jour (2026-10-12). Ajouter .2, .3 pour une
  reconstruction le même jour.

.PARAMETER PythonConstruction
  Python 3.12 avec pip, utilisé seulement pour télécharger les paquets.
  Par défaut : anaconda de l'utilisateur, sinon « py -3.12 ».

.PARAMETER GraphifyCommit
  Commit validé du clone de graphify (python-aoi\build\graphify). S'il est donné, la construction
  refuse un clone à un autre commit ; sinon le commit courant du clone est inscrit dans verrou.txt.
#>
param(
  [string]$Version = (Get-Date -Format "yyyy-MM-dd"),
  [string]$PythonConstruction,
  [string]$GraphifyCommit
)
$ErrorActionPreference = "Stop"
try { [Console]::OutputEncoding = [Text.Encoding]::UTF8 } catch { }
# Construction réservée à l'IT, hors de Claude Code : dans Claude, le contrôle des imports
# refuse pip, et ce script ne doit pas servir à le contourner.
if ($env:CLAUDECODE -or $env:CLAUDE_CODE_CHILD_SESSION) {
  throw "Lancez ce script dans une fenêtre PowerShell ordinaire, pas depuis Claude Code."
}

$racine = Split-Path $PSScriptRoot
$ici = $PSScriptRoot
$runtime = Join-Path $racine "plugins\aoi\controle\runtime"
$build = Join-Path $ici "build\python"
$dist = Join-Path $ici "dist"
$archive = Join-Path $dist "python-aoi-$Version.zip"
$depot = "itmaster-aoi/outils-ia"
$etiquette = "python-aoi-$Version"

if (-not $PythonConstruction) {
  $PythonConstruction = @("$env:LOCALAPPDATA\anaconda3\python.exe", "$env:USERPROFILE\anaconda3\python.exe") |
    Where-Object { Test-Path $_ } | Select-Object -First 1
}
if (-not $PythonConstruction) {
  $py = Get-Command py -ErrorAction SilentlyContinue
  if ($py) { $PythonConstruction = (& py -3.12 -c "import sys; print(sys.executable)") }
}
if (-not $PythonConstruction) { throw "Aucun Python avec pip trouvé : passez -PythonConstruction <chemin de python.exe>." }
Write-Host "Python de construction : $PythonConstruction"

# 1. Python portable du plugin
if (Test-Path $build) { Remove-Item $build -Recurse -Force }   # build\graphify (le clone) est gardé
New-Item -ItemType Directory -Force $build, $dist | Out-Null
Copy-Item "$runtime\*" $build -Recurse
$sp = Join-Path $build "Lib\site-packages"

# 2. Paquets : roues binaires Windows 64 bits pour Python 3.12, sans pip dans le résultat
& $PythonConstruction -m pip install --target $sp --only-binary=:all: --platform win_amd64 `
  --python-version 3.12 --implementation cp --no-compile --disable-pip-version-check `
  -r (Join-Path $ici "paquets.txt")
if ($LASTEXITCODE -ne 0) { throw "Échec du téléchargement des paquets." }
Get-ChildItem $sp -Directory -Filter "bin" | Remove-Item -Recurse -Force

# 2b. graphify : clone GitHub relu par l'IT, installé sans ses dépendances (elles viennent de paquets.txt)
$clone = Join-Path $ici "build\graphify"
if (-not (Test-Path (Join-Path $clone "pyproject.toml"))) {
  throw "Clone de graphify introuvable. Lancez : git clone --branch v8 https://github.com/Graphify-Labs/graphify `"$clone`" puis git -C `"$clone`" checkout <commit validé>."
}
$commit = (& git -C $clone rev-parse HEAD).Trim()
if ($GraphifyCommit -and -not $commit.StartsWith($GraphifyCommit)) { throw "Le clone de graphify est au commit $commit, pas au commit validé $GraphifyCommit." }
if (& git -C $clone status --porcelain) { throw "Le clone de graphify a des modifications locales : construction refusée." }
Write-Host "graphify : clone $clone, commit $commit"
& $PythonConstruction -m pip install --target $sp --no-deps --no-compile --disable-pip-version-check $clone
if ($LASTEXITCODE -ne 0) { throw "Échec de l'installation de graphify depuis le clone." }
Get-ChildItem $sp -Directory -Filter "bin" | Remove-Item -Recurse -Force

# 3. Chemin de recherche : Python, site-packages, puis le contrôle des imports de l'atelier
@"
python312.zip
.
Lib\site-packages
C:\ProgramData\aoi\guard
import site
"@ | Set-Content (Join-Path $build "python312._pth") -Encoding ASCII
Set-Content (Join-Path $build "aoi-version.txt") $Version -Encoding ASCII

# 4. Versions exactes
$verrou = Get-ChildItem $sp -Directory -Filter "*.dist-info" | ForEach-Object {
  $_.Name -replace '\.dist-info$', '' -replace '-(?=[^-]+$)', '=='
} | Sort-Object
$entete = "# Python AOI $Version : Python 3.12.10 portable (python.org) et paquets ci-dessous"
$origine = "# graphify : clone https://github.com/Graphify-Labs/graphify, commit $commit (installé sans pip, voir construire.ps1)"
($entete, $origine, $verrou) | ForEach-Object { $_ } | Set-Content (Join-Path $ici "verrou.txt") -Encoding UTF8
Copy-Item (Join-Path $ici "verrou.txt") (Join-Path $build "aoi-verrou.txt")

# 5. Essai : chaque librairie de la liste blanche se charge, contrôle des imports en mode relevé
$env:AOI_IMPORT_MODE = "report"
$env:AOI_IMPORT_LOG = Join-Path $ici "build\essai-imports.jsonl"
& (Join-Path $build "python.exe") -c "import openpyxl, docx, pptx, pypdf, pymupdf, fitz, reportlab, numpy, pandas, PIL, matplotlib, yaml, requests, networkx, rapidfuzz, tree_sitter, tree_sitter_python, graphify, graphify.detect, graphify.extract, sys; from tree_sitter import Language, Parser; Parser(Language(tree_sitter_python.language())).parse(b'x = 1'); from importlib.metadata import version; print('Essai réussi :', sys.version.split()[0], '- graphify', version('graphifyy'))"
if ($LASTEXITCODE -ne 0) { throw "Une librairie ne se charge pas." }
Remove-Item Env:AOI_IMPORT_MODE, Env:AOI_IMPORT_LOG

# 5b. Skill /graphify du plugin, générée du même clone : texte d'origine, Python AOI à la place des installeurs
& (Join-Path $runtime "python.exe") (Join-Path $ici "adapter_skill_graphify.py") $clone
if ($LASTEXITCODE -ne 0) { throw "Échec de la génération de la skill graphify." }

# 6. Archive et fiche du plugin
if (Test-Path $archive) { Remove-Item $archive }
Get-ChildItem $build -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force
# Compress-Archive de PowerShell 5.1 écrit des chemins avec « \ » : l'archive est faite par Python.
& (Join-Path $runtime "python.exe") -c "import shutil, sys; shutil.make_archive(sys.argv[1], 'zip', sys.argv[2])" ($archive -replace '\.zip$', '') $build
if ($LASTEXITCODE -ne 0) { throw "Échec de la création de l'archive." }
$sha = (Get-FileHash $archive -Algorithm SHA256).Hash.ToLower()
$taille = (Get-Item $archive).Length
$fiche = [ordered]@{
  version = $Version
  url     = "https://github.com/$depot/releases/download/$etiquette/python-aoi-$Version.zip"
  sha256  = $sha
  taille  = $taille
}
$json = ($fiche | ConvertTo-Json) + "`n"
[IO.File]::WriteAllText((Join-Path $racine "plugins\aoi\python-aoi.json"), $json, (New-Object Text.UTF8Encoding $false))

Write-Host ""
Write-Host "Archive : $archive ($([math]::Round($taille / 1MB)) Mo)"
Write-Host "SHA-256 : $sha"
Write-Host "graphify : commit $commit (à reporter dans VERSIONS.md)"
Write-Host "Publier : gh release create $etiquette `"$archive`" --repo $depot --title `"Python AOI $Version`" --notes-file `"$(Join-Path $ici 'verrou.txt')`""
