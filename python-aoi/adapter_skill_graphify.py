"""Génère la skill /graphify du plugin à partir d'un clone de Graphify-Labs/graphify (réservé à l'IT).

    python-aoi/adapter_skill_graphify.py <clone>              clone GitHub (graphify/skill-windows.md)
    python-aoi/adapter_skill_graphify.py <dossier de skill>   dossier contenant SKILL.md et references/

Lancé par construire.ps1 après l'installation de graphify dans le Python AOI, pour que la skill
et la librairie viennent du même commit. Écrit plugins/aoi/skills/graphify/ :

    SKILL.md, references/*.md   texte d'origine (variante Windows), avec trois adaptations :
      - étape 1 : aucune installation (uv, pipx, pip) ; l'interpréteur est le Python AOI,
        %LOCALAPPDATA%\\aoi\\python, où l'IT a installé graphify ;
      - garde de l'interpréteur (sous-commandes) : même chose ;
      - appels « graphify … » en ligne de commande : « python.exe -m graphify … » du Python AOI,
        car l'archive n'a pas de graphify.exe.
    LICENSE, LICENSE-MIT, NOTICE  licences du projet d'origine, quand le clone les contient
    VERSION-AOI.txt               origine, version, commit, adaptations

Tout le reste du texte est repris tel quel. N'utilise que la bibliothèque standard.
"""
import datetime
import re
import shutil
import subprocess
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
DEST = RACINE / "plugins" / "aoi" / "skills" / "graphify"
ORIGINE = "https://github.com/Graphify-Labs/graphify"
LICENCES = ("LICENSE", "LICENSE-MIT", "NOTICE")

# Appels en ligne de commande, selon le langage du bloc de code qui les contient
CLI_PS = r'& "$env:LOCALAPPDATA\aoi\python\python.exe" -m graphify'
CLI_SH = r'"$LOCALAPPDATA/aoi/python/python.exe" -m graphify'
CLI = re.compile(r'^(?P<avant>\s*(?:#[^\n]*?:\s*)?)graphify (?=(?:export|query|path|explain|add|update|'
                 r'install|watch|cluster-only|serve|mcp|benchmark)\b)')

ETAPE1 = r'''# Python AOI de l'atelier : graphify y est installé par l'IT. Rien à installer ici
# (ni uv, ni pipx, ni pip : le contrôle des librairies de l'atelier s'applique).
New-Item -ItemType Directory -Force -Path graphify-out | Out-Null
$GRAPHIFY_PYTHON = Join-Path $env:LOCALAPPDATA "aoi\python\python.exe"
if (-not (Test-Path $GRAPHIFY_PYTHON)) { throw "Python AOI absent ($GRAPHIFY_PYTHON) : lancez /aoi:regen." }
& $GRAPHIFY_PYTHON -c "import graphify" 2>$null
if ($LASTEXITCODE -ne 0) { throw "graphify absent du Python AOI : lancez /aoi:regen (le Python AOI doit être à jour). Ne l'installez pas autrement." }
$Utf8NoBom = New-Object Text.UTF8Encoding $false
# Chemin de l'interpréteur, lu par toutes les étapes suivantes
[IO.File]::WriteAllText((Join-Path $PWD 'graphify-out\.graphify_python'), $GRAPHIFY_PYTHON, $Utf8NoBom)
# Racine analysée, pour que « --update » sans argument sache où regarder
[IO.File]::WriteAllText((Join-Path $PWD 'graphify-out\.graphify_root'), (Resolve-Path 'INPUT_PATH').Path, $Utf8NoBom)'''

GARDE = r'''if (-not (Test-Path graphify-out\.graphify_python)) {
    # Python AOI de l'atelier, où graphify est installé (voir l'étape 1) : pas de recherche ailleurs
    $GRAPHIFY_PYTHON = Join-Path $env:LOCALAPPDATA "aoi\python\python.exe"
    New-Item -ItemType Directory -Force -Path graphify-out | Out-Null
    [IO.File]::WriteAllText((Join-Path $PWD 'graphify-out\.graphify_python'), $GRAPHIFY_PYTHON, (New-Object Text.UTF8Encoding $false))
}'''

# Conseils d'installation dans la prose : sur les postes, c'est l'IT qui installe (Python AOI)
CONSEILS_PIP = (
    ("(`pip install 'graphifyy[gemini]'`)", "(extra `gemini` : demander à l'IT)"),
    ("(requires `pip install 'graphifyy[video]'`)", "(extra `video` : demander à l'IT)"),
    ("`pip install --upgrade graphifyy`", "demander à l'IT une nouvelle version du Python AOI"),
)

NOTE = ("> Skill d'origine : [Graphify-Labs/graphify]({origine}) (`graphify/skill-windows.md`, version {version}, "
        "commit `{commit}`), reprise par l'IT de l'atelier oï : le Python AOI (`%LOCALAPPDATA%\\aoi\\python`) est "
        "le seul interpréteur et **cette skill n'installe rien** (ni uv, ni pipx, ni pip). "
        "Détail des adaptations dans `VERSION-AOI.txt`.\n")


def remplacer_bloc(texte, titre, nouveau, fichier):
    """Remplace le premier bloc ```powershell qui suit la ligne de titre (expression régulière)."""
    m = re.search(titre, texte, re.MULTILINE)
    if not m:
        sys.exit(f"Titre introuvable dans {fichier.name} : {titre} (la skill d'origine a changé, adapter ce script)")
    debut = texte.find("```powershell\n", m.end())
    fin = texte.find("\n```", debut + 1) if debut >= 0 else -1
    if debut < 0 or fin < 0 or "\n#" in texte[m.end():debut]:  # pas de bloc, ou un autre titre avant lui
        sys.exit(f"Bloc PowerShell introuvable sous « {m.group(0)} » dans {fichier.name}")
    return texte[:debut] + "```powershell\n" + nouveau.rstrip("\n") + texte[fin:]


def remplacer_cli(texte):
    """« graphify … » dans un bloc de code → Python AOI en module. Renvoie (texte, nombre)."""
    lignes, n, langage = [], 0, None
    for ligne in texte.split("\n"):
        if ligne.startswith("```"):
            langage = None if langage is not None else ligne[3:].strip().lower()
        elif langage is not None:
            forme = CLI_PS if langage == "powershell" else CLI_SH
            ligne, k = CLI.subn(lambda m: m.group("avant") + forme + " ", ligne)
            n += k
        lignes.append(ligne)
    return "\n".join(lignes), n


def version_clone(src):
    """(version, commit) : pyproject.toml et git pour un clone ; .graphify_version pour un dossier de skill."""
    pyproject = src / "pyproject.toml"
    if pyproject.is_file():
        m = re.search(r'^version\s*=\s*"([^"]+)"', pyproject.read_text(encoding="utf-8"), re.MULTILINE)
        version = m.group(1) if m else "?"
        try:
            commit = subprocess.run(["git", "-C", str(src), "rev-parse", "HEAD"], capture_output=True,
                                    text=True, check=True).stdout.strip()
        except (OSError, subprocess.CalledProcessError):
            commit = "inconnu (pas un dépôt git)"
        return version, commit
    v = src / ".graphify_version"
    return (v.read_text(encoding="utf-8").strip() if v.is_file() else "?"), "inconnu (dossier de skill, pas un clone)"


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    src = Path(sys.argv[1]).resolve()
    if (src / "graphify" / "skill-windows.md").is_file():
        skill = src / "graphify" / "skill-windows.md"
        refs = src / "graphify" / "skills" / "windows" / "references"
    elif (src / "SKILL.md").is_file():
        skill = src / "SKILL.md"
        refs = src / "references"
    else:
        sys.exit(f"Ni graphify/skill-windows.md (clone) ni SKILL.md (dossier de skill) dans {src}")
    if not refs.is_dir():
        sys.exit(f"Dossier references introuvable : {refs}")
    version, commit = version_clone(src)

    texte = skill.read_text(encoding="utf-8").replace("\r\n", "\n")
    texte = remplacer_bloc(texte, r"^### Step 1\b.*$", ETAPE1, skill)
    texte = remplacer_bloc(texte, r"^## Interpreter guard\b.*$", GARDE, skill)
    texte, n = remplacer_cli(texte)
    for ancien, nouveau in CONSEILS_PIP:
        texte = texte.replace(ancien, nouveau)
    # Note d'origine juste après l'en-tête YAML
    fin_entete = texte.find("\n---\n", 4) + len("\n---\n") if texte.startswith("---\n") else 0
    texte = texte[:fin_entete] + "\n" + NOTE.format(origine=ORIGINE, version=version, commit=commit) + texte[fin_entete:]

    shutil.rmtree(DEST, ignore_errors=True)
    (DEST / "references").mkdir(parents=True)
    DEST.joinpath("SKILL.md").write_text(texte, encoding="utf-8", newline="\n")
    for f in sorted(refs.glob("*.md")):
        t, k = remplacer_cli(f.read_text(encoding="utf-8").replace("\r\n", "\n"))
        for ancien, nouveau in CONSEILS_PIP:
            t = t.replace(ancien, nouveau)
        n += k
        (DEST / "references" / f.name).write_text(t, encoding="utf-8", newline="\n")
    reprises = [l for l in LICENCES if (src / l).is_file()]
    for l in reprises:
        shutil.copy2(src / l, DEST / l)
    if not reprises:
        print("ATTENTION : aucune licence reprise (LICENSE, LICENSE-MIT, NOTICE absents de la source).")

    DEST.joinpath("VERSION-AOI.txt").write_text(
        f"Origine      : {ORIGINE} (graphify/skill-windows.md, graphify/skills/windows/references)\n"
        f"Version      : {version}\n"
        f"Commit       : {commit}\n"
        f"Source       : {src}\n"
        f"Généré le    : {datetime.date.today():%d.%m.%Y} par python-aoi/adapter_skill_graphify.py (construire.ps1)\n"
        f"Licences     : {', '.join(reprises) or 'aucune reprise'}\n"
        "Adaptations  : étape 1 et garde de l'interpréteur remplacées (Python AOI, aucune installation) ;\n"
        f"               {n} appels « graphify … » remplacés par « python.exe -m graphify … » du Python AOI ;\n"
        "               conseils « pip install … » de la prose renvoyés à l'IT. Le reste est le texte d'origine.\n",
        encoding="utf-8", newline="\n")
    print(f"Skill graphify générée dans {DEST} : version {version}, commit {commit}, "
          f"{n} appels en ligne de commande adaptés, {len(reprises)} licences reprises")


if __name__ == "__main__":
    main()
