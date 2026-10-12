"""Copie le contrôle des imports Python dans le dossier fixe que désigne la console.

    activer_controle.py              copie le contrôle et la liste blanche dans C:\\ProgramData\\aoi
    activer_controle.py --verifier   indique seulement si le contrôle est en place

Les managed settings de l'atelier contiennent "env": {"PYTHONPATH": "C:\\ProgramData\\aoi\\guard"} :
Claude Code transmet cette valeur à toutes ses commandes, Bash et PowerShell. Le chemin est le même
sur tous les postes, alors que le dossier du plugin change à chaque version. Ce script tient la
copie à jour ; il ne modifie ni le registre ni les variables du compte Windows.
N'utilise que la bibliothèque standard.
"""
import argparse
import filecmp
import os
import shutil
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
DEST = Path(os.environ.get("ProgramData") or r"C:\ProgramData") / "aoi"
GUARD = DEST / "guard"
FICHIERS = [(SKILL / "guard" / "sitecustomize.py", GUARD / "sitecustomize.py"),
            (SKILL / "whitelist.txt", DEST / "whitelist.txt")]

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def copie_a_jour():
    return all(d.is_file() and filecmp.cmp(s, d, shallow=False) for s, d in FICHIERS)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verifier", action="store_true")
    a = ap.parse_args()

    if not a.verifier:
        try:
            GUARD.mkdir(parents=True, exist_ok=True)
            for s, d in FICHIERS:
                shutil.copy2(s, d)
        except OSError as e:
            print(f"ÉCHEC : copie du contrôle dans {GUARD} impossible ({e}). Contactez l'IT.")
            return 1
        print(f"Contrôle copié dans {GUARD}")

    copie = copie_a_jour()
    print(f"Copie du contrôle ({GUARD}) : {'à jour' if copie else 'absente ou ancienne'}")
    if a.verifier:
        # Seule une commande lancée par Claude Code voit le PYTHONPATH de la console.
        pp = os.environ.get("PYTHONPATH", "")
        actif = os.path.normcase(os.path.normpath(pp)) == os.path.normcase(str(GUARD)) if pp else False
        print(f"PYTHONPATH de cette commande : {pp or '(vide)'}")
        print("CONTRÔLE EN PLACE" if copie and actif else
              "CONTRÔLE INACTIF : vérifier la clé env.PYTHONPATH des managed settings, puis lancer /regen")
        return 0 if copie and actif else 1
    return 0 if copie else 1


if __name__ == "__main__":
    sys.exit(main())
