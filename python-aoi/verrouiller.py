"""Verrouille les librairies ajoutées au Python AOI sans le reconstruire (réservé à l'IT).

    python verrouiller.py                 avec un Python 3 qui a pip (anaconda, py -3.12)
    python verrouiller.py --version 2026-10-16.2

Lit ajouts.txt (une librairie par ligne, comme paquets.txt), résout ses dépendances en roues
binaires Windows 64 bits pour Python 3.12, en gardant les versions déjà présentes dans le
Python AOI (verrou.txt). Les roues absentes du Python AOI sont vérifiées contre PyPI
(adresse et empreinte SHA-256) et inscrites dans plugins/aoi/python-libs.json. Les postes les
installent avec /regen ou installer-poste.cmd (archives_aoi.py), sans pip.

Essai : les roues sont installées dans un dossier temporaire, puis le Python AOI de ce poste
importe chaque librairie demandée avec la liste blanche du dépôt, contrôle des imports actif.
Une librairie dont aucun module n'est dans controle/whitelist.txt est signalée.

Ensuite : relire python-libs.json, compléter VERSIONS.md et CHANGELOG.md, monter la version de
plugin.json, créer l'étiquette et la reporter dans la console. Aucune archive à publier.
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

ICI = Path(__file__).resolve().parent
RACINE = ICI.parent
PLUGIN = RACINE / "plugins" / "aoi"
FICHE = PLUGIN / "python-libs.json"
WHITELIST = PLUGIN / "controle" / "whitelist.txt"
PYTHON_AOI = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "aoi" / "python" / "python.exe"
sys.path.insert(0, str(PLUGIN / "skills" / "regen" / "scripts"))
from archives_aoi import installer_roue, sha256  # noqa: E402  même décompression que les postes

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def norm(nom):
    return re.sub(r"[-_.]+", "-", nom).lower()


def lignes(chemin):
    for l in Path(chemin).read_text(encoding="utf-8-sig").splitlines():
        l = l.split("#", 1)[0].strip()
        if l:
            yield l


def modules(roue):
    """Modules importables d'une roue : top_level.txt, sinon les entrées de premier niveau."""
    with zipfile.ZipFile(roue) as z:
        noms = z.namelist()
        top = next((n for n in noms if n.endswith(".dist-info/top_level.txt")), None)
        if top:
            # « win32\lib\win32con » (pywin32) : importable sous son dernier nom, le .pth de la roue
            # ajoutant win32\lib au chemin de recherche
            return sorted({re.split(r"[\\/]", m.strip())[-1] for m in z.read(top).decode().splitlines() if m.strip()})
    res = set()
    for n in noms:
        tete = n.split("/", 1)[0]
        if tete.endswith((".dist-info", ".data", ".pth")):
            continue
        res.add(tete.split(".", 1)[0] if "." in tete else tete)
    return sorted(res)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", help="version de python-libs.json, par défaut la date du jour")
    a = ap.parse_args()
    # Comme construire.ps1 : hors de Claude Code, où le contrôle des imports refuse pip.
    if os.environ.get("CLAUDECODE") or os.environ.get("CLAUDE_CODE_CHILD_SESSION"):
        sys.exit("Lancez ce script dans une fenêtre ordinaire, pas depuis Claude Code.")

    demandes = list(lignes(ICI / "ajouts.txt"))
    noms_demandes = {norm(re.split(r"[<>=!~;\[ ]", d, 1)[0]) for d in demandes}
    base = {}  # paquets du Python AOI : nom normalisé -> version
    for l in lignes(ICI / "verrou.txt"):
        nom, _, version = l.partition("==")
        base[norm(nom)] = version
    python_aoi = json.loads((PLUGIN / "python-aoi.json").read_text(encoding="utf-8"))["version"]
    blanche = set(lignes(WHITELIST))

    tmp = Path(tempfile.mkdtemp(prefix="aoi-libs-"))
    try:
        roues, essai = tmp / "roues", tmp / "essai"
        roues.mkdir()
        contraintes = tmp / "contraintes.txt"
        contraintes.write_text("\n".join(f"{n}=={v}" for n, v in base.items() if n != "graphifyy") + "\n",
                               encoding="utf-8")
        paquets = []
        if demandes:
            r = subprocess.run([sys.executable, "-m", "pip", "download", "-r", str(ICI / "ajouts.txt"),
                                "-c", str(contraintes), "--only-binary=:all:", "--platform", "win_amd64",
                                "--python-version", "3.12", "--implementation", "cp",
                                "--disable-pip-version-check", "--dest", str(roues)])
            if r.returncode:
                sys.exit("ÉCHEC de la résolution. Si une dépendance demande une autre version qu'un paquet "
                         "du Python AOI, il faut reconstruire le Python AOI (construire.ps1).")
        for roue in sorted(roues.glob("*.whl")):
            nom, version = roue.name.split("-")[:2]
            if base.get(norm(nom)) == version:
                continue  # déjà dans le Python AOI
            with urllib.request.urlopen(f"https://pypi.org/pypi/{nom}/{version}/json", timeout=60) as f:
                pypi = next((u for u in json.load(f)["urls"] if u["filename"] == roue.name), None)
            empreinte = sha256(roue)
            if not pypi or pypi["digests"]["sha256"] != empreinte:
                sys.exit(f"ÉCHEC : {roue.name} introuvable sur PyPI ou empreinte différente.")
            paquets.append({"nom": nom, "version": version, "fichier": roue.name, "url": pypi["url"],
                            "sha256": empreinte, "taille": roue.stat().st_size,
                            "demande": norm(nom) in noms_demandes, "modules": modules(roue)})
            installer_roue(roue, essai)

        # Essai sur le Python AOI de ce poste, contrôle des imports actif, liste blanche du dépôt
        ok = True
        for p in (p for p in paquets if p["demande"]):
            admis = [m for m in p["modules"] if m in blanche]
            if not admis:
                print(f"ATTENTION : {p['nom']} : aucun de ses modules n'est dans la liste blanche. "
                      f"Modules importables : {', '.join(p['modules'])}")
                ok = False
                continue
            if not PYTHON_AOI.is_file():
                print(f"Essai d'import impossible : {PYTHON_AOI} absent.")
                continue
            env = dict(os.environ, AOI_IMPORT_WHITELIST=str(WHITELIST), AOI_IMPORT_MODE="enforce",
                       AOI_IMPORT_LOG=str(tmp / "imports.jsonl"))
            code = f"import site; site.addsitedir(r'{essai}'); " + "; ".join(f"import {m}" for m in admis)
            r = subprocess.run([str(PYTHON_AOI), "-c", code], env=env, capture_output=True, text=True)
            print(f"{p['nom']} {p['version']} : " + ("import réussi (" + ", ".join(admis) + ")" if r.returncode == 0
                  else "ÉCHEC de l'import :\n" + r.stderr.strip()))
            ok &= r.returncode == 0
        if not ok:
            sys.exit("python-libs.json n'est pas écrit : corriger ajouts.txt ou la liste blanche, puis relancer.")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    for p in paquets:
        del p["modules"]
    ancienne = json.loads(FICHE.read_text(encoding="utf-8")) if FICHE.is_file() else {}
    if ancienne.get("paquets") == paquets and ancienne.get("python_aoi") == python_aoi:
        print(f"python-libs.json inchangé (version {ancienne['version']}).")
        return 0
    version = a.version or datetime.date.today().isoformat()
    if not a.version and str(ancienne.get("version", "")).startswith(version):
        n = ancienne["version"][len(version) + 1:] or "1"
        version = f"{version}.{int(n) + 1}"
    fiche = {"version": version, "python_aoi": python_aoi, "paquets": paquets}
    FICHE.write_text(json.dumps(fiche, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\npython-libs.json : version {version}, {len(paquets)} roues, "
          f"{sum(p['taille'] for p in paquets) >> 20} Mo, pour le Python AOI {python_aoi}")
    for p in paquets:
        print(f"  {'*' if p['demande'] else ' '} {p['nom']}=={p['version']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
