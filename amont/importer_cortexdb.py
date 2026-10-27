"""Importe les commandes /remember et /recall d'une version de cortexdb dans le plugin (réservé à l'IT).

    amont/importer_cortexdb.py <clone>                          copie seulement
    amont/importer_cortexdb.py <clone> --plugin AAAA.MM.JJ.N    copie et nouvelle version du plugin

<clone> est un clone de https://github.com/itmaster-aoi/cortexdb (fork de liliang-cn/cortexdb), fait hors
de Claude Code et placé sur une étiquette relue (git checkout vX.Y.Z), sans modification locale. Le script
refuse tout autre état.

Écrit :

    plugins/aoi/commands/remember.md, recall.md    repris tels quels : ils n'appellent que les outils MCP
    plugins/aoi/mcp/cortexdb/LICENSE                licence MIT du projet d'origine
    plugins/aoi/mcp/cortexdb/README.md              mode d'emploi pour l'atelier
    plugins/aoi/mcp/cortexdb/VERSION-AOI.txt        origine, étiquette, commit, empreinte SHA-256 de chaque fichier

Le serveur ne vient pas d'ici : c'est le binaire publié par l'auteur pour cette étiquette, mis en archive
par archives/construire.py cortexdb-server <version>. Ne sont pas repris : la skill d'origine (documentation
de la librairie Go), les 11 autres commandes (elles lancent le binaire en bash depuis le dossier de données
du plugin d'origine), bin/, hooks/, .mcp.json et le mod cortexdb-live.

Avec --plugin, écrit aussi la version dans plugin.json, la ligne des commandes cortexdb de VERSIONS.md
et un brouillon d'entrée en tête de CHANGELOG.md, à compléter à la main.

Signale sans rien corriger : un bloc de code, un chemin bin/, une variable CORTEXDB_ ou une adresse http
dans les commandes reprises. N'utilise que la bibliothèque standard.
"""
import argparse
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
DEST = PLUGIN / "mcp" / "cortexdb"
COMMANDES = PLUGIN / "commands"
ORIGINE = "https://github.com/itmaster-aoi/cortexdb"
AMONT = "https://github.com/liliang-cn/cortexdb"
SOURCE = "plugins/cortexdb"
REPRIS = ("commands/remember.md", "commands/recall.md")
SUSPECTS = re.compile(r"```|\bbin/|CORTEXDB_\w+|https?://\S+")

README = """# cortexdb

Mémoire d'agent et graphe de connaissances dans un seul fichier SQLite. Projet d'origine : [liliang-cn/cortexdb]({amont}), repris par le fork [itmaster-aoi/cortexdb]({origine}), étiquette `{tag}` (commit `{commit_court}`). Voir `VERSION-AOI.txt`.

| Élément | Origine |
|---|---|
| serveur `plugin:aoi:cortexdb` | binaire `cortexdb-mcp-windows-amd64.exe` publié par l'auteur pour `{tag}`, renommé `cortexdb-mcp.exe`, livré par l'archive `cortexdb-server-{version}` (fiche `plugins/aoi/cortexdb-server-aoi.json`) et installé par `/regen` dans `%LOCALAPPDATA%\\aoi\\cortexdb-server-{version}` |
| `/aoi:remember`, `/aoi:recall` | `commands/remember.md` et `commands/recall.md` du plugin d'origine, repris tels quels par `amont/importer_cortexdb.py` |
| skill `/aoi:cortexdb` | écrite pour l'atelier (`skills/cortexdb/SKILL.md`) |
| `LICENSE` | licence MIT du projet d'origine |

## Données

La base est `%USERPROFILE%\\.cortexdb\\cortexdb.db`, sur le poste de l'utilisateur. `plugins/aoi/.mcp.json` vide les variables des services externes (`OPENAI_*`, `CORTEXDB_EMBED_*`, `CORTEXDB_LLM_*`, `CORTEXDB_RERANK_*`) et celles du serveur partagé (`CORTEXDB_REMOTE`, `CORTEXDB_GRPC_TOKEN`). Le serveur travaille donc en mode lexical, sans service externe. Les fonctions qui demandent un modèle de langage restent inactives.

Non repris : la skill d'origine (documentation de la librairie Go), les 11 autres commandes, les crochets (rappel à chaque requête, contexte avant chaque lecture de fichier), le mod `cortexdb-live`.

## Vérification

1. `/mcp` montre `plugin:aoi:cortexdb` connecté.
2. `/aoi:remember Test : le poste de l'IT utilise cortexdb.`
3. `/aoi:recall cortexdb` retrouve ce fait.

## Licence

MIT, « Copyright (c) 2025 liliang-cn » (`LICENSE`).
"""


def git(clone, *args):
    r = subprocess.run(["git", "-C", str(clone), *args], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None


def controler(clone):
    """(étiquette, commit, version) d'un clone propre, posé sur une étiquette vX.Y.Z ; sinon arrêt."""
    if git(clone, "rev-parse", "--is-inside-work-tree") != "true":
        sys.exit(f"{clone} n'est pas un dépôt git : cloner {ORIGINE} hors de Claude Code.")
    distant = git(clone, "remote", "get-url", "origin") or ""
    if not re.search(r"github\.com[/:]itmaster-aoi/cortexdb(\.git)?$", distant):
        sys.exit(f"Dépôt d'origine inattendu : « {distant} » (attendu {ORIGINE}).")
    tag = git(clone, "describe", "--exact-match", "--tags", "HEAD")
    if not tag or not re.fullmatch(r"v\d+\.\d+\.\d+", tag):
        sys.exit(f"HEAD n'est pas sur une étiquette vX.Y.Z (git checkout vX.Y.Z), trouvé : {tag}.")
    if git(clone, "status", "--porcelain", "--untracked-files=no"):
        sys.exit("Le clone a des modifications locales : seule une étiquette relue, sans changement, est importée.")
    commit = git(clone, "rev-parse", "HEAD")
    manifeste = clone / SOURCE / ".claude-plugin" / "plugin.json"
    version = json.loads(manifeste.read_text(encoding="utf-8")).get("version")
    if version != tag[1:]:
        sys.exit(f"Versions incohérentes : étiquette {tag}, plugin d'origine {version}.")
    return tag, commit, version


def copier(clone):
    """Copie les commandes et la licence. Renvoie {chemin relatif au plugin : fichier}."""
    DEST.mkdir(parents=True, exist_ok=True)
    COMMANDES.mkdir(parents=True, exist_ok=True)
    copies = {}
    for rel in REPRIS:
        src = clone / SOURCE / rel
        if not src.is_file():
            sys.exit(f"{SOURCE}/{rel} absent du clone (le projet d'origine a changé, adapter REPRIS)")
        cible = COMMANDES / src.name
        shutil.copy2(src, cible)
        copies[cible.relative_to(PLUGIN).as_posix()] = cible
    shutil.copy2(clone / "LICENSE", DEST / "LICENSE")
    copies["mcp/cortexdb/LICENSE"] = DEST / "LICENSE"
    return copies


def verifier(copies):
    """Messages d'avertissement : ce qui, dans une commande reprise, dépasse l'appel des outils MCP."""
    alertes = []
    for rel, f in copies.items():
        if not rel.startswith("commands/"):
            continue
        for n, ligne in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            for m in SUSPECTS.finditer(ligne):
                alertes.append(f"{rel}:{n} : « {m.group(0)} » (relire : la commande doit n'appeler que les outils MCP).")
    return alertes


def versionner(plugin, tag, commit):
    """plugin.json, ligne des commandes cortexdb de VERSIONS.md, brouillon d'entrée du CHANGELOG."""
    if not re.fullmatch(r"\d{4}\.\d{2}\.\d{2}\.\d+", plugin):
        sys.exit(f"--plugin attend AAAA.MM.JJ.N, reçu {plugin}")
    pj = PLUGIN / ".claude-plugin" / "plugin.json"
    texte = pj.read_text(encoding="utf-8")
    pj.write_text(re.sub(r'("version":\s*")[^"]+(")', rf"\g<1>{plugin}\g<2>", texte, count=1),
                  encoding="utf-8", newline="\n")

    jour = datetime.date.today().strftime("%d.%m.%Y")
    ref = f"fork [itmaster-aoi/cortexdb]({ORIGINE}) de [liliang-cn/cortexdb]({AMONT}), étiquette `{tag}`, commit `{commit}`"
    debut = "| `cortexdb` | commandes"
    ligne = (f"{debut} `/aoi:remember` et `/aoi:recall` (`commands/`, importées par `amont/importer_cortexdb.py`, "
             f"voir `mcp/cortexdb/VERSION-AOI.txt`) | {ref}, `plugins/cortexdb/commands/` | {tag[1:]}, reprises "
             f"telles quelles ; skill et 11 autres commandes non reprises | MIT | {jour} |")
    vf = RACINE / "VERSIONS.md"
    lignes = vf.read_text(encoding="utf-8").split("\n")
    i = next((i for i, l in enumerate(lignes) if l.startswith(debut)), None)
    if i is None:
        sys.exit(f"Ligne introuvable dans VERSIONS.md : {debut}")
    lignes[i] = ligne
    vf.write_text("\n".join(lignes), encoding="utf-8", newline="\n")

    cf = RACINE / "CHANGELOG.md"
    texte = cf.read_text(encoding="utf-8")
    titre = f"## {plugin.rsplit('.', 1)[0].replace('.', '-')}.{plugin.rsplit('.', 1)[1]} (plugin {plugin})"
    if titre not in texte:
        entree = (f"{titre}\n\n- Commandes `/aoi:remember` et `/aoi:recall` : cortexdb {tag[1:]}, importées de {ref} "
                  "par `amont/importer_cortexdb.py`. À COMPLÉTER : serveur (archive `cortexdb-server`), "
                  "changements visibles.\n\n")
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

    copies = copier(clone)
    DEST.joinpath("README.md").write_text(
        README.format(amont=AMONT, origine=ORIGINE, tag=tag, commit_court=commit[:7], version=version),
        encoding="utf-8", newline="\n")
    empreintes = "".join(f"  {hashlib.sha256(f.read_bytes()).hexdigest()}  {rel}\n"
                         for rel, f in sorted(copies.items()))
    DEST.joinpath("VERSION-AOI.txt").write_text(
        f"Origine      : {ORIGINE} (fork de {AMONT})\n"
        f"Étiquette    : {tag}\n"
        f"Commit       : {commit}\n"
        f"Version      : {version}\n"
        f"Importé le   : {datetime.date.today():%d.%m.%Y} par amont/importer_cortexdb.py\n"
        f"Repris       : {', '.join(f'{SOURCE}/{r}' for r in REPRIS)}, LICENSE\n"
        "Adaptations  : aucune dans les fichiers repris. Générés pour l'atelier : README.md, ce fichier.\n"
        "Hors import  : serveur (archive cortexdb-server, archives/construire.py), skills/cortexdb (écrite par l'IT).\n"
        f"SHA-256 (chemins relatifs à plugins/aoi) :\n{empreintes}",
        encoding="utf-8", newline="\n")
    print(f"cortexdb {tag} ({commit[:7]}) importé : {', '.join(sorted(copies))}")

    for alerte in verifier(copies):
        print("ATTENTION :", alerte)
    if a.plugin:
        titre = versionner(a.plugin, tag, commit)
        etiquette = titre.split()[1]
        print(f"plugin.json → {a.plugin}, VERSIONS.md mis à jour, CHANGELOG : compléter l'entrée « {titre} ».")
        print("Ensuite : git diff, claude plugin validate . et ./plugins/aoi, commit, "
              f"git tag {etiquette}, git push origin main {etiquette}, puis l'IT met la console sur {etiquette}.")


if __name__ == "__main__":
    main()
