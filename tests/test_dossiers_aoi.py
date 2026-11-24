"""Tests de l'organisation des dossiers (voir chemins_aoi.py), sur un poste simulé.

    plugins\\aoi\\controle\\runtime\\python.exe tests\\test_dossiers_aoi.py

Chaque test tourne dans un dossier temporaire : LOCALAPPDATA, USERPROFILE, APPDATA et PUBLIC y
sont redirigés. Les vrais dossiers du poste et la vraie base cortexdb ne sont jamais touchés.
Pas de faux cortexdb-mcp.exe : un python.exe renommé fait réagir certains antivirus
(ATC, 28.10.2026). lancer_serveur() remplace le serveur par le vrai python.exe.
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
REVIT = "revit-server-2026-10-12"
resultats = []


def verifier(nom, condition, detail=""):
    resultats.append((nom, bool(condition)))
    print(f"{'OK   ' if condition else 'ÉCHEC'} {nom}" + (f" : {detail}" if detail and not condition else ""))


def poste():
    """Poste simulé dans l'ancienne organisation : deux serveurs à la racine de aoi, base Revit
    d'une ligne, journaux à la racine, base cortexdb dans ~\\.cortexdb."""
    t = Path(tempfile.mkdtemp(prefix="aoi-test-"))
    local, home = t / "local", t / "home"
    aoi = local / "aoi"
    for nom, version in (("cortexdb-server", "2.170.0"), ("revit-server", "2026-10-12")):
        d = aoi / f"{nom}-{version}"
        d.mkdir(parents=True)
        (d / "aoi-version.txt").write_text(version, encoding="utf-8")
    (aoi / REVIT / "build").mkdir()
    (aoi / REVIT / "build" / "index.js").write_text("// ancien serveur", encoding="utf-8")
    ecrire_revit(aoi / REVIT, 1)
    (home / ".cortexdb").mkdir(parents=True)
    (aoi / "session.json").write_text('{"version": "2026.10.28.1"}', encoding="utf-8")
    (aoi / "demarrage.log").write_text("ligne\n", encoding="utf-8")
    env = dict(os.environ, LOCALAPPDATA=str(local), USERPROFILE=str(home), HOME=str(home),
               APPDATA=str(t / "roaming"), PUBLIC=str(t / "public"))
    return t, aoi, env


def ecrire_revit(dossier, n):
    c = sqlite3.connect(dossier / "revit-data.db")
    c.execute("create table if not exists p(i)")
    c.execute("delete from p")
    c.executemany("insert into p values (?)", [(i,) for i in range(n)])
    c.commit()
    c.close()


def lignes_revit(dossier):
    f = dossier / "revit-data.db"
    if not f.is_file():
        return -1
    c = sqlite3.connect(f"file:{f}?mode=ro", uri=True)
    try:
        return c.execute("select count(*) from p").fetchone()[0]
    finally:
        c.close()


def lancer(args, env, entree=None, timeout=60):
    return subprocess.run([PY, *args], env=env, input=entree, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout)


def maj(env, *args):
    return lancer(["-c", f"import sys; sys.path.insert(0, r'{SCRIPTS}'); import maj; "
                         f"sys.argv = ['maj.py'] + {list(args)!r}; sys.exit(maj.main())"], env)


def installer_revit(t, env, verifier_seulement=False):
    """archives_aoi.installer_versionne du serveur Revit, avec une archive locale (pas de téléchargement)."""
    zip_ = t / "revit-server.zip"
    if not zip_.is_file():
        with zipfile.ZipFile(zip_, "w") as z:
            z.writestr("build/index.js", "// serveur réinstallé")
    code = (f"import sys, json, shutil; sys.path.insert(0, r'{SCRIPTS}'); import archives_aoi as a\n"
            f"f = json.load(open(r'{PLUGIN / 'revit-server-aoi.json'}', encoding='utf-8'))\n"
            f"f.update(sha256=a.sha256(r'{zip_}'), taille={zip_.stat().st_size})\n"
            f"a.telecharger = lambda url, cible, taille: shutil.copy(r'{zip_}', cible)\n"
            f"sys.exit(0 if a.installer_versionne(f, 'revit-server', 'Serveur MCP Revit', {verifier_seulement}) else 1)")
    return lancer(["-c", code], env)


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


def test_imports():
    for script in ("maj.py", "archives_aoi.py"):
        r = lancer([str(SCRIPTS / script), "--help"], os.environ)
        verifier(f"{script} se lance avec le Python embarqué", r.returncode == 0, r.stderr[-300:])
    r = lancer([str(PLUGIN / "lanceur" / "lancer.py")], os.environ)
    verifier("lancer.py sans argument : usage, code 2", r.returncode == 2 and "usage" in r.stderr, r.stderr)
    verifier("plus de script de migration", not (PLUGIN / "migrer-dossiers.cmd").exists()
             and not (SCRIPTS / "migrer_dossiers.py").exists())


def test_mcp_json():
    mcp = json.loads((PLUGIN / ".mcp.json").read_text(encoding="utf-8"))["mcpServers"]
    for nom in ("cortexdb", "revit"):
        e = mcp[nom]
        ok = (e["command"] == "${CLAUDE_PLUGIN_ROOT}/controle/runtime/python.exe"
              and e["args"] == ["${CLAUDE_PLUGIN_ROOT}/lanceur/lancer.py", nom])
        verifier(f".mcp.json : {nom} passe par le lanceur, sans version", ok, json.dumps(e))


def test_lanceur():
    t, aoi, env = poste()
    try:
        r = lancer_serveur(env)
        lignes = r.stdout.splitlines()
        verifier("lanceur, ancienne organisation : serveur de la racine, pas de CORTEXDB_PATH",
                 lignes[:1] == ["None"] and len(lignes) > 1
                 and lignes[1] == str(aoi / "cortexdb-server-2.170.0" / "cortexdb-mcp.exe"), r.stdout + r.stderr)
        shutil.copytree(aoi / "cortexdb-server-2.170.0", aoi / "serveurs" / "cortexdb-server-2.170.0")
        r = lancer_serveur(env)
        lignes = r.stdout.splitlines()
        verifier("lanceur : serveurs\\ d'abord, base cortexdb inchangée (pas de CORTEXDB_PATH)",
                 lignes[:1] == ["None"] and len(lignes) > 1 and "\\serveurs\\cortexdb-server-2.170.0\\" in lignes[1],
                 r.stdout + r.stderr)
        test_orphelin(env, aoi)
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


def test_regen_serveurs():
    """/regen sur un poste de l'ancienne organisation : installation dans serveurs\\, base Revit
    reprise, ancien dossier effacé quand il est libre."""
    t, aoi, env = poste()
    neuf = aoi / "serveurs" / REVIT
    try:
        r = installer_revit(t, env, verifier_seulement=True)
        verifier("état : serveur à réinstaller dans serveurs\\", r.returncode == 1 and "à réinstaller dans" in r.stdout,
                 r.stdout + r.stderr)
        r = maj(env, "--verifier-dossiers")
        verifier("--verifier-dossiers, ancienne organisation : code 3", r.returncode == 3, r.stdout + r.stderr)

        with open(aoi / REVIT / "revit-data.db", "rb"):  # serveur de la session en cours
            r = installer_revit(t, env)
        verifier("installation dans serveurs\\, base reprise", r.returncode == 0 and lignes_revit(neuf) == 1
                 and "réinstallé" in (neuf / "build" / "index.js").read_text(encoding="utf-8"), r.stdout + r.stderr)
        verifier("ancien dossier encore utilisé : gardé", (aoi / REVIT).is_dir() and "encore utilisée" in r.stdout,
                 r.stdout)

        r = installer_revit(t, env)
        verifier("/regen suivant : ancien dossier libre effacé", r.returncode == 0 and not (aoi / REVIT).exists()
                 and lignes_revit(neuf) == 1, r.stdout + r.stderr)
    finally:
        shutil.rmtree(t, ignore_errors=True)


def test_base_modifiee_apres_copie():
    """La session en cours écrit dans l'ancienne base après la copie : l'ancien dossier est gardé."""
    t, aoi, env = poste()
    neuf = aoi / "serveurs" / REVIT
    try:
        with open(aoi / REVIT / "revit-data.db", "rb"):
            installer_revit(t, env)
        time.sleep(1.5)
        ecrire_revit(aoi / REVIT, 5)
        r = installer_revit(t, env)
        verifier("base modifiée après la copie : ancien dossier gardé, alerte, rien écrasé",
                 (aoi / REVIT / "revit-data.db").is_file() and "ATTENTION" in r.stdout
                 and lignes_revit(aoi / REVIT) == 5 and lignes_revit(neuf) == 1, r.stdout + r.stderr)
    finally:
        shutil.rmtree(t, ignore_errors=True)


def test_reparation():
    """Serveur de la même version endommagé dans serveurs\\ (build/index.js retiré) : /regen le
    réinstalle et garde revit-data.db."""
    t, aoi, env = poste()
    dest = aoi / "serveurs" / REVIT
    try:
        dest.parent.mkdir()
        (aoi / REVIT).rename(dest)
        (dest / "build" / "index.js").unlink()
        with open(dest / "revit-data.db", "rb"):  # dossier utilisé : Windows refuse de le renommer
            r = installer_revit(t, env)
        verifier("réparation, dossier utilisé : refusée, base gardée",
                 r.returncode == 1 and "encore utilisé" in r.stdout and lignes_revit(dest) == 1, r.stdout + r.stderr)
        r = installer_revit(t, env)
        verifier("réparation : serveur réinstallé, revit-data.db gardé", r.returncode == 0 and lignes_revit(dest) == 1
                 and "réinstallé" in (dest / "build" / "index.js").read_text(encoding="utf-8"), r.stdout + r.stderr)
    finally:
        shutil.rmtree(t, ignore_errors=True)


def test_journal():
    t, aoi, env = poste()
    try:
        r = lancer(["-c", f"import sys; sys.path.insert(0, r'{SCRIPTS}'); import maj; sys.exit(maj.demarrage())"], env)
        verifier("crochet de démarrage : message JSON", r.returncode == 0 and "systemMessage" in r.stdout,
                 r.stdout + r.stderr)
        verifier("crochet : session.json et demarrage.log dans journal\\",
                 (aoi / "journal" / "session.json").is_file() and (aoi / "journal" / "demarrage.log").is_file())
        verifier("crochet : aucune consigne de migration", "migr" not in r.stdout, r.stdout)
        code = (f"import sys, os; sys.path.insert(0, r'{SCRIPTS}'); import maj; "
                "a = maj.prendre_verrou(); b = maj.prendre_verrou(); "
                "a.write_text('999999', encoding='utf-8'); c = maj.prendre_verrou(); "
                "print(a is not None, b is None, c is not None)")
        r = lancer(["-c", code], env)
        verifier("verrou de /regen : pris, refusé au second, repris s'il est abandonné",
                 r.stdout.strip() == "True True True", r.stdout + r.stderr)
    finally:
        shutil.rmtree(t, ignore_errors=True)


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


def test_pointeur_revit():
    """Add-in Revit : /regen remplace la copie complète de l'hôte par un pointeur, reprend le registre,
    puis suit une nouvelle version."""
    t, aoi, env = poste()
    try:
        src, hote, pointeur = revit_simule(env)
        code = (f"import sys; sys.path.insert(0, r'{SCRIPTS}'); import maj; "
                f"p = {{'chemin': __import__('pathlib').Path(r'{PLUGIN}'), 'version': None}}; "
                "print([maj.copier_addin(*x, appliquer=%s) for x in maj.addins(p, appliquer=%s)])")
        r = lancer(["-c", code % (False, False)], env)
        verifier("pointeur Revit : annoncé dans l'état, rien modifié",
                 "copie complète à remplacer par un pointeur" in r.stdout and (hote / "revit_mcp_plugin").is_dir(),
                 r.stdout + r.stderr)

        r = lancer(["-c", code % (True, True)], env)
        dll = (src / "revit_mcp_plugin" / "RevitMCPPlugin.dll").resolve()
        verifier("pointeur Revit : posé par /regen", "[True]" in r.stdout and "pointeur posé" in r.stdout,
                 r.stdout + r.stderr)
        verifier("pointeur Revit : l'hôte ne garde que le manifeste, chemin absolu vers aoi\\addins",
                 not (hote / "revit_mcp_plugin").exists() and assembly(hote) == str(dll), assembly(hote))
        verifier("pointeur Revit : commande désactivée par l'utilisateur reprise", commande_a(src) is False)

        r = lancer(["-c", code % (True, True)], env)
        verifier("pointeur Revit : /regen suivant, add-in à jour", "[True]" in r.stdout and "à jour (pointeur" in r.stdout,
                 r.stdout + r.stderr)
        r = maj(env, "--verifier-dossiers")
        verifier("pointeur Revit : --verifier-dossiers le montre", "add-in Revit 2025 : pointeur vers" in r.stdout, r.stdout)

        neuf, _, _ = revit_simule(env, version="2099-01-01")
        code2 = (f"import sys, json; from pathlib import Path; sys.path.insert(0, r'{SCRIPTS}'); import maj; "
                 f"ok = maj.poser_pointeur('Revit 2025', Path(r'{neuf}'), Path(r'{hote}'), '', {pointeur!r}, True); "
                 f"maj.nettoyer_addin('Revit 2025', Path(r'{neuf}')); print(ok)")
        r = lancer(["-c", code2], env)
        verifier("pointeur Revit : nouvelle version, pointeur déplacé et choix repris",
                 r.stdout.strip().endswith("True") and assembly(hote).startswith(str(neuf.resolve()))
                 and commande_a(neuf) is False, r.stdout + r.stderr)
        verifier("pointeur Revit : ancienne version effacée après le passage", not src.exists())
    finally:
        shutil.rmtree(t, ignore_errors=True)


FAUX_UPIA = r'''
import json, os, sys
from pathlib import Path
# Faux installateur d'Adobe. FAUX_UPIA : ok (défaut), echec (code 3), menteur (code 0, rien d'écrit).
mode = os.environ.get("FAUX_UPIA", "ok")
registre = Path(os.environ["APPDATA"]) / "Adobe" / "UXP" / "PluginsInfo" / "v1" / os.environ.get("FAUX_REGISTRE", "ID.json")
plugins = json.loads(registre.read_text(encoding="utf-8"))["plugins"] if registre.is_file() else []
if mode == "echec":
    print("Failed to install, status = -410!")
    sys.exit(3)
if mode != "menteur":
    if sys.argv[1] == "/remove":
        plugins = [p for p in plugins if p["name"] != sys.argv[2]]
    elif sys.argv[1] == "/install":
        plugins.append({"name": os.environ.get("FAUX_NOM", "Claude MCP"), "pluginId": os.environ["FAUX_ID"], "status": "enabled",
                        "type": "uxp", "versionString": os.environ["FAUX_VERSION"]})
    registre.parent.mkdir(parents=True, exist_ok=True)
    registre.write_text(json.dumps({"plugins": plugins}), encoding="utf-8")
print("Installation Successful")
'''


def test_plugin_uxp():
    """Forme « uxp » d'une fiche d'add-in (plugin UXP d'InDesign), avec un faux installateur d'Adobe.
    Règle contrôlée dans chaque cas : poser_uxp renvoie vrai, donc la mise à jour n'est jamais bloquée."""
    t, aoi, env = poste()
    try:
        fiche = json.loads((PLUGIN / "mcp" / "indesign" / "addin.json").read_text(encoding="utf-8"))["add-ins"][0]
        uxp = fiche["uxp"]
        paquet = PLUGIN / "mcp" / "indesign" / uxp["paquet"]
        verifier("plugin UXP : le paquet de la fiche existe", paquet.is_file(), str(paquet))
        (t / "faux_upia.py").write_text(FAUX_UPIA, encoding="utf-8")
        (t / "upia.cmd").write_text(f'@"{PY}" "{t / "faux_upia.py"}" %*\r\n', encoding="ascii")
        dossier = Path(env["APPDATA"]) / "Adobe" / "UXP" / "PluginsInfo" / "v1"
        registre = dossier / "ID.json"
        env = dict(env, AOI_UPIA=str(t / "upia.cmd"), FAUX_ID=uxp["id"], FAUX_VERSION=uxp["version"])

        def poser(appliquer=True, proc="", env=env, **change):
            u = dict(uxp, **change)
            code = (f"import sys; from pathlib import Path; sys.path.insert(0, r'{SCRIPTS}'); import maj; "
                    f"print('RETOUR', maj.poser_uxp('InDesign', Path(r'{PLUGIN / 'mcp' / 'indesign'}'), "
                    f"Path(r'{dossier}'), {proc!r}, {u!r}, {appliquer}))")
            return lancer(["-c", code], env)

        def poses():
            return [(p["pluginId"], p["versionString"]) for p in json.loads(registre.read_text(encoding="utf-8"))["plugins"]] \
                if registre.is_file() else []

        def non_bloquant(r):
            return "RETOUR True" in r.stdout and r.returncode == 0 and "Traceback" not in r.stderr

        r = poser(appliquer=False)
        verifier("plugin UXP : état seul, « à poser », rien d'écrit",
                 non_bloquant(r) and "à poser" in r.stdout and not registre.exists(), r.stdout + r.stderr)
        r = poser(proc="python.exe")
        verifier("plugin UXP : hôte ouvert, pose remise sans échec",
                 non_bloquant(r) and "est ouvert" in r.stdout and "ÉCHEC" not in r.stdout and not registre.exists(),
                 r.stdout + r.stderr)
        r = poser()
        verifier("plugin UXP : posé par l'installateur d'Adobe",
                 non_bloquant(r) and "posé" in r.stdout and poses() == [(uxp["id"], uxp["version"])], r.stdout + r.stderr)
        r = poser()
        verifier("plugin UXP : mise à jour suivante, « à jour »", non_bloquant(r) and "à jour" in r.stdout, r.stdout + r.stderr)

        registre.write_text(json.dumps({"plugins": [{"name": "Claude MCP", "pluginId": "ancien.identifiant",
                                                     "status": "enabled", "versionString": "0.0.9"}]}), encoding="utf-8")
        r = poser()
        verifier("plugin UXP : ancienne version sous un autre identifiant retirée, puis nouvelle posée",
                 non_bloquant(r) and poses() == [(uxp["id"], uxp["version"])], r.stdout + r.stderr)

        registre.unlink()
        for nom, e2, change in (
                ("installateur d'Adobe absent", dict(env, AOI_UPIA=str(t / "absent.exe")), {}),
                ("installateur d'Adobe en échec (code 3)", dict(env, FAUX_UPIA="echec"), {}),
                ("installateur d'Adobe qui répond 0 sans rien poser", dict(env, FAUX_UPIA="menteur"), {}),
                ("empreinte SHA-256 fausse", env, {"sha256": "0" * 64}),
                ("paquet absent", env, {"paquet": "addin/absent.ccx", "sha256": ""}),
                ("fiche incomplète", env, {"id": ""}),
                ("exception dans le script", env, {"sha256": 123})):
            r = poser(env=e2, **change)
            verifier(f"plugin UXP : {nom} : échec affiché, non bloquant, rien de posé",
                     non_bloquant(r) and "ÉCHEC NON BLOQUANT" in r.stdout and "installer.cmd" in r.stdout
                     and poses() == [], r.stdout + r.stderr)

        registre.parent.mkdir(parents=True, exist_ok=True)
        registre.write_text("{ registre illisible", encoding="utf-8")
        r = poser(appliquer=False)
        verifier("plugin UXP : registre illisible, lu comme vide", non_bloquant(r) and "à poser" in r.stdout, r.stdout + r.stderr)
        registre.unlink()

        # Par les fiches du plugin : InDesign jamais lancé sur ce compte, puis lancé (dossier témoin)
        code = (f"import sys; sys.path.insert(0, r'{SCRIPTS}'); import maj; "
                f"p = {{'chemin': __import__('pathlib').Path(r'{PLUGIN}'), 'version': None}}; "
                "x = [a for a in maj.addins(p) if a[0] == 'InDesign']; print('FICHES', len(x)); "
                "print('RETOUR', [maj.copier_addin(*a, appliquer=False) for a in x])")
        r = lancer(["-c", code], env)
        verifier("plugin UXP : InDesign jamais lancé sur ce compte, fiche ignorée", "FICHES 0" in r.stdout, r.stdout + r.stderr)
        (Path(env["APPDATA"]) / "Adobe" / "InDesign").mkdir(parents=True)
        r = lancer(["-c", code], env)
        verifier("plugin UXP : fiche lue par addins(), état « à poser »",
                 "FICHES 1" in r.stdout and "RETOUR [True]" in r.stdout and "à poser" in r.stdout, r.stdout + r.stderr)
        r = maj(env, "--verifier-dossiers")
        verifier("plugin UXP : --verifier-dossiers ne prend pas la fiche pour un pointeur",
                 "Traceback" not in r.stderr and "add-in InDesign" not in r.stdout, r.stdout + r.stderr)
    finally:
        shutil.rmtree(t, ignore_errors=True)


def test_plugin_uxp_photoshop():
    """Plugin UXP de Photoshop (fiche de forme « uxp ») : le paquet du dépôt est celui de la fiche et de
    VERSION-AOI.txt, son nom ne se confond pas avec celui d'InDesign, et la pose écrit dans PS.json."""
    import hashlib
    import zipfile
    dossier = PLUGIN / "mcp" / "photoshop"
    fiche = json.loads((dossier / "addin.json").read_text(encoding="utf-8"))["add-ins"][0]
    uxp = fiche["uxp"]
    paquet = dossier / uxp["paquet"]
    empreinte = hashlib.sha256(paquet.read_bytes()).hexdigest() if paquet.is_file() else ""
    verifier("Photoshop : le paquet a l'empreinte de la fiche", empreinte == uxp["sha256"], empreinte)
    ecarts = []
    for ligne in (dossier / "VERSION-AOI.txt").read_text(encoding="utf-8").splitlines():
        parties = ligne.split()
        if len(parties) == 2 and len(parties[0]) == 64:
            f = dossier / parties[1]
            # Les fichiers texte peuvent avoir changé de fin de ligne au clone : l'empreinte est celle du contenu en LF.
            contenu = f.read_bytes() if f.is_file() else b""
            if hashlib.sha256(contenu).hexdigest() != parties[0] and \
                    hashlib.sha256(contenu.replace(b"\r\n", b"\n")).hexdigest() != parties[0]:
                ecarts.append(parties[1])
    verifier("Photoshop : les fichiers ont les empreintes de VERSION-AOI.txt", not ecarts, str(ecarts))
    with zipfile.ZipFile(paquet) as z:
        manifeste = json.loads(z.read("manifest.json"))
        noms = z.namelist()
    verifier("Photoshop : le manifeste du paquet porte l'identifiant, le nom et la version de la fiche",
             (manifeste["id"], manifeste["name"], manifeste["version"]) == (uxp["id"], uxp["nom"], uxp["version"])
             and manifeste["host"]["app"] == "PS", str(manifeste)[:300])
    verifier("Photoshop : le paquet contient le panneau, le moteur et les icônes",
             {"index.html", "main.js", "moteur.js", "commandes.js", "icons/dark@1x.png", "icons/light@1x.png"} <= set(noms), str(noms))
    indesign = json.loads((PLUGIN / "mcp" / "indesign" / "addin.json").read_text(encoding="utf-8"))["add-ins"][0]["uxp"]
    verifier("Photoshop : nom et identifiant différents de ceux du plugin d'InDesign (retrait par le nom)",
             uxp["nom"] != indesign["nom"] and uxp["id"] != indesign["id"], uxp["nom"])
    t, aoi, env = poste()
    try:
        (t / "faux_upia.py").write_text(FAUX_UPIA, encoding="utf-8")
        (t / "upia.cmd").write_text(f'@"{PY}" "{t / "faux_upia.py"}" %*\r\n', encoding="ascii")
        registres = Path(env["APPDATA"]) / "Adobe" / "UXP" / "PluginsInfo" / "v1"
        registres.mkdir(parents=True)
        autre = {"plugins": [{"name": indesign["nom"], "pluginId": indesign["id"], "status": "enabled",
                              "type": "uxp", "versionString": indesign["version"]}]}
        (registres / "ID.json").write_text(json.dumps(autre), encoding="utf-8")
        env = dict(env, AOI_UPIA=str(t / "upia.cmd"), FAUX_ID=uxp["id"], FAUX_VERSION=uxp["version"],
                   FAUX_REGISTRE=uxp["registre"], FAUX_NOM=uxp["nom"])
        # proc vide : le test ne dépend pas d'un Photoshop ouvert sur le poste
        code = (f"import sys; sys.path.insert(0, r'{SCRIPTS}'); import maj; "
                f"p = {{'chemin': __import__('pathlib').Path(r'{PLUGIN}'), 'version': None}}; "
                "x = [a[:3] + ('',) + a[4:] for a in maj.addins(p) if a[0] == 'Photoshop']; print('FICHES', len(x)); "
                "print('RETOUR', [maj.copier_addin(*a, appliquer=%s) for a in x])")
        r = lancer(["-c", code % "False"], env)
        verifier("Photoshop : absent de ce compte, fiche ignorée", "FICHES 0" in r.stdout, r.stdout + r.stderr)
        (Path(env["APPDATA"]) / "Adobe" / "UXP" / "PluginsStorage" / "PHSP").mkdir(parents=True)
        r = lancer(["-c", code % "False"], env)
        verifier("Photoshop : fiche lue par addins(), état « à poser »",
                 "FICHES 1" in r.stdout and "RETOUR [True]" in r.stdout and "à poser" in r.stdout, r.stdout + r.stderr)
        r = lancer(["-c", code % "True"], env)
        pose = json.loads((registres / "PS.json").read_text(encoding="utf-8"))["plugins"] if (registres / "PS.json").is_file() else []
        verifier("Photoshop : plugin posé dans PS.json",
                 "RETOUR [True]" in r.stdout and "posé" in r.stdout
                 and [(x["pluginId"], x["versionString"]) for x in pose] == [(uxp["id"], uxp["version"])], r.stdout + r.stderr)
        verifier("Photoshop : le registre d'InDesign n'a pas changé",
                 json.loads((registres / "ID.json").read_text(encoding="utf-8")) == autre)
        r = lancer(["-c", code % "True"], env)
        verifier("Photoshop : mise à jour suivante, « à jour »", "RETOUR [True]" in r.stdout and "à jour" in r.stdout, r.stdout + r.stderr)
    finally:
        shutil.rmtree(t, ignore_errors=True)


def test_panneau_cep():
    """Panneau CEP signé d'Illustrator (fiche de forme « source ») : les fichiers du dépôt sont ceux de la
    signature, git ne les convertit pas, et la mise à jour les copie à l'identique."""
    import hashlib
    dossier = PLUGIN / "mcp" / "illustrator"
    signe = dossier / "addin" / "illustrator-mcp.claude-mcp"
    attendus = {}
    for ligne in (dossier / "VERSION-AOI.txt").read_text(encoding="utf-8").splitlines():
        parties = ligne.split()
        if len(parties) == 2 and len(parties[0]) == 64 and parties[1].startswith("addin/illustrator-mcp.claude-mcp/"):
            attendus[parties[1].split("/", 2)[2]] = parties[0]
    reels = {f.relative_to(signe).as_posix(): hashlib.sha256(f.read_bytes()).hexdigest()
             for f in signe.rglob("*") if f.is_file()}
    verifier("panneau CEP : signature présente", "META-INF/signatures.xml" in reels and "mimetype" in reels, str(sorted(reels)))
    verifier("panneau CEP : fichiers du dépôt identiques aux empreintes de VERSION-AOI.txt (signature intacte)",
             reels == attendus and len(reels) == 6, f"{reels}\n{attendus}")
    r = subprocess.run(["git", "check-attr", "text", "--", str(signe / "main.js")], cwd=RACINE,
                       capture_output=True, text=True, errors="replace")
    verifier("panneau CEP : dossier signé marqué -text dans .gitattributes", "text: unset" in r.stdout, r.stdout + r.stderr)

    t, aoi, env = poste()
    try:
        dst = Path(env["APPDATA"]) / "Adobe" / "CEP" / "extensions" / "illustrator-mcp.claude-mcp"
        # proc vide : le test ne dépend pas d'un Illustrator ouvert sur le poste
        code = (f"import sys; sys.path.insert(0, r'{SCRIPTS}'); import maj; "
                f"p = {{'chemin': __import__('pathlib').Path(r'{PLUGIN}'), 'version': None}}; "
                "x = [a[:3] + ('',) + a[4:] for a in maj.addins(p) if a[0] == 'Illustrator']; print('FICHES', len(x)); "
                "print('RETOUR', [maj.copier_addin(*a, appliquer=%s) for a in x])")
        r = lancer(["-c", code % False], env)
        verifier("panneau CEP : Illustrator jamais lancé sur ce compte, fiche ignorée", "FICHES 0" in r.stdout, r.stdout + r.stderr)
        (Path(env["APPDATA"]) / "Adobe" / "Adobe Illustrator 30 Settings").mkdir(parents=True)
        r = lancer(["-c", code % False], env)
        verifier("panneau CEP : état seul, « à recopier », rien d'écrit",
                 "FICHES 1" in r.stdout and "à recopier" in r.stdout and not dst.exists(), r.stdout + r.stderr)
        r = lancer(["-c", code % True], env)
        copies = {f.relative_to(dst).as_posix(): hashlib.sha256(f.read_bytes()).hexdigest()
                  for f in dst.rglob("*") if f.is_file()} if dst.is_dir() else {}
        verifier("panneau CEP : copié à l'identique dans CEP\\extensions",
                 "RETOUR [True]" in r.stdout and copies == attendus, r.stdout + r.stderr)
        r = lancer(["-c", code % True], env)
        verifier("panneau CEP : mise à jour suivante, « à jour »", "RETOUR [True]" in r.stdout and "à jour" in r.stdout,
                 r.stdout + r.stderr)
        (dst / "main.js").write_text("// modifié", encoding="utf-8")
        r = lancer(["-c", code % True], env)
        verifier("panneau CEP : fichier modifié sur le poste, recopié",
                 hashlib.sha256((dst / "main.js").read_bytes()).hexdigest() == attendus["main.js"], r.stdout + r.stderr)
    finally:
        shutil.rmtree(t, ignore_errors=True)


def test_detail_plugin():
    """Détail affiché par la mise à jour : une ligne par serveur, skill, commande et style."""
    t, aoi, env = poste()
    try:
        ancien = t / "ancien"
        shutil.copytree(PLUGIN / "skills" / "adhd", ancien / "skills" / "adhd")
        (ancien / "mcp" / "keyshot").mkdir(parents=True)
        (ancien / "mcp" / "keyshot" / "VERSION-AOI.txt").write_text("Version      : 0.9.0\n", encoding="utf-8")
        (ancien / ".mcp.json").write_text(json.dumps({"mcpServers": {"keyshot": {}, "rhino": {}, "disparu": {}}}),
                                          encoding="utf-8")
        code = (f"import sys; from pathlib import Path; sys.path.insert(0, r'{SCRIPTS}'); import maj; "
                f"apres = {{'chemin': Path(r'{PLUGIN}'), 'version': 'essai'}}; "
                "avant = %s; maj.detail_plugin(avant, apres)")
        r = lancer(["-c", code % "None"], env)
        lignes = r.stdout.splitlines()
        attendus = json.loads((PLUGIN / ".mcp.json").read_text(encoding="utf-8"))["mcpServers"]
        verifier("détail : une ligne par serveur de .mcp.json, tous « nouveau » sans version précédente",
                 r.returncode == 0 and all(any(f"plugin:aoi:{s} " in l and "nouveau" in l for l in lignes) for s in attendus),
                 r.stdout + r.stderr)
        verifier("détail : version du serveur lue dans VERSION-AOI.txt",
                 any("plugin:aoi:indesign" in l and "0.1.0" in l for l in lignes), r.stdout)
        verifier("détail : skills, commandes et style listés",
                 any("/aoi:graphify" in l for l in lignes) and any("commande  /aoi:recall" in l for l in lignes)
                 and any("style     aoi:ste" in l for l in lignes), r.stdout)
        r = lancer(["-c", code % f"{{'chemin': Path(r'{ancien}'), 'version': 'vieux'}}"], env)
        sortie = r.stdout
        verifier("détail : états par rapport à la version précédente",
                 r.returncode == 0
                 and any("plugin:aoi:keyshot" in l and "mis à jour" in l for l in sortie.splitlines())
                 and any("plugin:aoi:rhino" in l and "inchangé" in l for l in sortie.splitlines())
                 and any("plugin:aoi:indesign" in l and "nouveau" in l for l in sortie.splitlines())
                 and any("plugin:aoi:disparu" in l and "retiré" in l for l in sortie.splitlines())
                 and any("/aoi:adhd" in l and "inchangé" in l for l in sortie.splitlines()), sortie + r.stderr)
    finally:
        shutil.rmtree(t, ignore_errors=True)


def test_etat_a_jour():
    """Poste passé entièrement : --verifier-dossiers répond 0."""
    t, aoi, env = poste()
    try:
        (aoi / "serveurs").mkdir()
        for d in ("cortexdb-server-2.170.0", REVIT):
            (aoi / d).rename(aoi / "serveurs" / d)
        r = maj(env, "--verifier-dossiers")
        verifier("--verifier-dossiers, tout dans serveurs\\ : code 0", r.returncode == 0, r.stdout + r.stderr)
    finally:
        shutil.rmtree(t, ignore_errors=True)


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    test_imports()
    test_mcp_json()
    test_lanceur()
    test_regen_serveurs()
    test_base_modifiee_apres_copie()
    test_reparation()
    test_journal()
    test_pointeur_revit()
    test_plugin_uxp()
    test_plugin_uxp_photoshop()
    test_panneau_cep()
    test_detail_plugin()
    test_etat_a_jour()
    echecs = [n for n, ok in resultats if not ok]
    print(f"\n{len(resultats) - len(echecs)} réussis, {len(echecs)} en échec")
    sys.exit(1 if echecs else 0)
