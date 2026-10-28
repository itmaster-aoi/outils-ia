"""Dossiers des outils de l'atelier sur le poste : seule définition, pour tous les scripts du plugin.

Deux organisations coexistent pendant la migration (docs/organisation-dossiers.md) :

    ancienne   serveurs, journaux et état à la racine de %LOCALAPPDATA%\\aoi ; base cortexdb dans ~\\.cortexdb
    nouvelle   %LOCALAPPDATA%\\aoi\\serveurs, \\donnees, \\journal

Le témoin journal\\migration-dossiers.json, écrit en dernier par migrer_dossiers.py, choisit la
nouvelle. Sans lui, le poste garde l'ancienne et fonctionne comme avant : rien ne bascule à moitié.
Python AOI, Node AOI, python-libs-<v> et addins\\ ne changent pas de place.

Le Python embarqué du plugin (fichier ._pth) n'ajoute pas le dossier du script à sys.path :
chaque script qui importe ce module ajoute lui-même skills/regen/scripts à sys.path.
N'utilise que la bibliothèque standard.
"""
import os
from pathlib import Path

AOI = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "aoi"
ADDINS = AOI / "addins"
SERVEURS_NOUVEAU = AOI / "serveurs"
DONNEES = AOI / "donnees"
JOURNAL_NOUVEAU = AOI / "journal"
TEMOIN = JOURNAL_NOUVEAU / "migration-dossiers.json"
TEMOIN_ANNULE = JOURNAL_NOUVEAU / "migration-dossiers.annule.json"
BASE_CORTEXDB_ANCIENNE = Path.home() / ".cortexdb" / "cortexdb.db"
BASE_CORTEXDB_NOUVELLE = DONNEES / "cortexdb" / "cortexdb.db"


def migre():
    return TEMOIN.is_file()


def serveurs():
    """Dossier où s'installent les serveurs versionnés (<nom>-<version>)."""
    return SERVEURS_NOUVEAU if migre() else AOI


def journal():
    """Dossier des journaux et de l'état (session.json, demarrage.log, témoins de /regen)."""
    return JOURNAL_NOUVEAU if migre() else AOI


def dossier_serveur(nom, version):
    """Dossier d'un serveur versionné : celui de l'organisation active, sinon l'autre (copie pas
    encore faite, ou retour arrière). None si aucun n'est installé."""
    for base in (serveurs(), AOI if migre() else SERVEURS_NOUVEAU):
        d = base / f"{nom}-{version}"
        if (d / "aoi-version.txt").is_file():
            return d
    return None


def base_cortexdb():
    """Fichier de la base cortexdb, ou None pour laisser cortexdb choisir (~\\.cortexdb)."""
    return BASE_CORTEXDB_NOUVELLE if migre() else None


def lire_journal(nom):
    """Fichier du journal dans l'organisation active ; à défaut, celui de l'autre organisation."""
    f = journal() / nom
    if f.is_file():
        return f
    autre = (AOI if migre() else JOURNAL_NOUVEAU) / nom
    return autre if autre.is_file() else f
