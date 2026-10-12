"""Met le plugin aoi à l'étiquette imposée par la console, sans passer par installer-poste.ps1.

    maj.py              état du poste, sans rien changer
    maj.py --appliquer  inscrit le catalogue à l'étiquette imposée, met le plugin à jour,
                        recopie les add-ins Rhino et Revit s'ils ont changé

N'utilise que la bibliothèque standard. L'étiquette vient toujours des managed settings
(~/.claude/remote-settings.json) : ce script ne choisit jamais lui-même une version.
"""
import argparse
import filecmp
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

DEPOT = "itmaster-aoi/outils-ia"
PLUGIN = "aoi@aoi"
CLAUDE = Path.home() / ".claude"

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def lire_json(chemin):
    try:
        return json.loads(Path(chemin).read_text(encoding="utf-8"))
    except Exception:
        return None


def ref_imposee():
    pol = lire_json(CLAUDE / "remote-settings.json") or {}
    return (((pol.get("extraKnownMarketplaces") or {}).get("aoi") or {}).get("source") or {}).get("ref")


def ref_inscrite():
    ins = lire_json(CLAUDE / "plugins" / "known_marketplaces.json") or {}
    return ((ins.get("aoi") or {}).get("source") or {}).get("ref")


def plugin_installe():
    d = lire_json(CLAUDE / "plugins" / "installed_plugins.json") or {}
    entrees = (d.get("plugins") or d).get(PLUGIN) or []
    if not entrees:
        return None
    e = entrees[0]
    chemin = Path(e.get("installPath", ""))
    return {"version": e.get("version"), "chemin": chemin} if chemin.is_dir() else None


def serveurs(plugin):
    if not plugin:
        return []
    mcp = lire_json(plugin["chemin"] / ".mcp.json") or {}
    return sorted(mcp.get("mcpServers", {}))


def claude(*args):
    exe = shutil.which("claude")
    if not exe:
        raise SystemExit("Commande « claude » introuvable : lancez installer-poste.cmd.")
    env = dict(os.environ, CLAUDE_CODE_PLUGIN_PREFER_HTTPS="1")
    # Une session par clé API ne reçoit pas les managed settings : la commande doit
    # passer par le compte claude.ai de l'atelier.
    env.pop("ANTHROPIC_API_KEY", None)
    print(f"  > claude {' '.join(args)}")
    r = subprocess.run([exe, *args], env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    sortie = (r.stdout + r.stderr).strip()
    if sortie:
        print("    " + sortie.replace("\n", "\n    "))
    return r.returncode == 0


def processus_actifs(*noms):
    try:
        r = subprocess.run(["tasklist", "/fo", "csv", "/nh"], capture_output=True, text=True, errors="replace")
        lances = {l.split(",")[0].strip('"').lower() for l in r.stdout.splitlines() if l}
        return [n for n in noms if n.lower() in lances]
    except Exception:
        return []


def deja_copie(source, dst):
    """Vrai si chaque fichier de source existe dans dst avec le même contenu."""
    for f in source.rglob("*"):
        if f.is_file():
            g = dst / f.relative_to(source)
            if not (g.is_file() and filecmp.cmp(f, g, shallow=False)):
                return False
    return True


def addins(plugin):
    """Add-ins décrits par mcp/<serveur>/addin.json : un serveur sans ce fichier n'a pas d'add-in.

    (nom, dossier source dans le plugin, dossier de destination, processus à fermer, fichiers à sauvegarder)
    Seules les applications déjà lancées sur ce compte (dossier « si_existe ») sont traitées.
    """
    liste = []
    for manifeste in sorted((plugin["chemin"] / "mcp").glob("*/addin.json")):
        for e in (lire_json(manifeste) or {}).get("add-ins", []):
            source = manifeste.parent / e["source"]
            temoin = Path(os.path.expandvars(e.get("si_existe", e["destination"])))
            if source.is_dir() and temoin.is_dir():
                liste.append((e["nom"], source, Path(os.path.expandvars(e["destination"])),
                              e.get("processus", ""), e.get("sauvegarder", [])))
    return liste


def copier_addin(nom, source, dst, proc, sauvegarder, appliquer):
    if deja_copie(source, dst):
        print(f"  {nom} : add-in à jour")
        return True
    if not appliquer:
        print(f"  {nom} : add-in à recopier")
        return False
    if proc and processus_actifs(proc):
        print(f"  {nom} : add-in à recopier, mais {proc} est ouvert. Fermez-le puis relancez /regen.")
        return False
    dst.mkdir(parents=True, exist_ok=True)
    for rel in sauvegarder:
        f = dst / rel
        if f.is_file():
            shutil.copy2(f, f.with_name(f.name + time.strftime(".avant-aoi-%Y%m%d-%H%M%S")))
    shutil.copytree(source, dst, dirs_exist_ok=True)
    print(f"  {nom} : add-in recopié vers {dst}")
    return True


def controle(plugin, verifier):
    """Contrôle des imports Python : copie dans C:\\ProgramData\\aoi (skill report du plugin)."""
    script = plugin["chemin"] / "skills" / "report" / "scripts" / "activer_controle.py"
    if script.is_file():
        r = subprocess.run([sys.executable, str(script)] + (["--verifier"] if verifier else []),
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        print("  " + (r.stdout + r.stderr).strip().replace("\n", "\n  "))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--appliquer", action="store_true")
    a = ap.parse_args()

    imposee, inscrite, avant = ref_imposee(), ref_inscrite(), plugin_installe()
    print(f"Étiquette imposée par la console : {imposee or 'aucune (règles non reçues)'}")
    print(f"Étiquette inscrite sur ce poste  : {inscrite or 'aucune'}")
    print(f"Plugin installé                  : {avant['version'] if avant else 'aucun'}")
    print(f"Serveurs du plugin installé      : {', '.join('plugin:aoi:' + s for s in serveurs(avant)) or 'aucun'}")

    if not imposee:
        print("\nRÈGLES NON REÇUES : la session doit être connectée avec le compte claude.ai de l'atelier "
              "(pas de clé API). Rien n'a été modifié.")
        return 2

    a_jour = inscrite == imposee and avant is not None
    if not a.appliquer:
        print("\nÉTAT : " + ("catalogue à jour." if a_jour else f"mise à jour disponible vers {imposee}."))
        if avant:
            for x in addins(avant):
                copier_addin(*x, appliquer=False)
            controle(avant, verifier=True)
        return 0

    print()
    if inscrite != imposee:
        if inscrite:
            claude("plugin", "marketplace", "remove", "aoi")
        if not claude("plugin", "marketplace", "add", f"{DEPOT}#{imposee}"):
            print("\nÉCHEC : inscription du catalogue refusée. Vérifiez la connexion et les règles de la console.")
            return 1
    # Retirer le catalogue désinstalle aussi son plugin : on regarde à nouveau ce qui reste.
    if plugin_installe() is None:
        ok = claude("plugin", "install", PLUGIN)
    else:
        ok = claude("plugin", "update", PLUGIN)
    apres = plugin_installe()
    if not ok or apres is None:
        print("\nÉCHEC : le plugin n'a pas pu être installé ou mis à jour.")
        return 1

    nouveaux = sorted(set(serveurs(apres)) - set(serveurs(avant)))
    retires = sorted(set(serveurs(avant)) - set(serveurs(apres)))
    print(f"\nPlugin : {avant['version'] if avant else 'aucun'} -> {apres['version']}")
    print(f"Nouveaux serveurs : {', '.join('plugin:aoi:' + s for s in nouveaux) or 'aucun'}")
    if retires:
        print(f"Serveurs retirés  : {', '.join('plugin:aoi:' + s for s in retires)}")
    for x in addins(apres):
        copier_addin(*x, appliquer=True)
    controle(apres, verifier=False)
    if avant is None or apres["version"] != avant["version"]:
        print("\nREDÉMARRAGE REQUIS : quittez Claude Code et relancez-le pour charger les serveurs à jour.")
    else:
        print("\nDéjà à jour : aucun redémarrage nécessaire.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
