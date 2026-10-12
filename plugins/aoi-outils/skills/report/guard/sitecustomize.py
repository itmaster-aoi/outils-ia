"""Contrôle des imports Python de l'atelier (aoi-outils / report).

Chargé automatiquement par Python au démarrage quand ce dossier est dans PYTHONPATH
(le plugin aoi-outils l'y place pour les commandes que lance Claude Code).

Pour chaque librairie importée :
- la bibliothèque standard de Python est toujours acceptée ;
- une librairie inscrite dans whitelist.txt est acceptée ;
- une dépendance importée par une librairie acceptée est acceptée ;
- un module du dossier de travail (les scripts du projet) est accepté ;
- tout le reste est refusé : l'import lève ModuleNotFoundError.

Chaque décision est inscrite, une fois par librairie et par processus, dans le journal
%LOCALAPPDATA%\\aoi\\imports.jsonl, que la skill /report résume.

Variables d'environnement :
- AOI_IMPORT_MODE=report : journaliser sans refuser (mode d'essai) ;
- AOI_IMPORT_WHITELIST : autre chemin de liste blanche ;
- AOI_IMPORT_LOG : autre chemin de journal.
"""
import datetime
import importlib.machinery
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_WHITELIST = os.environ.get("AOI_IMPORT_WHITELIST") or os.path.join(os.path.dirname(_HERE), "whitelist.txt")
_LOG = os.environ.get("AOI_IMPORT_LOG") or os.path.join(
    os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "aoi", "imports.jsonl")
_ENFORCE = os.environ.get("AOI_IMPORT_MODE", "enforce").lower() != "report"


def _read_whitelist(path):
    names = set()
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                name = line.split("#", 1)[0].strip()
                if name:
                    names.add(name)
    except OSError:
        pass  # liste absente : seule la bibliothèque standard passe
    return names


_ALLOWED = _read_whitelist(_WHITELIST)
_STDLIB = set(sys.stdlib_module_names) | set(sys.builtin_module_names)
_ROOTS = {os.path.normcase(os.path.abspath(os.getcwd()))}
if sys.argv and sys.argv[0] not in ("", "-c", "-m"):
    _ROOTS.add(os.path.normcase(os.path.dirname(os.path.abspath(sys.argv[0]))))
_decided = {}


def _log(top, decision, detail=""):
    if top in _decided:
        return
    _decided[top] = decision
    try:
        os.makedirs(os.path.dirname(_LOG), exist_ok=True)
        with open(_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "date": datetime.datetime.now().isoformat(timespec="seconds"),
                "pid": os.getpid(),
                "script": sys.argv[0] if sys.argv else "",
                "cwd": os.getcwd(),
                "librairie": top,
                "decision": decision,
                "detail": detail,
            }, ensure_ascii=False) + "\n")
    except OSError:
        pass


def _importer_top():
    """Librairie (hors importlib et hors ce fichier) qui a demandé l'import."""
    frame = sys._getframe(2)
    while frame is not None:
        name = frame.f_globals.get("__name__", "")
        top = name.split(".", 1)[0]
        if top and top not in ("importlib", "_frozen_importlib", "_frozen_importlib_external") \
                and frame.f_code.co_filename != __file__:
            return top
        frame = frame.f_back
    return ""


def _is_local(spec):
    origin = spec.origin if spec and spec.origin not in (None, "built-in", "frozen") else None
    if origin is None and spec and spec.submodule_search_locations:
        origin = next(iter(spec.submodule_search_locations), None)
    if not origin:
        return False
    origin = os.path.normcase(os.path.abspath(origin))
    return any(origin.startswith(root + os.sep) for root in _ROOTS)


class _AoiImportGuard:
    def find_spec(self, fullname, path=None, target=None):
        top = fullname.split(".", 1)[0]
        if top in _STDLIB or top in _decided and _decided[top] != "refusé":
            return None
        if top in _ALLOWED:
            _log(top, "accepté", "liste blanche")
            return None
        spec = importlib.machinery.PathFinder.find_spec(top)
        if spec is None:
            return None  # introuvable : Python lèvera lui-même l'erreur habituelle
        importer = _importer_top()
        if importer and importer != top and _decided.get(importer) in ("accepté", "dépendance"):
            _log(top, "dépendance", "importé par " + importer)
            return None
        if _is_local(spec):
            _log(top, "local", spec.origin or "")
            return None
        _log(top, "refusé" if _ENFORCE else "signalé", spec.origin or "")
        if _ENFORCE:
            raise ModuleNotFoundError(
                f"Import de '{top}' refusé : cette librairie n'est pas dans la liste blanche "
                f"de l'atelier ({_WHITELIST}). Demandez à l'IT de la valider.",
                name=fullname)
        return None


sys.meta_path.insert(0, _AoiImportGuard())
