"""Installe les archives de l'atelier publiées à part du plugin (Python AOI, Node AOI...).

    archives_aoi.py              installe ou met à jour, seulement si la version a changé
    archives_aoi.py --verifier   indique seulement l'état

Chaque fiche <nom>-aoi.json à la racine du plugin donne la version, l'adresse de l'archive
(version GitHub du dépôt de l'atelier, hors du plugin) et son empreinte SHA-256. L'archive est
installée dans %LOCALAPPDATA%\\aoi\\<nom> et n'est téléchargée que si la version installée
diffère : un changement d'étiquette du plugin ne la recharge pas. Une archive dont l'empreinte
ne correspond pas est refusée.
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
BASE = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "aoi"
NOMS = {"python": "Python AOI", "node": "Node AOI"}

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


def installer(fiche, dossier, nom, verifier):
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
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
