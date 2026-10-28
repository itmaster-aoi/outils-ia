"""Tests de la migration des dossiers (docs/organisation-dossiers.md), sur un poste simulé.

    plugins\\aoi\\controle\\runtime\\python.exe tests\\test_migration_dossiers.py

Chaque test tourne dans un dossier temporaire : LOCALAPPDATA et USERPROFILE y sont redirigés.
Les vrais dossiers du poste et la vraie base cortexdb ne sont jamais touchés.
Le contrôle « Claude Code fermé » est neutralisé dans les tests de migration (cette session
tourne) ; un test séparé vérifie qu'il refuse bien quand claude.exe tourne.
À lancer avec le Python embarqué du plugin : c'est celui des postes. Bibliothèque standard seulement.
"""
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
PLUGIN = RACINE / "plugins" / "aoi"
SCRIPTS = PLUGIN / "skills" / "regen" / "scripts"
PY = sys.executable
resultats = []


def verifier(nom, condition, detail=""):
    resultats.append((nom, bool(condition)))
    print(f"{'OK   ' if condition else 'ÉCHEC'} {nom}" + (f" : {detail}" if detail and not condition else ""))


def poste():
    """Poste simulé : ancienne organisation, deux serveurs, une base cortexdb en WAL."""
    t = Path(tempfile.mkdtemp(prefix="aoi-test-"))
    local, home = t / "local", t / "home"
    aoi = local / "aoi"
    for nom, version in (("cortexdb-server", "2.139.1"), ("revit-server", "2026-10-12")):
        d = aoi / f"{nom}-{version}"
        d.mkdir(parents=True)
        (d / "aoi-version.txt").write_text(version, encoding="utf-8")
    (aoi / "revit-server-2026-10-12" / "build").mkdir()
    (aoi / "revit-server-2026-10-12" / "build" / "index.js").write_text("// faux serveur", encoding="utf-8")
    # Pas de faux cortexdb-mcp.exe : un python.exe renommé fait arrêter la session par Bitdefender
    # (ATC, 28.10.2026). Le lanceur est appelé par lancer_serveur(), qui lance le vrai python.exe.
    revit = sqlite3.connect(aoi / "revit-server-2026-10-12" / "revit-data.db")
    revit.execute("create table p(i)")
    revit.execute("insert into p values (1)")
    revit.commit()
    revit.close()
    base = home / ".cortexdb" / "cortexdb.db"
    base.parent.mkdir(parents=True)
    c = sqlite3.connect(base)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("create table souvenirs(texte)")
    c.executemany("insert into souvenirs values (?)", [(f"souvenir {i}",) for i in range(250)])
    c.commit()
    c.close()
    (aoi / "session.json").write_text('{"version": "2026.10.28.1"}', encoding="utf-8")
    (aoi / "demarrage.log").write_text("ligne\n", encoding="utf-8")
    # APPDATA et PUBLIC aussi : les add-ins (Revit, KeyShot...) ne doivent jamais toucher ceux du poste
    env = dict(os.environ, LOCALAPPDATA=str(local), USERPROFILE=str(home), HOME=str(home),
               APPDATA=str(t / "roaming"), PUBLIC=str(t / "public"))
    return t, aoi, base, env


MANIFESTE = ('<?xml version="1.0" encoding="utf-8"?>\n<RevitAddIns>\n  <AddIn Type="Application">\n'
             "    <Assembly>revit_mcp_plugin/RevitMCPPlugin.dll</Assembly>\n  </AddIn>\n</RevitAddIns>\n")
REGISTRE = Path("revit_mcp_plugin") / "Commands" / "commandRegistry.json"


def revit_simule(env, version=None, commande_a=True):
    """Add-in Revit 2025 simulé : une version dans aoi\\addins et l'hôte Revit en copie complète,
    où l'utilisateur a désactivé la commande « a »."""
    fiche = json.loads((PLUGIN / "mcp" / "revit" / "addin.json").read_text(encoding="utf-8"))["add-ins"][0]
    src = Path(env["LOCALAPPDATA"]) / "aoi" / "addins" / f"revit-2025-{version or fiche['archive']['version']}"
    hote = Path(env["APPDATA"]) / "Autodesk" / "Revit" / "Addins" / "2025"
    for d, actif in ((src, commande_a), (hote, False)):
        if d == hote and version:
            continue
        (d / REGISTRE).parent.mkdir(parents=True)
        (d / "revit_mcp_plugin" / "RevitMCPPlugin.dll").write_bytes(b"dll")
        (d / "mcp-servers-for-revit.addin").write_text(MANIFESTE, encoding="utf-8")
        (d / REGISTRE).write_text(json.dumps({"Commands": [{"commandName": "a", "enabled": actif},
                                                           {"commandName": "b", "enabled": True}]}), encoding="utf-8")
    (src / "aoi-version.txt").write_text(src.name, encoding="utf-8")
    return src, hote, fiche["pointeur"]


def commande_a(dossier):
    donnees = json.loads((dossier / REGISTRE).read_text(encoding="utf-8"))
    return next(c["enabled"] for c in donnees["Commands"] if c["commandName"] == "a")


def assembly(hote):
    texte = (hote / "mcp-servers-for-revit.addin").read_text(encoding="utf-8")
    return texte.split("<Assembly>")[1].split("</Assembly>")[0]


def compter(base):
    """Lignes de la table souvenirs ; connexion fermée aussitôt (sinon la base reste « ouverte »)."""
    if not base.is_file():
        return -1
    c = sqlite3.connect(f"file:{base}?mode=ro", uri=True)
    try:
        return c.execute("select count(*) from souvenirs").fetchone()[0]
    finally:
        c.close()


def lancer(args, env, entree=None, timeout=60):
    return subprocess.run([PY, *args], env=env, input=entree, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout)


LANCEUR = """
import subprocess, sys
sys.argv = ["lancer.py", "cortexdb"]
sys.path.insert(0, r"%s")
vrai = subprocess.Popen
def faux(commande, env=None, **kw):
    # Serveur remplacé par ce Python, sous son vrai nom ; il exécute le script reçu sur stdin.
    return vrai([sys.executable], env=dict(env or {}, AOI_TEST_COMMANDE=commande[0]), **kw)
subprocess.Popen = faux
import lancer
sys.exit(lancer.main())
""" % (PLUGIN / "lanceur")
SCRIPT_SERVEUR = "import os; print(os.environ.get('CORTEXDB_PATH')); print(os.environ.get('AOI_TEST_COMMANDE'))"


def lancer_serveur(env):
    """lancer.py cortexdb ; ligne 1 : CORTEXDB_PATH, ligne 2 : serveur que le lanceur aurait lancé."""
    return lancer(["-c", LANCEUR], env, entree=SCRIPT_SERVEUR)


def migrer(env, *options, sans_processus=True):
    """migrer_dossiers.main() avec le contrôle des processus neutralisé (sans_processus)."""
    code = ("import sys; sys.path.insert(0, r'%s'); import migrer_dossiers as m; %s"
            "sys.argv = ['migrer_dossiers.py'] + %r; sys.exit(m.main())"
            % (SCRIPTS, "m.processus_du_compte = lambda: []; " if sans_processus else "", list(options)))
    return lancer(["-c", code], env)


def test_imports():
    for script in ("maj.py", "archives_aoi.py", "migrer_dossiers.py"):
        r = lancer([str(SCRIPTS / script), "--help"], os.environ)
        verifier(f"{script} se lance avec le Python embarqué", r.returncode == 0, r.stderr[-300:])
    r = lancer([str(PLUGIN / "lanceur" / "lancer.py")], os.environ)
    verifier("lancer.py sans argument : usage, code 2", r.returncode == 2 and "usage" in r.stderr, r.stderr)


def test_mcp_json():
    mcp = json.loads((PLUGIN / ".mcp.json").read_text(encoding="utf-8"))["mcpServers"]
    for nom in ("cortexdb", "revit"):
        e = mcp[nom]
        ok = (e["command"] == "${CLAUDE_PLUGIN_ROOT}/controle/runtime/python.exe"
              and e["args"] == ["${CLAUDE_PLUGIN_ROOT}/lanceur/lancer.py", nom])
        verifier(f".mcp.json : {nom} passe par le lanceur, sans version", ok, json.dumps(e))
    texte = (RACINE / "archives" / "construire.py").read_text(encoding="utf-8")
    verifier("construire.py ne réécrit plus .mcp.json", '".mcp.json"' not in texte and "MCP[" not in texte)


def test_migration():
    t, aoi, base, env = poste()
    try:
        r = migrer(env, "--simuler")
        verifier("simulation : code 0, aucun témoin", r.returncode == 0
                 and not (aoi / "journal" / "migration-dossiers.json").exists(), r.stdout + r.stderr)

        r = migrer(env, "--appliquer", sans_processus=False)
        verifier("claude.exe en cours : migration refusée (code 2)", r.returncode == 2 and "claude.exe" in r.stdout,
                 r.stdout)

        verrou = sqlite3.connect(aoi / "revit-server-2026-10-12" / "revit-data.db")
        verrou.execute("begin exclusive")
        r = migrer(env, "--appliquer")
        verrou.rollback()
        verrou.close()
        verifier("base Revit ouverte par un autre processus : migration refusée (code 2), rien d'écrit",
                 r.returncode == 2 and "bases encore ouvertes" in r.stdout and not (aoi / "journal").exists(),
                 r.stdout)

        r = migrer(env, "--appliquer")
        temoin = aoi / "journal" / "migration-dossiers.json"
        verifier("migration : code 0 et témoin écrit", r.returncode == 0 and temoin.is_file(), r.stdout + r.stderr)
        nouvelle = aoi / "donnees" / "cortexdb" / "cortexdb.db"
        verifier("base cortexdb copiée, 250 lignes", compter(nouvelle) == 250, str(compter(nouvelle)))
        verifier("ancienne base intacte", compter(base) == 250)
        verifier("serveurs copiés dans serveurs\\, anciens gardés",
                 (aoi / "serveurs" / "revit-server-2026-10-12" / "revit-data.db").is_file()
                 and (aoi / "revit-server-2026-10-12" / "revit-data.db").is_file())
        verifier("journaux copiés", (aoi / "journal" / "session.json").is_file())
        verifier("note MIGRE-VERS-AOI.txt dans l'ancien dossier", (base.parent / "MIGRE-VERS-AOI.txt").is_file())

        r = migrer(env, "--appliquer")
        verifier("relance : déjà migré, code 0", r.returncode == 0 and "Déjà migré" in r.stdout, r.stdout)

        r = lancer_serveur(env)
        lignes = r.stdout.splitlines()
        verifier("lanceur migré : CORTEXDB_PATH = nouvelle base", lignes[:1] == [str(nouvelle)], r.stdout + r.stderr)
        verifier("lanceur migré : serveur lancé depuis serveurs\\",
                 len(lignes) > 1 and "\\serveurs\\cortexdb-server-2.139.1\\" in lignes[1], r.stdout)

        r = lancer(["-c", f"import sys; sys.path.insert(0, r'{SCRIPTS}'); import maj; sys.argv=['maj.py','--verifier-dossiers']; sys.exit(maj.main())"], env)
        verifier("maj.py --verifier-dossiers : migré, code 0", r.returncode == 0 and "nouvelle" in r.stdout, r.stdout + r.stderr)

        test_orphelin(env, aoi)

        r = migrer(env, "--annuler")
        verifier("annulation : code 0, témoin retiré", r.returncode == 0 and not temoin.exists()
                 and (aoi / "journal" / "migration-dossiers.annule.json").is_file(), r.stdout + r.stderr)
        r = lancer_serveur(env)
        lignes = r.stdout.splitlines()
        verifier("après annulation : pas de CORTEXDB_PATH, serveur de l'ancien dossier",
                 lignes[:1] == ["None"] and len(lignes) > 1 and "\\serveurs\\" not in lignes[1], r.stdout + r.stderr)

        time.sleep(1.5)
        c = sqlite3.connect(base)
        c.execute("insert into souvenirs values ('écrit après annulation')")
        c.commit()
        c.close()
        r = migrer(env, "--appliquer")
        verifier("divergence après annulation : arrêt, code 3, rien de modifié",
                 r.returncode == 3 and "ARRÊT" in r.stdout and not temoin.exists(), r.stdout)
    finally:
        shutil.rmtree(t, ignore_errors=True)


def test_orphelin(env, aoi):
    """Lanceur tué : le serveur doit s'arrêter avec lui (Job Object)."""
    pid_f = aoi / "pid.txt"
    p = subprocess.Popen([PY, "-c", LANCEUR], env=env, stdin=subprocess.PIPE, text=True)
    p.stdin.write(f"import os, time\nopen(r'{pid_f}', 'w').write(str(os.getpid()))\ntime.sleep(60)\n")
    p.stdin.close()
    for _ in range(50):
        if pid_f.is_file() and pid_f.read_text():
            break
        time.sleep(0.1)
    pid = pid_f.read_text() if pid_f.is_file() else ""
    p.kill()
    p.wait()
    time.sleep(1)
    vivant = pid and pid in subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                                           capture_output=True, text=True).stdout
    verifier("lanceur tué : pas de serveur orphelin", pid and not vivant, f"pid {pid}")
    if vivant:
        subprocess.run(["taskkill", "/PID", pid, "/F"], capture_output=True)


def test_verrou_regen():
    t, aoi, base, env = poste()
    try:
        code = (f"import sys, os; sys.path.insert(0, r'{SCRIPTS}'); import maj; "
                "a = maj.prendre_verrou(); b = maj.prendre_verrou(); "
                "a.write_text('999999', encoding='utf-8'); c = maj.prendre_verrou(); "
                "print(a is not None, b is None, c is not None)")
        r = lancer(["-c", code], env)
        verifier("verrou de /regen : pris, refusé au second, repris s'il est abandonné",
                 r.stdout.strip() == "True True True", r.stdout + r.stderr)
    finally:
        shutil.rmtree(t, ignore_errors=True)


def test_demarrage():
    t, aoi, base, env = poste()
    try:
        code = (f"import sys; sys.path.insert(0, r'{SCRIPTS}'); import maj; sys.exit(maj.demarrage())")
        r = lancer(["-c", code], env)
        ok = r.returncode == 0 and "systemMessage" in r.stdout
        verifier("crochet de démarrage, ancienne organisation : message JSON", ok, r.stdout + r.stderr)
        verifier("crochet : demarrage.log à l'ancien emplacement",
                 "dossiers : à migrer" in (aoi / "demarrage.log").read_text(encoding="utf-8"))
        migrer(env, "--appliquer")
        r = lancer(["-c", code], env)
        verifier("crochet, nouvelle organisation : session.json et demarrage.log dans journal\\",
                 r.returncode == 0 and "dossiers : migré" in (aoi / "journal" / "demarrage.log").read_text(encoding="utf-8")
                 and (aoi / "journal" / "session.json").is_file(), r.stdout + r.stderr)
    finally:
        shutil.rmtree(t, ignore_errors=True)


def test_archives_versionne():
    t, aoi, base, env = poste()
    try:
        migrer(env, "--appliquer")
        code = (f"import sys, json; sys.path.insert(0, r'{SCRIPTS}'); import archives_aoi as a; "
                f"f = json.load(open(r'{PLUGIN / 'revit-server-aoi.json'}', encoding='utf-8')); "
                "a.installer_versionne(f, 'revit-server', 'Serveur MCP Revit', True)")
        r = lancer(["-c", code], env)
        verifier("archives_aoi, poste migré : serveur trouvé dans serveurs\\",
                 "\\serveurs\\revit-server-2026-10-12" in r.stdout, r.stdout + r.stderr)
    finally:
        shutil.rmtree(t, ignore_errors=True)


def test_reparation():
    """Serveur de la même version endommagé (build/index.js retiré) : /regen le réinstalle et garde
    revit-data.db. Archive locale à la place du téléchargement."""
    t, aoi, base, env = poste()
    try:
        dest = aoi / "revit-server-2026-10-12"
        (dest / "build" / "index.js").unlink()
        source = t / "archive"
        (source / "build").mkdir(parents=True)
        (source / "build" / "index.js").write_text("// serveur réinstallé", encoding="utf-8")
        zip_ = t / "revit-server.zip"
        with zipfile.ZipFile(zip_, "w") as z:
            z.write(source / "build" / "index.js", "build/index.js")
        code = (f"import sys, json, shutil; sys.path.insert(0, r'{SCRIPTS}'); import archives_aoi as a\n"
                f"f = json.load(open(r'{PLUGIN / 'revit-server-aoi.json'}', encoding='utf-8'))\n"
                f"f.update(sha256=a.sha256(r'{zip_}'), taille={zip_.stat().st_size})\n"
                f"a.telecharger = lambda url, cible, taille: shutil.copy(r'{zip_}', cible)\n"
                "sys.exit(0 if a.installer_versionne(f, 'revit-server', 'Serveur MCP Revit', False) else 1)")

        with open(dest / "revit-data.db", "rb"):  # dossier utilisé : Windows refuse de le renommer
            r = lancer(["-c", code], env)
        verifier("réparation, dossier utilisé : refusée, base gardée",
                 r.returncode == 1 and "encore utilisé" in r.stdout and lignes_revit(dest) == 1, r.stdout + r.stderr)

        r = lancer(["-c", code], env)
        verifier("réparation : serveur réinstallé", r.returncode == 0
                 and "réinstallé" in (dest / "build" / "index.js").read_text(encoding="utf-8"), r.stdout + r.stderr)
        verifier("réparation : revit-data.db gardé", lignes_revit(dest) == 1, r.stdout)
    finally:
        shutil.rmtree(t, ignore_errors=True)


def test_pointeur_revit():
    """Add-in Revit : copie complète de l'hôte remplacée par un pointeur à la migration, registre
    repris, mise à jour vers une nouvelle version, retour arrière."""
    t, aoi, base, env = poste()
    try:
        src, hote, pointeur = revit_simule(env)
        r = migrer(env, "--simuler")
        verifier("pointeur Revit : annoncé en simulation, rien modifié",
                 "pointeur vers" in r.stdout and (hote / "revit_mcp_plugin").is_dir(), r.stdout + r.stderr)

        r = migrer(env, "--appliquer")
        dll = (src / "revit_mcp_plugin" / "RevitMCPPlugin.dll").resolve()
        verifier("pointeur Revit : migration, code 0", r.returncode == 0, r.stdout + r.stderr)
        verifier("pointeur Revit : l'hôte ne garde que le manifeste, chemin absolu vers aoi\\addins",
                 not (hote / "revit_mcp_plugin").exists() and assembly(hote) == str(dll), assembly(hote))
        garde = aoi / "journal" / "avant-migration" / "revit-2025"
        verifier("pointeur Revit : copie complète gardée dans journal\\avant-migration",
                 (garde / REGISTRE).is_file() and (garde / "destination.txt").is_file())
        verifier("pointeur Revit : commande désactivée par l'utilisateur reprise", commande_a(src) is False)

        code = (f"import sys; sys.path.insert(0, r'{SCRIPTS}'); import maj; "
                f"p = {{'chemin': __import__('pathlib').Path(r'{PLUGIN}'), 'version': None}}; "
                "print([maj.copier_addin(*x, appliquer=True) for x in maj.addins(p, appliquer=True)])")
        r = lancer(["-c", code], env)
        verifier("pointeur Revit : /regen suivant, add-in à jour", "[True]" in r.stdout and "à jour (pointeur" in r.stdout,
                 r.stdout + r.stderr)
        r = lancer(["-c", f"import sys; sys.path.insert(0, r'{SCRIPTS}'); import maj; sys.argv=['maj.py','--verifier-dossiers']; sys.exit(maj.main())"], env)
        verifier("pointeur Revit : --verifier-dossiers le montre", "add-in Revit 2025 : pointeur vers" in r.stdout, r.stdout)

        neuf, _, _ = revit_simule(env, version="2099-01-01")
        code = (f"import sys, json; from pathlib import Path; sys.path.insert(0, r'{SCRIPTS}'); import maj; "
                f"ok = maj.poser_pointeur('Revit 2025', Path(r'{neuf}'), Path(r'{hote}'), '', {pointeur!r}, True); "
                f"maj.nettoyer_addin('Revit 2025', Path(r'{neuf}')); print(ok)")
        r = lancer(["-c", code], env)
        verifier("pointeur Revit : nouvelle version, pointeur déplacé et choix repris",
                 r.stdout.strip().endswith("True") and assembly(hote).startswith(str(neuf.resolve()))
                 and commande_a(neuf) is False, r.stdout + r.stderr)
        verifier("pointeur Revit : ancienne version effacée après le passage", not src.exists())

        r = migrer(env, "--annuler")
        verifier("pointeur Revit : --annuler remet la copie complète",
                 r.returncode == 0 and (hote / REGISTRE).is_file() and assembly(hote) == "revit_mcp_plugin/RevitMCPPlugin.dll"
                 and commande_a(hote) is False and not garde.exists(), r.stdout + r.stderr)
    finally:
        shutil.rmtree(t, ignore_errors=True)


def test_espace_libre():
    t, aoi, base, env = poste()
    try:
        code = (f"import sys, types; sys.path.insert(0, r'{SCRIPTS}'); import migrer_dossiers as m; "
                "m.processus_du_compte = lambda: []; m.shutil.disk_usage = lambda p: types.SimpleNamespace(free=0); "
                "sys.argv = ['migrer_dossiers.py', '--appliquer']; sys.exit(m.main())")
        r = lancer(["-c", code], env)
        verifier("espace disque insuffisant : refus, code 2, rien écrit",
                 r.returncode == 2 and "espace disque insuffisant" in r.stdout and not (aoi / "journal").exists(),
                 r.stdout + r.stderr)
    finally:
        shutil.rmtree(t, ignore_errors=True)


def lignes_revit(dossier):
    f = dossier / "revit-data.db"
    if not f.is_file():
        return -1
    c = sqlite3.connect(f"file:{f}?mode=ro", uri=True)
    try:
        return c.execute("select count(*) from p").fetchone()[0]
    finally:
        c.close()


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    test_imports()
    test_mcp_json()
    test_migration()
    test_verrou_regen()
    test_demarrage()
    test_archives_versionne()
    test_reparation()
    test_pointeur_revit()
    test_espace_libre()
    echecs = [n for n, ok in resultats if not ok]
    print(f"\n{len(resultats) - len(echecs)} réussis, {len(echecs)} en échec")
    sys.exit(1 if echecs else 0)
