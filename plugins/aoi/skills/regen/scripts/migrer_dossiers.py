"""Passe les outils de l'atelier à la nouvelle organisation des dossiers, pour le compte Windows
qui le lance (docs/organisation-dossiers.md). Lancé par migrer-dossiers.cmd, à la racine du plugin.

    migrer-dossiers.cmd              simulation, puis demande de confirmation
    migrer-dossiers.cmd --simuler    simulation seulement
    migrer-dossiers.cmd --appliquer  migration sans question (IT)
    migrer-dossiers.cmd --annuler    retour à l'ancienne organisation

Claude Code et les logiciels de l'atelier doivent être fermés : une base copiée pendant qu'un
serveur l'utilise perd les écritures suivantes. Le script le vérifie et refuse sinon.
Il copie, il ne déplace jamais : les anciens dossiers restent intacts pour un retour arrière.
Il écrit le témoin journal\\migration-dossiers.json en dernier : tant qu'il manque, le plugin
garde l'ancienne organisation. Relancé, il reprend où il s'était arrêté.
N'utilise que la bibliothèque standard.
"""
import argparse
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import chemins_aoi as C  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# Processus qui utilisent les dossiers migrés, pour ce compte. Les logiciels hôtes (Revit, AutoCAD,
# KeyShot, Rhino) n'y sont pas : cette version ne touche pas à leurs dossiers. Le serveur Revit
# (node.exe) n'y est pas non plus : d'autres programmes s'appellent node.exe. Le test
# d'ouverture exclusive (bases_ouvertes) attrape toute base ouverte, même par un serveur orphelin.
PROCESSUS = ["claude.exe", "cortexdb-mcp.exe"]
JOURNAUX = ["session.json", "demarrage.log"]
NOTE = "MIGRE-VERS-AOI.txt"


def compte():
    return f"{os.environ.get('USERDOMAIN', '')}\\{os.environ.get('USERNAME', '')}".strip("\\")


def processus_du_compte():
    """Noms des processus de PROCESSUS qui tournent pour ce compte (tasklist filtré par utilisateur :
    une session d'un autre compte du poste n'utilise pas nos dossiers)."""
    r = subprocess.run(["tasklist", "/FI", f"USERNAME eq {compte()}", "/FO", "CSV", "/NH"],
                       capture_output=True, text=True, errors="replace")
    lances = {l.split(",")[0].strip('"').lower() for l in r.stdout.splitlines() if l.startswith('"')}
    return [p for p in PROCESSUS if p.lower() in lances]


def fichier_ouvert(f):
    """Vrai si un autre processus a ouvert le fichier : l'ouverture sans partage (CreateFileW,
    dwShareMode = 0) échoue alors. Ne modifie rien."""
    import ctypes
    from ctypes import wintypes
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    k.CreateFileW.restype = wintypes.HANDLE
    k.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
                              wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    h = k.CreateFileW(str(f), 0x80000000, 0, None, 3, 0x80, None)  # GENERIC_READ, OPEN_EXISTING
    if h == wintypes.HANDLE(-1).value:
        return True
    k.CloseHandle(h)
    return False


def bases_ouvertes():
    """Fichiers de base à copier qu'un processus utilise encore (serveur en cours, même orphelin)."""
    bases = [C.BASE_CORTEXDB_ANCIENNE] + [C.AOI / f"{n}-{v}" / "revit-data.db" for n, v in fiches_serveurs()]
    fichiers = [b.with_name(b.name + s) for b in bases for s in ("", "-wal", "-shm")]
    return [f for f in fichiers if f.is_file() and fichier_ouvert(f)]


def fiches_serveurs():
    for f in sorted(PLUGIN.glob("*-aoi.json")):
        fiche = json.loads(f.read_text(encoding="utf-8"))
        if fiche.get("versionne"):
            yield f.name[:-len("-aoi.json")], fiche["version"]


def compter(chemin):
    """Nombre de lignes de chaque table d'une base SQLite."""
    c = sqlite3.connect(f"file:{chemin}?mode=ro", uri=True)
    try:
        tables = [t for (t,) in c.execute("select name from sqlite_master where type='table'")]
        return {t: c.execute(f'select count(*) from "{t}"').fetchone()[0] for t in tables}
    finally:
        c.close()


def copier_base(src, dst):
    """Copie cohérente d'une base SQLite (API backup, source en lecture seule), contrôlée
    (integrity_check, nombre de lignes de chaque table), puis mise en place atomique."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(dst.name + ".tmp")
    tmp.unlink(missing_ok=True)
    s = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
    d = sqlite3.connect(tmp)
    try:
        s.backup(d)
    finally:
        d.close()
        s.close()
    c = sqlite3.connect(tmp)
    try:
        integre = c.execute("pragma integrity_check").fetchone()[0]
    finally:
        c.close()
    if integre != "ok":
        tmp.unlink(missing_ok=True)
        raise RuntimeError(f"copie de {src.name} non intègre : {integre}")
    avant, apres = compter(src), compter(tmp)
    if avant != apres:
        tmp.unlink(missing_ok=True)
        raise RuntimeError(f"copie de {src.name} incomplète : {avant} contre {apres}")
    os.replace(tmp, dst)
    return sum(apres.values())


def empreinte(f):
    st = f.stat()
    return {"taille": st.st_size, "modifie": st.st_mtime}


def plan():
    """Actions de la migration : (description, fonction ou None si déjà faite)."""
    actions = []
    for nom, version in fiches_serveurs():
        src, dst = C.AOI / f"{nom}-{version}", C.SERVEURS_NOUVEAU / f"{nom}-{version}"
        if (dst / "aoi-version.txt").is_file():
            actions.append((f"serveur {nom} {version} : déjà dans {C.SERVEURS_NOUVEAU}", None))
        elif (src / "aoi-version.txt").is_file():
            actions.append((f"serveur {nom} {version} : copie de {src} vers {dst}",
                            lambda s=src, d=dst: copier_dossier(s, d)))
        else:
            actions.append((f"serveur {nom} {version} : pas installé, /aoi:regen l'installera", None))
    src, dst = C.BASE_CORTEXDB_ANCIENNE, C.BASE_CORTEXDB_NOUVELLE
    if dst.is_file():
        actions.append((f"base cortexdb : déjà dans {dst}", None))
    elif src.is_file():
        actions.append((f"base cortexdb : copie contrôlée de {src} vers {dst}",
                        lambda: f"{copier_base(src, dst)} lignes copiées"))
    else:
        actions.append(("base cortexdb : aucune base à copier, cortexdb en créera une", None))
    for nom in JOURNAUX:
        s, d = C.AOI / nom, C.JOURNAL_NOUVEAU / nom
        if s.is_file() and not d.is_file():
            actions.append((f"journal : copie de {nom} vers {C.JOURNAL_NOUVEAU}",
                            lambda s=s, d=d: copier_fichier(s, d)))
    return actions


def copier_dossier(src, dst):
    tmp = dst.with_name(dst.name + ".tmp")
    shutil.rmtree(tmp, ignore_errors=True)
    shutil.copytree(src, tmp)
    tmp.rename(dst)


def copier_fichier(src, dst):
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def divergence():
    """Après un --annuler : l'ancienne base modifiée depuis la migration annulée ne doit pas
    être écrasée ni ignorée en silence. Renvoie un message, ou None."""
    ancien = json.loads(C.TEMOIN_ANNULE.read_text(encoding="utf-8")) if C.TEMOIN_ANNULE.is_file() else None
    src = C.BASE_CORTEXDB_ANCIENNE
    if not (ancien and src.is_file() and C.BASE_CORTEXDB_NOUVELLE.is_file()):
        return None
    note = (ancien.get("copies") or {}).get("base cortexdb")
    if note and src.stat().st_mtime > note["modifie"] + 1:
        return (f"l'ancienne base {src} a été modifiée après la migration du {ancien.get('date')}, et la "
                f"nouvelle base {C.BASE_CORTEXDB_NOUVELLE} existe aussi. Les deux contiennent des données "
                "différentes. Rien n'est modifié : contactez l'IT, qui choisit la base à garder.")
    return None


def ecrire_temoin():
    copies = {}
    if C.BASE_CORTEXDB_ANCIENNE.is_file():
        copies["base cortexdb"] = {"source": str(C.BASE_CORTEXDB_ANCIENNE), **empreinte(C.BASE_CORTEXDB_ANCIENNE)}
    version = (json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))).get("version")
    temoin = {"date": time.strftime("%Y-%m-%d %H:%M"), "compte": compte(), "plugin": version, "copies": copies}
    C.JOURNAL_NOUVEAU.mkdir(parents=True, exist_ok=True)
    tmp = C.TEMOIN.with_name(C.TEMOIN.name + ".tmp")
    tmp.write_text(json.dumps(temoin, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, C.TEMOIN)
    C.TEMOIN_ANNULE.unlink(missing_ok=True)
    if C.BASE_CORTEXDB_ANCIENNE.parent.is_dir():
        (C.BASE_CORTEXDB_ANCIENNE.parent / NOTE).write_text(
            f"Base copiée le {temoin['date']} vers {C.BASE_CORTEXDB_NOUVELLE}.\n"
            "Le plugin aoi utilise désormais la copie. Ce dossier est gardé pour un retour arrière.\n",
            encoding="utf-8")


def annuler():
    if not C.migre():
        print("Ce compte utilise déjà l'ancienne organisation : rien à annuler.")
        return 0
    t = json.loads(C.TEMOIN.read_text(encoding="utf-8"))
    os.replace(C.TEMOIN, C.TEMOIN_ANNULE)
    (C.BASE_CORTEXDB_ANCIENNE.parent / NOTE).unlink(missing_ok=True)
    print(f"Migration du {t.get('date')} annulée : le plugin reprend l'ancienne organisation au prochain démarrage.")
    nouveau = C.BASE_CORTEXDB_NOUVELLE
    note = (t.get("copies") or {}).get("base cortexdb")
    if nouveau.is_file() and note and nouveau.stat().st_mtime > time.mktime(time.strptime(t["date"], "%Y-%m-%d %H:%M")) + 60:
        print(f"ATTENTION : {nouveau} a reçu des données après la migration. Elles ne sont pas dans l'ancienne "
              f"base {C.BASE_CORTEXDB_ANCIENNE}. Le fichier est gardé ; signalez-le à l'IT.")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--simuler", action="store_true")
    g.add_argument("--appliquer", action="store_true")
    g.add_argument("--annuler", action="store_true")
    a = ap.parse_args()
    print(f"Compte : {compte()}   Dossier : {C.AOI}")

    if not (PLUGIN / "lanceur" / "lancer.py").is_file():
        print("ÉCHEC : ce plugin ne connaît pas la nouvelle organisation. Tapez /aoi:regen, puis relancez ce script.")
        return 1
    if C.migre() and not a.annuler:
        print(f"Déjà migré ({json.loads(C.TEMOIN.read_text(encoding='utf-8')).get('date')}). Rien à faire.")
        return 0
    actifs = processus_du_compte()
    if actifs and not a.simuler:
        print(f"ÉCHEC : fermez d'abord : {', '.join(actifs)}. Rien n'a été modifié.")
        print("Claude Code doit être fermé : ses serveurs utilisent les dossiers à migrer.")
        return 2
    occupes = [] if a.simuler else bases_ouvertes()
    if occupes:
        print(f"ÉCHEC : bases encore ouvertes : {', '.join(map(str, occupes))}. Rien n'a été modifié.")
        print("Un serveur tourne peut-être encore sans Claude Code. Redémarrez Windows, puis relancez ce script.")
        return 2
    if a.annuler:
        return annuler()
    message = divergence()
    if message:
        print(f"ARRÊT : {message}")
        return 3

    actions = plan()
    print("\nActions :")
    for texte, _ in actions:
        print(f"  - {texte}")
    if a.simuler:
        if actifs:
            print(f"\nÀ fermer avant la migration : {', '.join(actifs)}")
        print("\nSimulation : rien n'a été modifié.")
        return 0
    if not a.appliquer:
        try:
            reponse = input("\nAppliquer la migration ? Tapez « oui » pour continuer : ")
        except EOFError:
            reponse = ""
        if reponse.strip().lower() != "oui":
            print("Rien n'a été modifié.")
            return 0

    print()
    for texte, faire in actions:
        if faire is None:
            continue
        try:
            detail = faire()
        except Exception as e:  # noqa: BLE001 : arrêt net, sans témoin : le plugin garde l'ancienne organisation
            print(f"ÉCHEC : {texte} : {type(e).__name__} : {e}")
            print("Migration arrêtée. Le plugin garde l'ancienne organisation. Relancez ce script après correction.")
            return 1
        print(f"  fait : {texte}" + (f" ({detail})" if detail else ""))
    ecrire_temoin()
    print(f"\nMigration terminée. Témoin : {C.TEMOIN}")
    print("Les anciens dossiers sont gardés pour un retour arrière (migrer-dossiers.cmd --annuler).")
    print("Relancez Claude Code.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
