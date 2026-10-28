"""Installe les archives de l'atelier publiées à part du plugin (Python AOI, Node AOI,
librairies du serveur Rhino, serveur MCP Revit...).

    archives_aoi.py              installe ou met à jour, seulement si la version a changé
    archives_aoi.py --verifier   indique seulement l'état

Chaque fiche <nom>-aoi.json à la racine du plugin donne la version, l'adresse de l'archive
(version GitHub du dépôt de l'atelier, hors du plugin) et son empreinte SHA-256. L'archive est
installée dans %LOCALAPPDATA%\\aoi\\<nom> et n'est téléchargée que si la version installée
diffère : un changement d'étiquette du plugin ne la recharge pas. Une archive dont l'empreinte
ne correspond pas est refusée.

Librairies ajoutées au Python AOI sans le reconstruire : python-libs.json à la racine du plugin
(écrit par python-aoi/verrouiller.py) donne chaque roue, son adresse sur PyPI et son empreinte
SHA-256. Les roues sont décompressées dans %LOCALAPPDATA%\\aoi\\python-libs-<version>, que le
fichier aoi-libs.pth du Python AOI ajoute à son chemin de recherche, après ses propres paquets.
Le contrôle des imports s'applique à ces librairies comme aux autres.
N'utilise que la bibliothèque standard.
"""
import argparse
import hashlib
import json
import os
import shutil
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[3]
# Python embarqué (._pth) : le dossier du script n'est pas dans sys.path (voir maj.py)
sys.path.insert(0, str(Path(__file__).resolve().parent))
import chemins_aoi  # noqa: E402

BASE = chemins_aoi.AOI
NOMS = {"python": "Python AOI", "node": "Node AOI",
        "revit-server": "Serveur MCP Revit", "cortexdb-server": "Serveur MCP CortexDB"}

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def telecharger(url, cible, taille):
    with urllib.request.urlopen(url, timeout=60) as r, open(cible, "wb") as f:
        recu, dernier = 0, 0
        while True:
            bloc = r.read(1 << 20)
            if not bloc:
                break
            f.write(bloc)
            recu += len(bloc)
            if taille and time.time() - dernier > 2:
                print(f"  ... {recu * 100 // taille} % ({recu >> 20} Mo)", flush=True)
                dernier = time.time()


def sha256(chemin):
    h = hashlib.sha256()
    with open(chemin, "rb") as f:
        for bloc in iter(lambda: f.read(1 << 20), b""):
            h.update(bloc)
    return h.hexdigest()


def effacer_si_libre(d):
    """Efface un dossier seulement si personne ne l'utilise : Windows refuse de renommer un
    dossier dont un fichier est ouvert (serveur d'une session en cours)."""
    corbeille = d.with_name(d.name + ".a-effacer")
    try:
        d.rename(corbeille)
    except OSError:
        return False
    shutil.rmtree(corbeille, ignore_errors=True)
    return True


def installer_versionne(fiche, dossier, nom, verifier):
    """Partie installée dans un dossier par version (<serveurs>\\<nom>-<version>, voir chemins_aoi) :
    la nouvelle version s'installe à côté de celle qu'utilise peut-être la session en cours.
    lanceur/lancer.py désigne la version de la fiche. Les fichiers « conserver » (données locales)
    sont repris de la version précédente, cherchée dans les deux organisations ; seules les
    anciennes versions de l'organisation active sont effacées, dès qu'elles ne sont plus utilisées.
    Celles de l'ancienne organisation restent pour un retour arrière de la console."""
    voulue = fiche["version"]
    racine = chemins_aoi.serveurs()
    dest = racine / f"{dossier}-{voulue}"

    def versions(base):
        return [d for d in base.glob(f"{dossier}-*")
                if d.is_dir() and d != dest and not d.name.endswith((".tmp", ".a-effacer"))]
    anciennes = sorted(versions(racine), key=lambda d: d.stat().st_mtime, reverse=True)
    autre = chemins_aoi.AOI if racine != chemins_aoi.AOI else chemins_aoi.SERVEURS_NOUVEAU
    sources = sorted(anciennes + versions(autre), key=lambda d: d.stat().st_mtime, reverse=True)
    if dest.is_dir():
        # Installation incomplète de cette version (interrompue, ou fichiers retirés par l'antivirus) :
        # ses données sont les plus récentes et le dossier sera remplacé (revit-data.db perdu le 28.10.2026).
        sources.insert(0, dest)
    if (dest / "aoi-version.txt").is_file() and (dest / fiche["exe"]).is_file():
        print(f"{nom} : à jour ({voulue}, {dest})")
        for d in anciennes:
            if not verifier and effacer_si_libre(d):
                print(f"{nom} : ancienne version {d.name} effacée")
        return True
    if verifier:
        print(f"{nom} : version validée {voulue} à installer avec /regen")
        return False

    racine.mkdir(parents=True, exist_ok=True)
    zip_, neuf = racine / f"{dossier}-{voulue}.zip", racine / f"{dossier}-{voulue}.tmp"
    print(f"{nom} : téléchargement de la version {voulue} ({fiche.get('taille', 0) >> 20} Mo)")
    try:
        telecharger(fiche["url"], zip_, fiche.get("taille"))
        if sha256(zip_) != fiche["sha256"].lower():
            print(f"ÉCHEC : l'empreinte SHA-256 de l'archive {nom} ne correspond pas à la fiche. Archive refusée, contactez l'IT.")
            return False
        shutil.rmtree(neuf, ignore_errors=True)
        with zipfile.ZipFile(zip_) as z:
            z.extractall(neuf)
        if not (neuf / fiche["exe"]).is_file():
            print(f"ÉCHEC : archive {nom} incomplète ({fiche['exe']} absent).")
            return False
        for rel in fiche.get("conserver", []):
            precedent = next((d for d in sources if (d / rel).is_file()), None)
            if precedent:
                (neuf / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(precedent / rel, neuf / rel)
                print(f"{nom} : {rel} repris de {precedent.name}")
        (neuf / "aoi-version.txt").write_text(voulue, encoding="utf-8")
        # Installation incomplète : ses fichiers « conserver » sont déjà copiés dans neuf.
        if dest.exists() and not effacer_si_libre(dest):
            print(f"ÉCHEC : {nom} : {dest} est encore utilisé. Quittez Claude Code, puis relancez /regen.")
            return False
        neuf.rename(dest)
    except OSError as e:
        print(f"ÉCHEC : {nom} : {e}")
        return False
    finally:
        zip_.unlink(missing_ok=True)
        shutil.rmtree(neuf, ignore_errors=True)
    print(f"{nom} : version {voulue} installée dans {dest}")
    for d in anciennes:
        if effacer_si_libre(d):
            print(f"{nom} : ancienne version {d.name} effacée")
        else:
            print(f"{nom} : ancienne version {d.name} encore utilisée, effacée au prochain /regen")
    return True


def installer(fiche, dossier, nom, verifier):
    if fiche.get("versionne"):
        return installer_versionne(fiche, dossier, nom, verifier)
    dest = BASE / dossier
    exe = dest / fiche.get("exe", f"{dossier}.exe")
    voulue = fiche["version"]
    try:
        actuelle = (dest / "aoi-version.txt").read_text(encoding="utf-8").strip()
    except OSError:
        actuelle = None
    if actuelle == voulue and exe.is_file():
        print(f"{nom} : à jour ({voulue}, {dest})")
        return True
    if verifier:
        print(f"{nom} : {actuelle or 'absent'}, version validée {voulue} : à installer avec /regen")
        return False

    BASE.mkdir(parents=True, exist_ok=True)
    zip_ = BASE / f"{dossier}-aoi-{voulue}.zip"
    neuf = BASE / f"{dossier}-{voulue}.tmp"
    print(f"{nom} : téléchargement de la version {voulue} ({fiche.get('taille', 0) >> 20} Mo)")
    try:
        telecharger(fiche["url"], zip_, fiche.get("taille"))
        if sha256(zip_) != fiche["sha256"].lower():
            print(f"ÉCHEC : l'empreinte SHA-256 de l'archive {nom} ne correspond pas à la fiche. Archive refusée, contactez l'IT.")
            return False
        shutil.rmtree(neuf, ignore_errors=True)
        with zipfile.ZipFile(zip_) as z:
            z.extractall(neuf)
        if not (neuf / exe.name).is_file():
            print(f"ÉCHEC : archive {nom} incomplète ({exe.name} absent).")
            return False
        (neuf / "aoi-version.txt").write_text(voulue, encoding="utf-8")
        ancien = BASE / f"{dossier}.ancien"
        shutil.rmtree(ancien, ignore_errors=True)
        if dest.exists():
            try:
                dest.rename(ancien)
            except OSError:
                print(f"ÉCHEC : {dest} est en cours d'utilisation. Fermez Claude Code et les programmes qui l'utilisent, puis relancez /regen ou l'installeur.")
                return False
        neuf.rename(dest)
        shutil.rmtree(ancien, ignore_errors=True)
    except OSError as e:
        print(f"ÉCHEC : {nom} : {e}")
        return False
    finally:
        zip_.unlink(missing_ok=True)
        shutil.rmtree(neuf, ignore_errors=True)
    print(f"{nom} : version {voulue} installée dans {dest}")
    return True


def installer_roue(roue, dest):
    """Décompresse une roue (.whl) dans dest, comme pip : le contenu de <nom>.data/purelib et
    platlib rejoint la racine ; scripts, en-têtes et données du .data ne sont pas repris."""
    with zipfile.ZipFile(roue) as z:
        z.extractall(dest)  # extractall neutralise les chemins absolus et les « .. »
    for data in Path(dest).glob("*.data"):
        for sous in ("purelib", "platlib"):
            src = data / sous
            if src.is_dir():
                for p in src.iterdir():
                    cible = Path(dest) / p.name
                    if cible.is_dir() and p.is_dir():
                        shutil.copytree(p, cible, dirs_exist_ok=True)
                    else:
                        shutil.move(str(p), str(cible))
        shutil.rmtree(data, ignore_errors=True)


def ligne_pth(dest):
    # addsitedir (et non un simple chemin) : les .pth des roues sont lus à leur tour (pywin32)
    return f'import site; site.addsitedir(r"{dest}")\n'


def installer_libs(verifier):
    """Librairies de python-libs.json, à côté du Python AOI. Voir l'en-tête du fichier."""
    nom = "Librairies du Python AOI"
    chemin = PLUGIN / "python-libs.json"
    if not chemin.is_file():
        return True
    try:
        fiche = json.loads(chemin.read_text(encoding="utf-8"))
    except ValueError:
        print(f"ÉCHEC : fiche illisible {chemin.name}")
        return False
    python = BASE / "python"
    pth = python / "Lib" / "site-packages" / "aoi-libs.pth"
    if not (python / "python.exe").is_file():
        print(f"{nom} : en attente du Python AOI")
        return False
    try:
        base = (python / "aoi-version.txt").read_text(encoding="utf-8").strip()
    except OSError:
        base = None
    if fiche.get("python_aoi") and base != fiche["python_aoi"]:
        print(f"ATTENTION : {nom} établies pour le Python AOI {fiche['python_aoi']}, installé : {base or '?'}. Signalez-le à l'IT (verrouiller.py à relancer).")
    voulue, roues = fiche["version"], fiche.get("paquets", [])
    dest = BASE / f"python-libs-{voulue}"
    anciennes = [d for d in BASE.glob("python-libs-*")
                 if d.is_dir() and d != dest and not d.name.endswith((".tmp", ".a-effacer"))]

    if not roues:  # liste vide : rien à ajouter au Python AOI
        if not verifier:
            pth.unlink(missing_ok=True)
            for d in anciennes:
                effacer_si_libre(d)
        print(f"{nom} : aucune")
        return True
    if (dest / "aoi-version.txt").is_file():
        if verifier:
            ok = pth.is_file() and pth.read_text(encoding="utf-8") == ligne_pth(dest)
            print(f"{nom} : à jour ({voulue}, {len(roues)} paquets)" if ok
                  else f"{nom} : {voulue} à rebrancher avec /regen")
            return ok
    elif verifier:
        print(f"{nom} : version validée {voulue} ({len(roues)} paquets) à installer avec /regen")
        return False
    else:
        neuf = BASE / f"python-libs-{voulue}.tmp"
        shutil.rmtree(neuf, ignore_errors=True)
        neuf.mkdir(parents=True)
        total = sum(r.get("taille", 0) for r in roues)
        print(f"{nom} : téléchargement de la version {voulue} ({len(roues)} paquets, {total >> 20} Mo)")
        try:
            for r in roues:
                roue = neuf / r["fichier"]
                telecharger(r["url"], roue, None)
                if sha256(roue) != r["sha256"].lower():
                    print(f"ÉCHEC : l'empreinte SHA-256 de {r['fichier']} ne correspond pas à la fiche. Librairies refusées, contactez l'IT.")
                    return False
                installer_roue(roue, neuf)
                roue.unlink()
            (neuf / "aoi-version.txt").write_text(voulue, encoding="utf-8")
            shutil.rmtree(dest, ignore_errors=True)
            neuf.rename(dest)
        except (OSError, zipfile.BadZipFile) as e:
            print(f"ÉCHEC : {nom} : {e}")
            return False
        finally:
            shutil.rmtree(neuf, ignore_errors=True)
        print(f"{nom} : version {voulue} installée dans {dest} : "
              + ", ".join(f"{r['nom']} {r['version']}" for r in roues if r.get("demande")))
    # Le Python AOI remplacé par une nouvelle archive perd ce fichier : il est réécrit à chaque passage.
    if not pth.is_file() or pth.read_text(encoding="utf-8") != ligne_pth(dest):
        pth.write_text(ligne_pth(dest), encoding="utf-8")
        print(f"{nom} : branchées sur le Python AOI ({pth.name})")
    else:
        print(f"{nom} : à jour ({voulue}, {len(roues)} paquets)")
    for d in anciennes:
        if effacer_si_libre(d):
            print(f"{nom} : ancienne version {d.name} effacée")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verifier", action="store_true")
    a = ap.parse_args()
    ok = True
    for chemin in sorted(PLUGIN.glob("*-aoi.json")):
        dossier = chemin.name[:-len("-aoi.json")]
        try:
            fiche = json.loads(chemin.read_text(encoding="utf-8"))
        except ValueError:
            print(f"ÉCHEC : fiche illisible {chemin.name}")
            ok = False
            continue
        ok &= installer(fiche, dossier, NOMS.get(dossier, f"{dossier} AOI"), a.verifier)
    ok &= installer_libs(a.verifier)  # après le Python AOI, qui reçoit aoi-libs.pth
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
