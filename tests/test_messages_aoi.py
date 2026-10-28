"""Messages et chemins du plugin après le retrait de la skill /regen (plugin 2026.10.28.4).

    plugins\\aoi\\controle\\runtime\\python.exe tests\\test_messages_aoi.py

Les scripts des postes (upgrader-outils.cmd...) et leurs tests sont dans un dépôt interne de l'IT,
non publié. Ce fichier vérifie seulement ce que ce dépôt leur fournit.
À lancer avec le Python embarqué du plugin. Bibliothèque standard seulement.
"""
import os
import subprocess
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
PLUGIN = RACINE / "plugins" / "aoi"
resultats = []

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def verifier(nom, condition, detail=""):
    resultats.append((nom, bool(condition)))
    print(f"{'OK   ' if condition else 'ÉCHEC'} {nom}" + (f"\n      {detail}" if detail and not condition else ""))


def test_controle_hors_claude():
    """activer_controle.py --verifier hors de Claude Code (lancé par upgrader-outils.cmd) : pas de faux « INACTIF »."""
    env = {k: v for k, v in os.environ.items() if k not in ("CLAUDECODE", "PYTHONPATH")}
    r = subprocess.run([str(PLUGIN / "controle" / "runtime" / "python.exe"),
                        str(PLUGIN / "controle" / "scripts" / "activer_controle.py"), "--verifier"],
                       env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    verifier("activer_controle --verifier hors de Claude Code : pas de faux « INACTIF »",
             "INACTIF" not in r.stdout and "pas ici" in r.stdout, r.stdout + r.stderr)


def test_plus_de_regen():
    """Aucun message pour les utilisateurs ne renvoie encore à la skill retirée ; le moteur garde son chemin."""
    restes = []
    for f in PLUGIN.rglob("*.py"):
        if "libs" in f.parts:
            continue
        for i, l in enumerate(f.read_text(encoding="utf-8-sig", errors="replace").splitlines(), 1):
            if ("/aoi:regen" in l or "tapez /regen" in l.lower() or "relancez /regen" in l) and "#" not in l.split('"')[0]:
                restes.append(f"{f.relative_to(RACINE)}:{i}: {l.strip()}")
    verifier("messages : plus de renvoi à /aoi:regen", not restes, "\n      ".join(restes))
    verifier("skill /regen retirée, moteur maj.py gardé à son chemin",
             not (PLUGIN / "skills" / "regen" / "SKILL.md").exists()
             and (PLUGIN / "skills" / "regen" / "scripts" / "maj.py").is_file()
             and (PLUGIN / "controle" / "runtime" / "python.exe").is_file())
    verifier("maj.py garde l'option --finir", "--finir" in (PLUGIN / "skills" / "regen" / "scripts" / "maj.py")
             .read_text(encoding="utf-8"))


if __name__ == "__main__":
    for test in [v for k, v in list(globals().items()) if k.startswith("test_")]:
        test()
    echecs = sum(1 for _, ok in resultats if not ok)
    print(f"\n{len(resultats) - echecs} réussis, {echecs} en échec")
    sys.exit(1 if echecs else 0)
