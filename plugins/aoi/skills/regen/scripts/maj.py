"""Met le plugin aoi à l'étiquette imposée par la console, sans passer par installer-poste.ps1.

    maj.py              état du poste, sans rien changer
    maj.py --appliquer  inscrit le catalogue à l'étiquette imposée, met le plugin à jour,
                        recopie les add-ins Rhino et Revit s'ils ont changé

N'utilise que la bibliothèque standard. L'étiquette vient toujours des managed settings
(~/.claude/remote-settings.json) : ce script ne choisit jamais lui-même une version.
Claude Code n'écrit ce fichier qu'au démarrage d'un processus « claude » : le script en lance
un (lecture seule) pour le rafraîchir, sans qu'il faille redémarrer la session.
"""
import argparse
import filecmp
import json
import os
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

DEPOT = "itmaster-aoi/outils-ia"
PLUGIN = "aoi@aoi"
CLAUDE = Path.home() / ".claude"
AOI = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "aoi"
# Le Python « embeddable » du plugin (fichier ._pth) n'ajoute pas le dossier du script à sys.path :
# sans cette ligne, « import archives_aoi » échoue alors qu'il marche avec un Python complet.
sys.path.insert(0, str(Path(__file__).resolve().parent))

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


def skills(plugin):
    if not plugin:
        return []
    return sorted(p.parent.name for p in (plugin["chemin"] / "skills").glob("*/SKILL.md"))


def claude(*args, silencieux=False):
    exe = shutil.which("claude")
    if not exe:
        raise SystemExit("Commande « claude » introuvable : lancez installer-poste.cmd.")
    env = dict(os.environ, CLAUDE_CODE_PLUGIN_PREFER_HTTPS="1")
    # Une session par clé API ne reçoit pas les managed settings : la commande doit
    # passer par le compte claude.ai de l'atelier.
    env.pop("ANTHROPIC_API_KEY", None)
    if not silencieux:
        print(f"  > claude {' '.join(args)}")
    r = subprocess.run([exe, *args], env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    sortie = (r.stdout + r.stderr).strip()
    if sortie and not silencieux:
        print("    " + sortie.replace("\n", "\n    "))
    return r.returncode == 0


def rafraichir_regles():
    """Fait relire les managed settings à la console : un processus « claude » qui démarre
    réécrit ~/.claude/remote-settings.json. La session en cours, elle, garde ses règles."""
    f = CLAUDE / "remote-settings.json"
    avant = f.stat().st_mtime if f.is_file() else 0
    claude("plugin", "marketplace", "list", silencieux=True)
    apres = f.stat().st_mtime if f.is_file() else 0
    quand = time.strftime("%d.%m.%Y %H:%M", time.localtime(apres)) if apres else "jamais"
    # Claude Code ne réécrit le fichier que si les règles ont changé : une date inchangée
    # veut dire « rien de nouveau dans la console » (ou console injoignable).
    etat = "nouvelles règles reçues à l'instant" if apres > avant else "inchangées depuis le"
    print(f"Règles de la console             : {etat} {quand}")


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
        if f.is_file() and f.name != "aoi-version.txt":
            g = dst / f.relative_to(source)
            if not (g.is_file() and filecmp.cmp(f, g, shallow=False)):
                return False
    return True


def archive_addin(nom, fiche, appliquer):
    """Dossier extrait de l'archive d'un add-in publiée à part du plugin (version GitHub).

    L'archive n'est téléchargée que si sa version manque sur le poste, et refusée si son
    empreinte SHA-256 ne correspond pas à la fiche. Renvoie None si elle reste à télécharger."""
    slug = "".join(c if c.isalnum() else "-" for c in nom.lower()).strip("-")
    dossier = AOI / "addins" / f"{slug}-{fiche['version']}"
    if (dossier / "aoi-version.txt").is_file():
        return dossier
    if not appliquer:
        return None
    from archives_aoi import sha256, telecharger  # même dossier que ce script
    dossier.parent.mkdir(parents=True, exist_ok=True)
    zip_, neuf = dossier.with_suffix(".zip"), dossier.with_suffix(".tmp")
    print(f"  {nom} : téléchargement de l'add-in {fiche['version']} ({fiche.get('taille', 0) >> 20} Mo)")
    try:
        telecharger(fiche["url"], zip_, fiche.get("taille"))
        if sha256(zip_) != fiche["sha256"].lower():
            print(f"  ÉCHEC : l'empreinte SHA-256 de l'add-in {nom} ne correspond pas à la fiche. Archive refusée, contactez l'IT.")
            return None
        shutil.rmtree(neuf, ignore_errors=True)
        with zipfile.ZipFile(zip_) as z:
            z.extractall(neuf)
        (neuf / "aoi-version.txt").write_text(fiche["version"], encoding="utf-8")
        neuf.rename(dossier)
    except OSError as e:
        print(f"  ÉCHEC : add-in {nom} : {e}")
        return None
    finally:
        zip_.unlink(missing_ok=True)
        shutil.rmtree(neuf, ignore_errors=True)
    for ancien in dossier.parent.glob(f"{slug}-*"):  # versions précédentes de cet add-in
        if ancien != dossier and ancien.is_dir():
            shutil.rmtree(ancien, ignore_errors=True)
    return dossier


def addins(plugin, appliquer=False):
    """Add-ins décrits par mcp/<serveur>/addin.json : un serveur sans ce fichier n'a pas d'add-in.

    (nom, dossier source, dossier de destination, processus à fermer, fichiers à sauvegarder, version)
    La source est soit un dossier du plugin (« source »), soit une archive publiée à part
    (« archive ») ; None si l'archive reste à télécharger.
    Seules les applications déjà lancées sur ce compte (dossier « si_existe ») sont traitées.
    """
    liste = []
    for manifeste in sorted((plugin["chemin"] / "mcp").glob("*/addin.json")):
        for e in (lire_json(manifeste) or {}).get("add-ins", []):
            temoin = Path(os.path.expandvars(e.get("si_existe", e["destination"])))
            if not temoin.is_dir():
                continue
            if e.get("archive"):
                source, version = archive_addin(e["nom"], e["archive"], appliquer), e["archive"]["version"]
            elif e.get("source"):
                source, version = manifeste.parent / e["source"], None
                if not source.is_dir():
                    continue
            else:  # forme inconnue (fiche plus récente que ce script) : ignorée, sans planter
                print(f"  {e.get('nom', '?')} : fiche d'add-in non reconnue, ignorée (mettez /regen à jour)")
                continue
            liste.append((e["nom"], source, Path(os.path.expandvars(e["destination"])),
                          e.get("processus", ""), e.get("sauvegarder", []), version))
    return liste


def copier_addin(nom, source, dst, proc, sauvegarder, version, appliquer):
    if source is None:
        print(f"  {nom} : add-in {version} à télécharger" + ("" if appliquer else " (/regen)"))
        return False
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
    shutil.copytree(source, dst, dirs_exist_ok=True, ignore=shutil.ignore_patterns("aoi-version.txt"))
    print(f"  {nom} : add-in recopié vers {dst}")
    return True


def anciennes_versions(garder):
    cache = CLAUDE / "plugins" / "cache" / "aoi" / "aoi"
    for reste in cache.glob("*.a-effacer"):  # effacement interrompu la fois précédente
        shutil.rmtree(reste, ignore_errors=True)
    return [d for d in cache.glob("*") if d.is_dir() and d.resolve() not in garder]


def nettoyer_cache(*garder):
    """Claude Code garde une copie complète de chaque version du plugin (~300 Mo chacune) et
    ne les efface jamais. On garde la version installée et celle dont tourne la session
    en cours (ses serveurs et ce script en dépendent) : elle partira au /regen suivant."""
    garder = {Path(g["chemin"]).resolve() for g in garder if g}
    garder.add(Path(sys.executable).resolve().parents[3])  # .../<version>/skills/report/runtime/python.exe
    libere, echecs = 0, []
    for d in anciennes_versions(garder):
        taille = sum(f.stat().st_size for f in d.rglob("*") if f.is_file())
        # Renommer d'abord : Windows refuse si un fichier du dossier est ouvert (serveur MCP
        # d'une session en cours). On n'efface donc jamais à moitié une version utilisée.
        corbeille = d.with_name(d.name + ".a-effacer")
        try:
            d.rename(corbeille)
        except OSError:
            echecs.append(d.name)
            continue
        shutil.rmtree(corbeille, ignore_errors=True)
        libere += taille
    if libere:
        print(f"Anciennes versions effacées du cache : {libere / 2**20:,.0f} Mo libérés".replace(",", " "))
    if echecs:
        print(f"Anciennes versions encore utilisées, à effacer au prochain /regen : {', '.join(echecs)}")


def controle(plugin, verifier):
    """Contrôle des imports Python : copie dans C:\\ProgramData\\aoi (skill report du plugin)."""
    script = plugin["chemin"] / "skills" / "report" / "scripts" / "activer_controle.py"
    if script.is_file():
        r = subprocess.run([sys.executable, str(script)] + (["--verifier"] if verifier else []),
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        print("  " + (r.stdout + r.stderr).strip().replace("\n", "\n  "))
    # Python AOI, Node AOI : archives téléchargées à part, seulement si leur version change
    script = plugin["chemin"] / "skills" / "regen" / "scripts" / "archives_aoi.py"
    if script.is_file():
        sys.stdout.flush()
        subprocess.run([sys.executable, str(script)] + (["--verifier"] if verifier else []))


def etat_session(plugin):
    archives = {}
    if plugin:  # parties publiées à part : <nom>-aoi.json à la racine du plugin
        for f in sorted(plugin["chemin"].glob("*-aoi.json")):
            archives[f.name[:-len("-aoi.json")]] = (lire_json(f) or {}).get("version")
    return {"version": plugin["version"] if plugin else None,
            "serveurs": serveurs(plugin), "skills": skills(plugin), "archives": archives,
            "add-ins": {x[0]: x[5] or "dans le plugin" for x in addins(plugin)} if plugin else {}}


def demarrage():
    """Crochet SessionStart : bilan d'une ligne à chaque session (version, serveurs, contrôle des
    imports, refus récents), puis tableau des nouveautés par rapport à la session précédente
    (%LOCALAPPDATA%\\aoi\\session.json) et mise à jour imposée par la console, s'il y en a.
    Ne modifie rien d'autre que ce fichier."""
    debut = time.time()
    sys.stdout = open(os.devnull, "w", encoding="utf-8")  # silence des fonctions d'état
    try:
        # Pas de rafraichir_regles() ici : Claude Code vient de relire les règles en démarrant,
        # et un « claude » imbriqué pendant son démarrage peut bloquer jusqu'au délai du crochet.
        imposee, inscrite, plugin = ref_imposee(), ref_inscrite(), plugin_installe()
        etat = etat_session(plugin)
        f = AOI / "session.json"
        avant = lire_json(f) or {}
        lignes = []
        if avant and avant.get("version") != etat["version"]:
            lignes.append(("Plugin aoi", avant.get("version") or "-", etat["version"] or "-"))
            for cle, prefixe, nom in (("serveurs", "plugin:aoi:", "Serveur"), ("skills", "/aoi:", "Skill")):
                for s in sorted(set(etat[cle]) - set(avant.get(cle, []))):
                    lignes.append((f"{nom} {prefixe}{s}", "-", "nouveau"))
                for s in sorted(set(avant.get(cle, [])) - set(etat[cle])):
                    lignes.append((f"{nom} {prefixe}{s}", "présent", "retiré"))
            for nom, v in etat["add-ins"].items():
                if avant.get("add-ins", {}).get(nom) != v:
                    lignes.append((f"Add-in {nom}", avant.get("add-ins", {}).get(nom) or "-", v))
            for nom, v in etat["archives"].items() if "archives" in avant else ():  # ancien format : pas de comparaison
                if avant.get("archives", {}).get(nom) != v:
                    lignes.append((f"Archive {nom}", avant.get("archives", {}).get(nom) or "-", v or "-"))
        AOI.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(etat, ensure_ascii=False, indent=2), encoding="utf-8")
    finally:
        sys.stdout = sys.__stdout__
    # Bilan affiché à l'utilisateur à chaque session (systemMessage). Il n'est pas transmis à
    # Claude (pas d'additionalContext) : le suivi des outils reste séparé de la conversation.
    # La version du plugin est déjà en tête de ligne : seul son changement ne fait pas un nouvel outil.
    nouveautes = [f"{l[0]} ({l[2]})" if l[2] != "nouveau" else l[0]
                  for l in lignes if l[0] != "Plugin aoi"]
    if imposee and inscrite != imposee:
        suivi = f"mise à jour disponible ({imposee}) : tapez /aoi:regen"
    elif nouveautes:
        suivi = "nouveaux outils : " + ", ".join(nouveautes)
    else:
        suivi = "vos librairies sont à jour"
    texte = [f"Outils IA atelier oï, v{etat['version'] or '?'} : {', '.join(etat['serveurs']) or 'aucun serveur'}"
             f" · {python_aoi()} · {suivi}"]
    if not controle_actif():
        texte.append("ATTENTION : contrôle des imports Python inactif. Lancez /aoi:regen ou contactez l'IT.")
    print(json.dumps({"systemMessage": "\n".join(texte)}, ensure_ascii=False))
    try:  # trace du crochet, pour vérifier qu'il tourne et combien de temps il prend
        with open(AOI / "demarrage.log", "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S')}  {etat['version']}  {time.time() - debut:.1f} s"
                    f"  nouveautés : {len(lignes)}\n")
    except OSError:
        pass
    return 0


def controle_actif():
    """Contrôle des imports : la copie fixe existe et PYTHONPATH (managed settings) la désigne."""
    guard = Path(r"C:\ProgramData\aoi\guard")
    return (guard / "sitecustomize.py").is_file() and str(guard).lower() in os.environ.get("PYTHONPATH", "").lower()


def python_aoi():
    """Version et chemin du Python AOI, celui qu'utilisent les scripts de Claude."""
    dossier = AOI / "python"
    exe = dossier / "python.exe"
    if not exe.is_file():
        return f"Python AOI absent ({dossier}) : lancez /aoi:regen"
    try:
        r = subprocess.run([str(exe), "-c", "import sys; print('%d.%d.%d' % sys.version_info[:3])"],
                           capture_output=True, text=True, timeout=10)
        version = r.stdout.strip() or "?"
    except (OSError, subprocess.SubprocessError):
        version = "?"
    return f"Python {version}, {dossier}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--appliquer", action="store_true")
    ap.add_argument("--addins", action="store_true", help="seulement les add-ins (installeur)")
    ap.add_argument("--demarrage", action="store_true", help="crochet SessionStart : rapport des nouveautés")
    a = ap.parse_args()
    if a.demarrage:
        return demarrage()
    if a.addins:
        plugin = plugin_installe()
        if not plugin:
            print("Plugin aoi introuvable : add-ins non installés.")
            return 1
        ok = [copier_addin(*x, appliquer=True) for x in addins(plugin, appliquer=True)]
        return 0 if all(ok) else 1

    rafraichir_regles()
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
            vieilles = anciennes_versions({avant["chemin"].resolve(), Path(sys.executable).resolve().parents[3]})
            if vieilles:
                print(f"  ANCIENNES VERSIONS dans le cache : {', '.join(d.name for d in vieilles)} "
                      "(--appliquer les efface)")
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
    nouvelles = sorted(set(skills(apres)) - set(skills(avant)))
    print(f"Nouvelles skills  : {', '.join('/aoi:' + s for s in nouvelles) or 'aucune'}")
    for x in addins(apres, appliquer=True):
        copier_addin(*x, appliquer=True)
    controle(apres, verifier=False)
    nettoyer_cache(avant, apres)
    if avant is None or apres["version"] != avant["version"]:
        print("\nREDÉMARRAGE REQUIS : quittez Claude Code et relancez-le pour charger les serveurs à jour.")
    else:
        print("\nDéjà à jour : aucun redémarrage nécessaire.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
