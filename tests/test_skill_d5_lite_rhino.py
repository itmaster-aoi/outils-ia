"""Contrôle statique de la skill /aoi:d5-lite-rhino (plugin 2026.11.12.1).

    plugins\\aoi\\controle\\runtime\\python.exe tests\\test_skill_d5_lite_rhino.py

Ce test ne demande ni D5 Lite ni Rhino. Les essais sur le logiciel sont dans
plugins/aoi/skills/d5-lite-rhino/essais (voir LISEZMOI.md).
À lancer avec le Python embarqué du plugin. Bibliothèque standard seulement.
"""
import ast
import json
import re
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
PLUGIN = RACINE / "plugins" / "aoi"
SKILL = PLUGIN / "skills" / "d5-lite-rhino"
resultats = []

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def verifier(nom, condition, detail=""):
    resultats.append((nom, bool(condition)))
    print(f"{'OK   ' if condition else 'ÉCHEC'} {nom}" + (f"\n      {detail}" if detail and not condition else ""))


def test_en_tete():
    """L'en-tête YAML se lit : fins de ligne LF, nom et description présents."""
    brut = (SKILL / "SKILL.md").read_bytes()
    texte = brut.decode("utf-8")
    verifier("SKILL.md commence par un en-tête YAML", texte.startswith("---\n"))
    verifier("SKILL.md sans fin de ligne CRLF", b"\r\n" not in brut)
    entete = texte.split("---\n")[1] if texte.startswith("---\n") else ""
    verifier("en-tête : name: d5-lite-rhino", re.search(r"^name: d5-lite-rhino$", entete, re.M) is not None)
    verifier("en-tête : description présente", re.search(r"^description: .{80,}$", entete, re.M) is not None)


def test_fichiers():
    """Les fichiers cités par SKILL.md existent."""
    texte = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    cites = sorted(set(re.findall(r"`((?:scripts|references|essais)/[\w./-]+\.(?:py|md))`", texte)))
    verifier("SKILL.md cite des scripts et des références", len(cites) >= 6, str(cites))
    for chemin in cites:
        verifier(f"fichier cité présent : {chemin}", (SKILL / chemin).is_file())
    verifier("provenance VERSION-AOI.txt présente", (SKILL / "VERSION-AOI.txt").is_file())
    verifier("aucun dossier __pycache__", not list(SKILL.rglob("__pycache__")))


def test_scripts():
    """Les scripts se compilent. Les modules pour Rhino restent compatibles avec IronPython 2.7."""
    for f in sorted(SKILL.rglob("*.py")):
        source = f.read_text(encoding="utf-8")
        try:
            ast.parse(source, filename=str(f))
            ok, detail = True, ""
        except SyntaxError as err:
            ok, detail = False, str(err)
        verifier(f"syntaxe : {f.relative_to(SKILL)}", ok, detail)
    for nom in ("d5mat.py", "d5lum.py", "d5scene.py"):
        source = (SKILL / "scripts" / nom).read_text(encoding="utf-8")
        verifier(f"{nom} : pas de f-string (IronPython 2.7)", re.search(r"""\bf["']""", source) is None)
        verifier(f"{nom} : pas d'annotation de type (IronPython 2.7)", "->" not in source and "from __future__" not in source)
        verifier(f"{nom} : source en ASCII", all(ord(c) < 128 for c in source))
        verifier(f"{nom} : jamais d'affectation directe objet.RenderMaterial (écrase une entrée de table)",
                 re.search(r"^\s*(?!l\.|layer\.)\w+\.RenderMaterial\s*=", source, re.M) is None)


def test_aucune_donnee_de_poste():
    """Dépôt public : ni chemin d'utilisateur, ni chemin réseau, ni adresse e-mail, ni jeton."""
    interdits = re.compile(r"C:\\\\?Users\\\\?(?!<)[A-Za-z]|[\w.-]+@[\w-]+\.[a-z]{2,}|(?<![\w%:\\\\])(?:\\\\){1,2}[A-Za-z][\w-]*\\{1,2}[A-Za-z]|gho_[A-Za-z0-9]", re.I)
    for f in sorted(SKILL.rglob("*")):
        if f.is_file() and f.suffix in (".py", ".md", ".txt", ".json"):
            trouve = interdits.search(f.read_text(encoding="utf-8", errors="replace"))
            verifier(f"aucune donnée de poste : {f.relative_to(SKILL)}", trouve is None, trouve.group(0) if trouve else "")


def test_versions():
    """La skill est inscrite dans le catalogue, le journal et les versions."""
    version = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))["version"]
    catalogue = (RACINE / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8")
    verifier("catalogue : /aoi:d5-lite-rhino cité", "/aoi:d5-lite-rhino" in catalogue)
    verifier("VERSIONS.md : ligne de la skill", "`/aoi:d5-lite-rhino`" in (RACINE / "VERSIONS.md").read_text(encoding="utf-8"))
    source = (SKILL / "scripts" / "d5lite.py").read_text(encoding="utf-8")
    contrats = re.search(r'CONTRATS_TESTES = "(sha256:[0-9a-f]{64})"', source)
    verifier("d5lite.py : empreinte des contrats testés", contrats is not None)
    verifier("VERSION-AOI.txt : même empreinte que d5lite.py",
             contrats is not None and contrats.group(1) in (SKILL / "VERSION-AOI.txt").read_text(encoding="utf-8"))


if __name__ == "__main__":
    for test in [v for k, v in list(globals().items()) if k.startswith("test_")]:
        test()
    echecs = sum(1 for _, ok in resultats if not ok)
    print(f"\n{len(resultats) - echecs} réussis, {echecs} en échec")
    sys.exit(1 if echecs else 0)
