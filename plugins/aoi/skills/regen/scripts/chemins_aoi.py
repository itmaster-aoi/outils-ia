"""Dossiers des outils de l'atelier sur le poste : seule définition, pour tous les scripts du plugin.

Organisation (docs/organisation-dossiers.md) :

    %LOCALAPPDATA%\\aoi\\serveurs\\<nom>-<version>   serveurs publiés à part (cortexdb, revit)
    %LOCALAPPDATA%\\aoi\\journal                     journaux et état (session.json, demarrage.log...)
    %LOCALAPPDATA%\\aoi\\addins\\<add-in>-<version>   add-ins publiés à part

Pas de migration : /regen installe à ces emplacements et efface les anciens dès qu'ils sont libres.
Pendant la transition, un serveur ou un journal encore à l'ancien emplacement (racine de
%LOCALAPPDATA%\\aoi) est lu là. La base cortexdb reste où cortexdb la met (~\\.cortexdb).
Python AOI, Node AOI et python-libs-<v> ne changent pas de place.

Le Python embarqué du plugin (fichier ._pth) n'ajoute pas le dossier du script à sys.path :
chaque script qui importe ce module ajoute lui-même skills/regen/scripts à sys.path.
N'utilise que la bibliothèque standard.
"""
import os
from pathlib import Path

AOI = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "aoi"
ADDINS = AOI / "addins"
SERVEURS = AOI / "serveurs"
JOURNAL = AOI / "journal"
ANCIEN = AOI  # ancienne organisation : serveurs et journaux à la racine


def dossier_serveur(nom, version):
    """Dossier d'un serveur versionné : serveurs\\, sinon l'ancien emplacement (pas encore réinstallé,
    ou retour à une ancienne étiquette). None si aucun n'est installé."""
    for base in (SERVEURS, ANCIEN):
        d = base / f"{nom}-{version}"
        if (d / "aoi-version.txt").is_file():
            return d
    return None


def lire_journal(nom):
    """Fichier du journal ; à défaut, celui de l'ancien emplacement."""
    f = JOURNAL / nom
    if f.is_file():
        return f
    ancien = ANCIEN / nom
    return ancien if ancien.is_file() else f
