"""Installe le Python AOI de l'atelier dans %LOCALAPPDATA%\\aoi\\python.

    python_aoi.py              installe ou met à jour, seulement si la version a changé
    python_aoi.py --verifier   indique seulement l'état

La fiche python-aoi.json du plugin donne la version, l'adresse de l'archive (version GitHub
du dépôt de l'atelier, hors du plugin) et son empreinte SHA-256. L'archive n'est téléchargée que
si la version installée diffère : un changement d'étiquette du plugin ne la recharge pas.
Une archive dont l'empreinte ne correspond pas est refusée.
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
FICHE = PLUGIN / "python-aoi.json"
BASE = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "aoi"
DEST = BASE / "python"

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def version_installee():
    try:
        return (DEST / "aoi-version.txt").read_text(encoding="utf-8").strip()
    except OSError:
        return None


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verifier", action="store_true")
    a = ap.parse_args()

    try:
        fiche = json.loads(FICHE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        print("Python AOI : pas de fiche dans ce plugin.")
        return 0
    voulue, actuelle = fiche["version"], version_installee()
    if actuelle == voulue and (DEST / "python.exe").is_file():
        print(f"Python AOI : à jour ({voulue}, {DEST})")
        return 0
    if a.verifier:
        print(f"Python AOI : {actuelle or 'absent'}, version validée {voulue} : à installer avec /regen")
        return 1

    BASE.mkdir(parents=True, exist_ok=True)
    zip_ = BASE / f"python-aoi-{voulue}.zip"
    neuf = BASE / f"python-{voulue}.tmp"
    print(f"Python AOI : téléchargement de la version {voulue} ({fiche.get('taille', 0) >> 20} Mo)")
    try:
        telecharger(fiche["url"], zip_, fiche.get("taille"))
        if sha256(zip_) != fiche["sha256"].lower():
            print("ÉCHEC : l'empreinte SHA-256 de l'archive ne correspond pas à la fiche. Archive refusée, contactez l'IT.")
            return 1
        shutil.rmtree(neuf, ignore_errors=True)
        with zipfile.ZipFile(zip_) as z:
            z.extractall(neuf)
        if not (neuf / "python.exe").is_file():
            print("ÉCHEC : archive incomplète (python.exe absent).")
            return 1
        ancien = BASE / "python.ancien"
        shutil.rmtree(ancien, ignore_errors=True)
        if DEST.exists():
            try:
                DEST.rename(ancien)
            except OSError:
                print(f"ÉCHEC : {DEST} est en cours d'utilisation. Fermez les scripts Python ouverts, puis relancez /regen.")
                return 1
        neuf.rename(DEST)
        shutil.rmtree(ancien, ignore_errors=True)
    except OSError as e:
        print(f"ÉCHEC : {e}")
        return 1
    finally:
        zip_.unlink(missing_ok=True)
        shutil.rmtree(neuf, ignore_errors=True)
    print(f"Python AOI : version {voulue} installée dans {DEST}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
