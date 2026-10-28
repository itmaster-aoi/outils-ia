"""Importe une version de lfoletti/keyshot-mcp dans le serveur keyshot du plugin (réservé à l'IT).

    amont/importer_keyshot.py <clone>                          copie seulement
    amont/importer_keyshot.py <clone> --plugin AAAA.MM.JJ.N    copie et nouvelle version du plugin

<clone> est un clone de https://github.com/lfoletti/keyshot-mcp, fait hors de Claude Code et placé
sur une étiquette relue (git checkout vX.Y.Z), sans modification locale. Le script refuse tout autre état.

Écrit plugins/aoi/mcp/keyshot/ (libs/ n'est pas touché) :

    run.py, server/, addin/Scripts/, LICENSE   repris tels quels : aucune adaptation du code
    addin.json                                 fiche de l'add-in, lue par upgrader-outils.cmd, avec les scripts des versions précédentes à retirer
    README.md                                  mode d'emploi pour l'atelier
    VERSION-AOI.txt                            origine, étiquette, commit, empreinte SHA-256 de chaque fichier

Avec --plugin, écrit aussi la version dans plugin.json, les lignes keyshot (serveur, pont) de VERSIONS.md
et un brouillon d'entrée en tête de CHANGELOG.md, à compléter à la main.

Signale sans rien corriger : une version de mcp différente de celle de libs/, et les imports du serveur
qui ne sont ni dans la bibliothèque standard, ni dans libs/ (à demander à l'IT pour la liste blanche).
N'utilise que la bibliothèque standard.
"""
import argparse
import ast
import datetime
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
PLUGIN = RACINE / "plugins" / "aoi"
DEST = PLUGIN / "mcp" / "keyshot"
ORIGINE = "https://github.com/lfoletti/keyshot-mcp"
REPRIS = ("run.py", "LICENSE", "server", "addin/Scripts")
IGNORES = ("__pycache__", "*.pyc", "*.pyo")
PONT = "addin/Scripts/MCP start.py"
ARRET = "addin/Scripts/MCP stop.py"
# Scripts KeyShot des versions précédentes, effacés de la destination par upgrader-outils.cmd avant la copie
ANCIENS_SCRIPTS = ["aoi_keyshot_bridge.py", "aoi_keyshot_stop.py", "MCP server start.py", "MCP server stop.py"]

ADDIN = {"add-ins": [{
    "nom": "KeyShot Studio",
    "si_existe": "%PUBLIC%/Documents/KeyShot Studio",
    "source": "addin/Scripts",
    "destination": "%PUBLIC%/Documents/KeyShot Studio/Scripts",
    "processus": "keyshot.exe",  # upgrader-outils.ps1 demande de fermer KeyShot ; maj.py ne copie pas s'il est ouvert
    "retirer": ANCIENS_SCRIPTS,
}]}

README = """# keyshot

Serveur MCP qui permet à Claude de piloter KeyShot Studio 2026 (fenêtre ouverte). Code repris tel quel de [lfoletti/keyshot-mcp]({origine}), étiquette `{tag}` (commit `{commit_court}`), par `amont/importer_keyshot.py` : voir `VERSION-AOI.txt`. Ne pas modifier ces fichiers à la main, les changements se font dans le projet d'origine puis passent par une nouvelle importation.

| Dossier | Contenu |
|---|---|
| `server/` | le serveur MCP `keyshotmcp` {version} : {outils} outils, prompts {prompts} |
| `addin/Scripts/` | le pont `MCP start.py` {version} et son script d'arrêt `MCP stop.py`, qui tournent dans KeyShot (stdlib et `lux` seulement) |
| `addin.json` | la fiche de l'add-in : `upgrader-outils.cmd` copie `addin/Scripts` dans `%PUBLIC%\\Documents\\KeyShot Studio\\Scripts` si KeyShot Studio a déjà été lancé sur le poste (dossier présent), après avoir effacé les scripts des versions précédentes (`MCP server start.py`, `MCP server stop.py`, `aoi_keyshot_*.py`) |
| `run.py` | le lanceur : il place `server/` et `libs/` (avec les dossiers de pywin32) en tête du chemin de recherche |
| `LICENSE` | licence MIT du projet d'origine |

Librairies : `libs/`, copie identique de celles du serveur rhino (liste de `VERSIONS.md`), hors importation. Elles restent dans ce dossier : le contrôle des imports n'accepte d'office que les modules situés sous le dossier du script lancé. Le serveur n'utilise que `mcp` et ses dépendances.

Le serveur tourne avec le **Python AOI** de l'atelier (`%LOCALAPPDATA%\\aoi\\python`), lancé avec `-I -S` comme le serveur rhino (`plugins/aoi/.mcp.json`).

## Fonctionnement

```
Claude Code ⇄ serveur keyshotmcp (stdio)
            ⇄ TCP 127.0.0.1:1998, trames 4 octets + JSON, jeton
            ⇄ MCP start.py dans KeyShot
```

Le pont écrit son port, son jeton et le pid de KeyShot dans `%LOCALAPPDATA%\\keyshot-mcp\\pont-actif.json`, et son journal dans `pont.log` du même dossier. Le serveur relit ce fichier à chaque connexion.

## Utilisation

1. Après `upgrader-outils.cmd`, redémarrer KeyShot une fois (il ne relit le dossier Scripts qu'à son démarrage).
2. Dans KeyShot : *Window > Scripting Console > Scripts > MCP start > Run*.
3. Dans Claude Code, `/mcp` montre `plugin:aoi:keyshot` ; l'outil `keyshot_status` doit répondre.
4. Arrêt : script `MCP stop`, ou fermeture de KeyShot. Après une mise à jour du pont par `upgrader-outils.cmd`, l'outil `reload_bridge` recharge le pont sans Run.

Réglages facultatifs, par poste : `%LOCALAPPDATA%\\keyshot-mcp\\pont-config.json` (avant la 1.0.0 : `%LOCALAPPDATA%\\aoi\\keyshot\\`, plus lu).
- `execute_python` : `false` par défaut ; seul `true` active l'outil (ou la variable `KEYSHOT_MCP_EXECUTE_PYTHON=1`).
- `dossier_sorties` : chemin absolu des captures, rendus et copies de sauvegarde.
- `dossiers_textures` : dossiers où les textures peuvent être lues (les chemins réseau sont refusés).

## Vérification

```
%LOCALAPPDATA%\\aoi\\python\\python.exe -I -S run.py --check
```
La commande doit afficher {outils} outils et des chemins qui pointent tous dans le plugin.

## Licence

MIT, « Copyright (c) 2026 Lauro Foletti » (`LICENSE`). Projet sans lien avec Luxion. Les licences des librairies se trouvent dans chaque dossier `libs/*.dist-info`.
"""


def git(clone, *args):
    r = subprocess.run(["git", "-C", str(clone), *args], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None


def lire_version(fichier, nom):
    m = re.search(rf'^{nom}\s*=\s*["\']([^"\']+)["\']', fichier.read_text(encoding="utf-8"), re.MULTILINE)
    if not m:
        sys.exit(f"{nom} introuvable dans {fichier} (le projet d'origine a changé, adapter ce script)")
    return m.group(1)


def controler(clone):
    """(étiquette, commit, version) d'un clone propre, posé sur une étiquette vX.Y.Z ; sinon arrêt."""
    if git(clone, "rev-parse", "--is-inside-work-tree") != "true":
        sys.exit(f"{clone} n'est pas un dépôt git : cloner {ORIGINE} hors de Claude Code.")
    distant = git(clone, "remote", "get-url", "origin") or ""
    if not re.search(r"github\.com[/:]lfoletti/keyshot-mcp(\.git)?$", distant):
        sys.exit(f"Dépôt d'origine inattendu : « {distant} » (attendu {ORIGINE}).")
    tag = git(clone, "describe", "--exact-match", "--tags", "HEAD")
    if not tag or not re.fullmatch(r"v\d+\.\d+\.\d+", tag):
        sys.exit(f"HEAD n'est pas sur une étiquette vX.Y.Z (git checkout vX.Y.Z), trouvé : {tag}.")
    if git(clone, "status", "--porcelain", "--untracked-files=no"):
        sys.exit("Le clone a des modifications locales : seule une étiquette relue, sans changement, est importée.")
    commit = git(clone, "rev-parse", "HEAD")
    serveur = lire_version(clone / "server" / "keyshotmcp" / "__init__.py", "__version__")
    pont = lire_version(clone / PONT, "BRIDGE_VERSION")
    if not serveur == pont == tag[1:]:
        sys.exit(f"Versions incohérentes : étiquette {tag}, serveur {serveur}, pont {pont}.")
    return tag, commit, serveur


def copier(clone):
    """Remplace tout le contenu de DEST sauf libs/. Renvoie les fichiers copiés (chemins relatifs, triés)."""
    for p in DEST.iterdir():
        if p.name == "libs":
            continue
        shutil.rmtree(p) if p.is_dir() else p.unlink()
    for rel in REPRIS:
        src = clone / rel
        if src.is_dir():
            shutil.copytree(src, DEST / rel, ignore=shutil.ignore_patterns(*IGNORES))
        elif src.is_file():
            (DEST / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, DEST / rel)
        else:
            sys.exit(f"{rel} absent du clone (le projet d'origine a changé, adapter REPRIS)")
    return sorted(p.relative_to(DEST).as_posix() for p in DEST.rglob("*")
                  if p.is_file() and p.relative_to(DEST).parts[0] != "libs")


def compter(clone):
    """(nombre d'outils, noms des prompts) par lecture du code : décorateurs .tool et .prompt."""
    outils, prompts = 0, []
    for f in (clone / "server").rglob("*.py"):
        for noeud in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if not isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for d in noeud.decorator_list:
                cible = d.func if isinstance(d, ast.Call) else d
                if isinstance(cible, ast.Attribute) and cible.attr == "tool":
                    outils += 1
                elif isinstance(cible, ast.Attribute) and cible.attr == "prompt":
                    prompts.append(noeud.name)
    return outils, sorted(prompts)


def modules_libs():
    """Noms de premier niveau importables depuis libs/ (et les dossiers pywin32 que run.py ajoute)."""
    noms = set()
    libs = DEST / "libs"
    for base in (libs, libs / "win32", libs / "win32" / "lib", libs / "pythonwin"):
        if not base.is_dir():
            continue
        for p in base.iterdir():
            if p.is_dir() and not p.name.endswith((".dist-info", ".data")):
                noms.add(p.name)
            elif p.suffix in (".py", ".pyd"):
                noms.add(p.name.split(".")[0])
    return noms


def verifier(clone):
    """Messages d'avertissement : version de mcp, imports introuvables."""
    alertes = []
    exige = re.search(r"mcp==([\w.]+)", (clone / "README.md").read_text(encoding="utf-8"))
    present = sorted(p.name[4:-len(".dist-info")] for p in (DEST / "libs").glob("mcp-*.dist-info"))
    if not exige:
        alertes.append("README d'origine : version de mcp introuvable (« mcp==… »), vérifier libs/ à la main.")
    elif present != [exige.group(1)]:
        alertes.append(f"mcp {exige.group(1)} demandé par le projet, {', '.join(present) or 'aucun'} dans libs/ : "
                       "libs/ à refaire par l'IT (et la liste de VERSIONS.md).")
    connus = set(sys.stdlib_module_names) | modules_libs() | {"keyshotmcp", "__future__"}
    manquants = set()
    for f in [clone / "run.py", *(clone / "server").rglob("*.py")]:
        for n in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if isinstance(n, ast.Import):
                manquants |= {a.name.split(".")[0] for a in n.names}
            elif isinstance(n, ast.ImportFrom) and n.level == 0 and n.module:
                manquants.add(n.module.split(".")[0])
    manquants -= connus
    if manquants:
        alertes.append(f"Imports hors stdlib et hors libs/ : {', '.join(sorted(manquants))} "
                       "(à ajouter à libs/, et à faire inscrire par l'IT dans controle/whitelist.txt).")
    return alertes


def versionner(plugin, tag, commit, version, outils, prompts):
    """plugin.json, lignes keyshot de VERSIONS.md, brouillon d'entrée du CHANGELOG."""
    if not re.fullmatch(r"\d{4}\.\d{2}\.\d{2}\.\d+", plugin):
        sys.exit(f"--plugin attend AAAA.MM.JJ.N, reçu {plugin}")
    pj = PLUGIN / ".claude-plugin" / "plugin.json"
    texte = pj.read_text(encoding="utf-8")
    pj.write_text(re.sub(r'("version":\s*")[^"]+(")', rf"\g<1>{plugin}\g<2>", texte, count=1),
                  encoding="utf-8", newline="\n")

    jour = datetime.date.today().strftime("%d.%m.%Y")
    ref = f"[lfoletti/keyshot-mcp]({ORIGINE}), étiquette `{tag}`, commit `{commit}`"
    lignes = {
        "| `keyshot` | serveur MCP": (
            f"| `keyshot` | serveur MCP (`mcp/keyshot/server`, importé par `amont/importer_keyshot.py`, "
            f"voir `mcp/keyshot/VERSION-AOI.txt`) | {ref} | {version} : {outils} outils, prompts "
            f"{', '.join(f'`{p}`' for p in prompts)} | MIT | {jour} |"),
        "| `keyshot` | pont dans KeyShot": (
            "| `keyshot` | pont dans KeyShot (`mcp/keyshot/addin/Scripts`, fiche `plugins/aoi/mcp/keyshot/addin.json`, "
            "copié dans `%PUBLIC%\\Documents\\KeyShot Studio\\Scripts`) | même origine (`MCP start.py` et `MCP stop.py`, "
            "anciennement `MCP server start.py`/`MCP server stop.py` et `aoi_keyshot_*.py`), stdlib et `lux` seulement "
            f"| {version} | MIT | {jour} |"),
    }
    vf = RACINE / "VERSIONS.md"
    sortie = []
    for ligne in vf.read_text(encoding="utf-8").split("\n"):
        debut = next((d for d in lignes if ligne.startswith(d)), None)
        sortie.append(lignes.pop(debut) if debut else ligne)
    if lignes:
        sys.exit(f"Lignes introuvables dans VERSIONS.md : {', '.join(lignes)}")
    vf.write_text("\n".join(sortie), encoding="utf-8", newline="\n")

    cf = RACINE / "CHANGELOG.md"
    texte = cf.read_text(encoding="utf-8")
    titre = f"## {plugin.rsplit('.', 1)[0].replace('.', '-')}.{plugin.rsplit('.', 1)[1]} (plugin {plugin})"
    if titre not in texte:
        entree = (f"{titre}\n\n- Serveur `plugin:aoi:keyshot` : keyshot-mcp {version}, importé de {ref} "
                  f"par `amont/importer_keyshot.py`. {outils} outils. À COMPLÉTER : changements visibles.\n\n")
        i = texte.find("\n## ") + 1
        cf.write_text(texte[:i] + entree + texte[i:], encoding="utf-8", newline="\n")
    return titre


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("clone", type=Path)
    ap.add_argument("--plugin", help="nouvelle version du plugin, AAAA.MM.JJ.N")
    a = ap.parse_args()
    clone = a.clone.resolve()
    tag, commit, version = controler(clone)
    outils, prompts = compter(clone)

    fichiers = copier(clone)
    DEST.joinpath("addin.json").write_text(json.dumps(ADDIN, ensure_ascii=False, indent=2) + "\n",
                                           encoding="utf-8", newline="\n")
    DEST.joinpath("README.md").write_text(
        README.format(origine=ORIGINE, tag=tag, commit_court=commit[:7], version=version, outils=outils,
                      prompts=", ".join(f"`{p}`" for p in prompts)), encoding="utf-8", newline="\n")
    empreintes = "".join(f"  {hashlib.sha256((DEST / f).read_bytes()).hexdigest()}  {f}\n" for f in fichiers)
    DEST.joinpath("VERSION-AOI.txt").write_text(
        f"Origine      : {ORIGINE}\n"
        f"Étiquette    : {tag}\n"
        f"Commit       : {commit}\n"
        f"Version      : serveur et pont {version}, {outils} outils, prompts {', '.join(prompts)}\n"
        f"Importé le   : {datetime.date.today():%d.%m.%Y} par amont/importer_keyshot.py\n"
        f"Repris       : {', '.join(REPRIS)} (sans __pycache__)\n"
        "Adaptations  : aucune dans le code. Générés pour l'atelier : addin.json, README.md, ce fichier.\n"
        "Hors import  : libs/ (copie des librairies de rhino, voir VERSIONS.md).\n"
        f"SHA-256      :\n{empreintes}",
        encoding="utf-8", newline="\n")
    print(f"keyshot-mcp {tag} ({commit[:7]}) importé dans {DEST} : {len(fichiers)} fichiers, "
          f"{outils} outils, prompts {', '.join(prompts)}")

    for alerte in verifier(clone):
        print("ATTENTION :", alerte)
    if a.plugin:
        titre = versionner(a.plugin, tag, commit, version, outils, prompts)
        etiquette = titre.split()[1]
        print(f"plugin.json → {a.plugin}, VERSIONS.md mis à jour, CHANGELOG : compléter l'entrée « {titre} ».")
        print("Ensuite : git diff, claude plugin validate . et ./plugins/aoi, commit, "
              f"git tag {etiquette}, git push origin main {etiquette}, puis l'IT met la console sur {etiquette}.")


if __name__ == "__main__":
    main()
