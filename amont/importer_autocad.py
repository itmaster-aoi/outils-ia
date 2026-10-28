"""Importe une version de lfoletti/autocad-mcp dans le serveur autocad du plugin (réservé à l'IT).

    amont/importer_autocad.py <clone>                          copie seulement
    amont/importer_autocad.py <clone> --plugin AAAA.MM.JJ.N    copie et nouvelle version du plugin

<clone> est un clone de https://github.com/lfoletti/autocad-mcp, fait hors de Claude Code et placé
sur une étiquette relue (git checkout vX.Y.Z), sans modification locale. Le script refuse tout autre état.

Écrit plugins/aoi/mcp/autocad/ :

    README.md, LICENSE   repris tels quels de integration/plugin/mcp/autocad/ du projet
    addin.json           fiche de l'add-in, lue par upgrader-outils.cmd ; l'entrée « archive » déjà écrite par construire.py est gardée
    VERSION-AOI.txt      origine, étiquette, commit, archive, empreinte SHA-256 de chaque fichier

Le serveur ne vient pas d'ici : c'est l'add-in compilé (le serveur MCP tourne dans AutoCAD), livré par
l'archive autocad-addin-<version>. Pour la construire à partir du clone :

    powershell -NoProfile -ExecutionPolicy Bypass -File <clone>\\outils\\preparer-archive.ps1
    plugins/aoi/controle/runtime/python.exe archives/construire.py autocad-addin <AAAA-MM-JJ>

Le script vérifie que les DLL de cette archive portent le commit importé (version « X.Y.Z+<commit> »).
Sinon il le signale, et refuse --plugin : la fiche doit désigner une archive construite à partir de l'étiquette.

Avec --plugin, écrit aussi la version dans plugin.json, la ligne autocad de VERSIONS.md et un brouillon
d'entrée en tête de CHANGELOG.md, à compléter à la main. N'utilise que la bibliothèque standard.
"""
import argparse
import datetime
import hashlib
import json
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
PLUGIN = RACINE / "plugins" / "aoi"
DEST = PLUGIN / "mcp" / "autocad"
ORIGINE = "https://github.com/lfoletti/autocad-mcp"
SOURCE = "integration/plugin/mcp/autocad"
REPRIS = ("README.md", "LICENSE")
OUTILS = "addin/AoiAutoCad.Mcp"
NOM = "AutoCAD 2027"


def git(clone, *args):
    r = subprocess.run(["git", "-C", str(clone), *args], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None


def sha256(chemin):
    return hashlib.sha256(Path(chemin).read_bytes()).hexdigest()


def controler(clone):
    """(étiquette, commit, version) d'un clone propre, posé sur une étiquette vX.Y.Z ; sinon arrêt."""
    if git(clone, "rev-parse", "--is-inside-work-tree") != "true":
        sys.exit(f"{clone} n'est pas un dépôt git : cloner {ORIGINE} hors de Claude Code.")
    distant = git(clone, "remote", "get-url", "origin") or ""
    if not re.search(r"github\.com[/:]lfoletti/autocad-mcp(\.git)?$", distant):
        sys.exit(f"Dépôt d'origine inattendu : « {distant} » (attendu {ORIGINE}).")
    tag = git(clone, "describe", "--exact-match", "--tags", "HEAD")
    if not tag or not re.fullmatch(r"v\d+\.\d+\.\d+", tag):
        sys.exit(f"HEAD n'est pas sur une étiquette vX.Y.Z (git checkout vX.Y.Z), trouvé : {tag}.")
    if git(clone, "status", "--porcelain", "--untracked-files=no"):
        sys.exit("Le clone a des modifications locales : seule une étiquette relue, sans changement, est importée.")
    commit = git(clone, "rev-parse", "HEAD")
    props = clone / "addin" / "Directory.Build.props"
    m = re.search(r"<Version>([^<]+)</Version>", props.read_text(encoding="utf-8"))
    if not m:
        sys.exit(f"<Version> introuvable dans {props} (le projet d'origine a changé, adapter ce script)")
    if m.group(1) != tag[1:]:
        sys.exit(f"Versions incohérentes : étiquette {tag}, add-in {m.group(1)}.")
    return tag, commit, m.group(1)


def compter(clone):
    """(nombre d'outils, nombre de prompts) : attributs [McpServerTool] et [McpServerPrompt] du C#."""
    texte = "".join(f.read_text(encoding="utf-8") for f in (clone / OUTILS).glob("*.cs"))
    return len(re.findall(r"\[McpServerTool\b(?!Type)", texte)), len(re.findall(r"\[McpServerPrompt\b(?!Type)", texte))


def nuget(clone):
    """Paquets NuGet des projets livrés (sans les tests), « Nom Version », triés."""
    paquets = set()
    for f in (clone / "addin").glob("*/*.csproj"):
        if f.parent.name.endswith(".Tests"):
            continue
        paquets |= set(re.findall(r'<PackageReference\s+Include="([^"]+)"\s+Version="([^"]+)"', f.read_text(encoding="utf-8")))
    return sorted(f"{n} {v}" for n, v in paquets)


def copier(clone):
    """README.md et LICENSE tels quels ; addin.json du projet, avec l'archive déjà inscrite. Renvoie l'archive."""
    source = clone / SOURCE
    for rel in REPRIS:
        if not (source / rel).is_file():
            sys.exit(f"{SOURCE}/{rel} absent du clone (le projet d'origine a changé, adapter REPRIS)")
        shutil.copy2(source / rel, DEST / rel)
    actuelle = json.loads((DEST / "addin.json").read_text(encoding="utf-8")) if (DEST / "addin.json").is_file() else {}
    archive = next((e.get("archive") for e in actuelle.get("add-ins", []) if e.get("nom") == NOM), None)
    fiche = json.loads((source / "addin.json").read_text(encoding="utf-8"))
    entree = next((e for e in fiche["add-ins"] if e.get("nom") == NOM), None)
    if entree is None:
        sys.exit(f"Entrée « {NOM} » absente de {SOURCE}/addin.json")
    if archive:
        entree.pop("source", None)
        entree["archive"] = archive
    (DEST / "addin.json").write_text(json.dumps(fiche, ensure_ascii=False, indent=2) + "\n",
                                     encoding="utf-8", newline="\n")
    return archive


def verifier_archive(archive, commit, version):
    """Message d'erreur si l'archive locale manque, diffère de la fiche ou vient d'un autre commit ; sinon None."""
    if not archive:
        return "addin.json n'a pas d'archive : lancer preparer-archive.ps1 depuis le clone, puis construire.py."
    zip_ = RACINE / "archives" / "dist" / f"autocad-addin-{archive['version']}.zip"
    if not zip_.is_file():
        return f"{zip_} introuvable : impossible de vérifier de quel commit vient l'archive."
    if sha256(zip_) != archive["sha256"]:
        return f"{zip_.name} ne correspond pas à l'empreinte de addin.json : relancer construire.py."
    vus = set()
    with zipfile.ZipFile(zip_) as z:
        for n in z.namelist():
            if re.search(r"(^|/)AoiAutoCad\.[^/]+\.dll$", n):
                vus |= {(v.decode(), c.decode()) for v, c in
                        re.findall(rb"(\d+\.\d+\.\d+)\+([0-9a-f]{40})", z.read(n))}
    if vus != {(version, commit)}:
        trouves = ", ".join(f"{v}+{c[:7]}" for v, c in sorted(vus)) or "aucune version lisible"
        return (f"l'archive {zip_.name} contient {trouves}, attendu {version}+{commit[:7]} : la reconstruire "
                "à partir du clone (preparer-archive.ps1, puis construire.py).")
    return None


def versionner(plugin, tag, commit, version, outils, archive, paquets):
    """plugin.json, ligne autocad de VERSIONS.md, brouillon d'entrée du CHANGELOG."""
    if not re.fullmatch(r"\d{4}\.\d{2}\.\d{2}\.\d+", plugin):
        sys.exit(f"--plugin attend AAAA.MM.JJ.N, reçu {plugin}")
    pj = PLUGIN / ".claude-plugin" / "plugin.json"
    texte = pj.read_text(encoding="utf-8")
    pj.write_text(re.sub(r'("version":\s*")[^"]+(")', rf"\g<1>{plugin}\g<2>", texte, count=1),
                  encoding="utf-8", newline="\n")

    jour = datetime.date.today().strftime("%d.%m.%Y")
    ref = f"[lfoletti/autocad-mcp]({ORIGINE}), étiquette `{tag}`, commit `{commit}`"
    debut = "| `autocad` |"
    ligne = (
        f"{debut} add-in AutoCAD 2027, qui est aussi le serveur MCP (HTTP `127.0.0.1:1997/mcp`, entrée `autocad` "
        f"de `.mcp.json`) ; archive `autocad-addin-{archive['version']}` publiée à part, SHA-256 `{archive['sha256']}`, "
        "fiche `plugins/aoi/mcp/autocad/addin.json`, copié dans "
        "`%APPDATA%\\Autodesk\\ApplicationPlugins\\aoi-autocad-mcp.bundle` "
        f"| {ref} (importé par `amont/importer_autocad.py`, voir `mcp/autocad/VERSION-AOI.txt`) ; construit par "
        f"`outils/preparer-archive.ps1` ; NuGet {', '.join(f'`{p}`' for p in paquets) or 'aucun'} et leurs dépendances "
        f"| {version} : {outils} outils ; `execute_lisp` et `run_command` **actifs** (`\"enable_execute\": false` dans "
        "`%LOCALAPPDATA%\\autocad-mcp\\config.json` les ferme) ; sans jeton ; DLL non signées "
        f"| MIT | {jour} |")
    vf = RACINE / "VERSIONS.md"
    lignes = vf.read_text(encoding="utf-8").split("\n")
    i = next((i for i, l in enumerate(lignes) if l.startswith(debut)), None)
    if i is None:
        sys.exit(f"Ligne « {debut} » introuvable dans VERSIONS.md")
    lignes[i] = ligne
    vf.write_text("\n".join(lignes), encoding="utf-8", newline="\n")

    cf = RACINE / "CHANGELOG.md"
    texte = cf.read_text(encoding="utf-8")
    titre = f"## {plugin.rsplit('.', 1)[0].replace('.', '-')}.{plugin.rsplit('.', 1)[1]} (plugin {plugin})"
    if titre not in texte:
        entree = (f"{titre}\n\n- Serveur `plugin:aoi:autocad` : autocad-mcp {version}, importé de {ref} "
                  f"par `amont/importer_autocad.py`, archive `autocad-addin-{archive['version']}`. {outils} outils. "
                  "À COMPLÉTER : changements visibles.\n\n")
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
    paquets = nuget(clone)

    DEST.mkdir(parents=True, exist_ok=True)
    archive = copier(clone)
    probleme = verifier_archive(archive, commit, version)
    fichiers = sorted(p.name for p in DEST.iterdir() if p.is_file() and p.name != "VERSION-AOI.txt")
    empreintes = "".join(f"  {sha256(DEST / f)}  {f}\n" for f in fichiers)
    DEST.joinpath("VERSION-AOI.txt").write_text(
        f"Origine      : {ORIGINE}\n"
        f"Étiquette    : {tag}\n"
        f"Commit       : {commit}\n"
        f"Version      : add-in et serveur {version}, {outils} outils, {prompts} prompt(s)\n"
        f"NuGet        : {', '.join(paquets) or 'aucun'} (et leurs dépendances)\n"
        f"Archive      : " + (f"autocad-addin-{archive['version']}, SHA-256 {archive['sha256']}"
                              + (" (NON VÉRIFIÉE)" if probleme else f", DLL {version}+{commit[:7]}")
                              if archive else "aucune") + "\n"
        f"Importé le   : {datetime.date.today():%d.%m.%Y} par amont/importer_autocad.py\n"
        f"Repris       : {SOURCE}/ ({', '.join(REPRIS)}, addin.json)\n"
        "Adaptations  : aucune. addin.json garde l'archive écrite par archives/construire.py. Généré : ce fichier.\n"
        f"SHA-256      :\n{empreintes}",
        encoding="utf-8", newline="\n")
    print(f"autocad-mcp {tag} ({commit[:7]}) importé dans {DEST} : {outils} outils, {prompts} prompt(s)")

    if probleme:
        print("ATTENTION :", probleme)
        print(f"  powershell -NoProfile -ExecutionPolicy Bypass -File \"{clone / 'outils' / 'preparer-archive.ps1'}\"")
        print(f"  \"{PLUGIN / 'controle' / 'runtime' / 'python.exe'}\" \"{RACINE / 'archives' / 'construire.py'}\" "
              f"autocad-addin {datetime.date.today():%Y-%m-%d}")
        if a.plugin:
            sys.exit("--plugin refusé tant que l'archive ne vient pas de l'étiquette importée.")
    if a.plugin:
        titre = versionner(a.plugin, tag, commit, version, outils, archive, paquets)
        etiquette = titre.split()[1]
        print(f"plugin.json → {a.plugin}, VERSIONS.md mis à jour, CHANGELOG : compléter l'entrée « {titre} ».")
        print(f"Ensuite : git diff, claude plugin validate . et ./plugins/aoi, commit, gh release create "
              f"autocad-addin-{archive['version']} (commande de construire.py), git tag {etiquette}, "
              f"git push origin main {etiquette}, puis l'IT met la console sur {etiquette}.")


if __name__ == "__main__":
    main()
