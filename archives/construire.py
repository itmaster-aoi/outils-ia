"""Construit l'archive d'une partie lourde des outils de l'atelier et écrit sa fiche dans le plugin.

    python archives/construire.py <nom> <version>
    nom : rhino-libs | revit-server | cortexdb-server | rhino-addin | revit-addin

Les parties lourdes (librairies, serveurs compilés, add-ins) ne sont plus dans le plugin : elles
sont publiées comme versions GitHub du dépôt (<nom>-<version>) et /regen ou l'installeur ne les
téléchargent que si leur version change. Leur empreinte SHA-256, écrite dans la fiche, est figée
par l'étiquette du plugin : une archive modifiée est refusée.

    archives/build/<nom>/              contenu de la partie (non publié, voir .gitignore)
    archives/dist/<nom>-<version>.zip  archive à publier (commande affichée à la fin)

À lancer avec le Python du plugin : plugins/aoi/controle/runtime/python.exe.
N'utilise que la bibliothèque standard.
"""
import hashlib
import json
import sys
import zipfile
from pathlib import Path

ICI = Path(__file__).resolve().parent
RACINE = ICI.parent
PLUGIN = RACINE / "plugins" / "aoi"
DEPOT = "itmaster-aoi/outils-ia"
EXCLUS_DOSSIERS = {"__pycache__"}
EXCLUS_SUFFIXES = {".pyc", ".db", ".sqlite", ".log"}

# Fiche « racine » : plugins/aoi/<nom>-aoi.json, installée dans %LOCALAPPDATA%\aoi\<nom>.
# Fiche « add-in » : entrée « archive » de plugins/aoi/mcp/<serveur>/addin.json.
PARTIES = {
    "rhino-libs":   {"titre": "Librairies Python du serveur Rhino", "fiche": "racine",
                     "temoin": "mcp/__init__.py"},
    "revit-server": {"titre": "Serveur MCP Revit", "fiche": "racine",
                     "temoin": "build/index.js", "conserver": ["revit-data.db"]},
    # Binaire publié par l'auteur (cortexdb-mcp-windows-amd64.exe), renommé cortexdb-mcp.exe
    "cortexdb-server": {"titre": "Serveur MCP CortexDB", "fiche": "racine",
                        "temoin": "cortexdb-mcp.exe"},
    "rhino-addin":  {"titre": "Add-in Rhino 8", "fiche": "addin", "serveur": "rhino", "nom": "Rhino 8"},
    "revit-addin":  {"titre": "Add-in Revit 2025", "fiche": "addin", "serveur": "revit", "nom": "Revit 2025"},
}

# Serveurs lancés depuis l'archive : entrée de .mcp.json et clé qui porte le chemin
MCP = {"revit-server": ("revit", "args"), "cortexdb-server": ("cortexdb", "command")}


def archiver(source, zip_):
    zip_.parent.mkdir(parents=True, exist_ok=True)
    zip_.unlink(missing_ok=True)
    n = 0
    with zipfile.ZipFile(zip_, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for f in sorted(source.rglob("*")):
            rel = f.relative_to(source)
            if f.is_file() and not (set(rel.parts) & EXCLUS_DOSSIERS) and f.suffix.lower() not in EXCLUS_SUFFIXES:
                z.write(f, rel.as_posix())
                n += 1
    return n


def sha256(chemin):
    h = hashlib.sha256()
    with open(chemin, "rb") as f:
        for bloc in iter(lambda: f.read(1 << 20), b""):
            h.update(bloc)
    return h.hexdigest()


def ecrire(chemin, donnees):
    chemin.write_text(json.dumps(donnees, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def main():
    if len(sys.argv) != 3 or sys.argv[1] not in PARTIES:
        sys.exit(f"Usage : construire.py <{'|'.join(PARTIES)}> <version>")
    nom, version = sys.argv[1], sys.argv[2]
    p = PARTIES[nom]
    source = ICI / "build" / nom
    if not source.is_dir():
        sys.exit(f"Dossier introuvable : {source}")
    if p.get("temoin") and not (source / p["temoin"]).is_file():
        sys.exit(f"Partie incomplète : {p['temoin']} absent de {source}")
    etiquette = f"{nom}-{version}"
    zip_ = ICI / "dist" / f"{etiquette}.zip"
    n = archiver(source, zip_)
    archive = {"version": version,
               "url": f"https://github.com/{DEPOT}/releases/download/{etiquette}/{etiquette}.zip",
               "sha256": sha256(zip_), "taille": zip_.stat().st_size}

    if p["fiche"] == "racine":
        # Installée dans %LOCALAPPDATA%\aoi\<nom>-<version> : le plugin désigne cette version.
        fiche = PLUGIN / f"{nom}-aoi.json"
        ecrire(fiche, {**archive, "versionne": True, "exe": p["temoin"],
                       **({"conserver": p["conserver"]} if p.get("conserver") else {})})
        if nom in MCP:  # .mcp.json lance le serveur de cette version
            serveur, cle = MCP[nom]
            chemin = f"${{LOCALAPPDATA}}/aoi/{nom}-{version}/{p['temoin']}"
            mcp = PLUGIN / ".mcp.json"
            d = json.loads(mcp.read_text(encoding="utf-8"))
            d["mcpServers"][serveur][cle] = [chemin] if cle == "args" else chemin
            ecrire(mcp, d)
        # rhino-libs : mcp/rhino/run.py lit lui-même la version dans rhino-libs-aoi.json
    else:
        fiche = PLUGIN / "mcp" / p["serveur"] / "addin.json"
        donnees = json.loads(fiche.read_text(encoding="utf-8"))
        entree = next(e for e in donnees["add-ins"] if e["nom"] == p["nom"])
        entree.pop("source", None)
        entree["archive"] = archive
        ecrire(fiche, donnees)

    print(f"Archive : {zip_} ({n} fichiers, {archive['taille'] / 2**20:.1f} Mo)")
    print(f"SHA-256 : {archive['sha256']}")
    print(f"Fiche   : {fiche}")
    print(f'Publier : gh release create {etiquette} "{zip_}" --repo {DEPOT} '
          f'--title "{p["titre"]} {version}" --notes "{p["titre"]} (voir VERSIONS.md). SHA-256 {archive["sha256"]}"')


if __name__ == "__main__":
    main()
