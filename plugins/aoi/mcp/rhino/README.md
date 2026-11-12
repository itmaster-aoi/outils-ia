# rhino

Serveur MCP qui permet à Claude de piloter Rhino 8. Ce dossier contient tout ce qu'il faut :

| Dossier | Contenu |
|---|---|
| `server/` | le serveur MCP `rhinomcp` 0.3.2 (Python) |
| `libs/` | ses librairies Python, figées : rien n'est téléchargé à l'installation |
| `addin.json` | la fiche du plugin Rhino 8 `rhinomcp` 0.4.1.1, qui reçoit les commandes dans Rhino : publié à part (archive `rhino-addin-<version>`), avec son adresse et son empreinte SHA-256 |
| `run.py` | le lanceur : il place `server/` et `libs/` en tête du chemin de recherche |

Le serveur tourne avec le **Python AOI** (`%LOCALAPPDATA%\aoi\python`, Python 3.12.10 portable), installé à part : il n'est pas retéléchargé quand ce dossier change.

## Installation

1. Python : le Python AOI, installé par la mise à jour du plugin (`skills/regen/scripts/maj.py`).
2. **Plugin Rhino** : la mise à jour télécharge l'archive (seulement si sa version manque), vérifie son empreinte et la copie dans `%APPDATA%\McNeel\Rhinoceros\packages\8.0\`, Rhino fermé. Relancer ensuite Rhino.

Les librairies Python (`libs/`) **restent dans le plugin**, dans le dossier de `run.py`.
3. Le serveur MCP lui-même s'installe tout seul : Claude Code récupère le plugin `aoi` depuis ce dépôt.

## Vérification

```
%LOCALAPPDATA%\aoi\python\python.exe -I -S run.py --check
```
La commande doit afficher `rhino : imports ok`, avec des chemins qui pointent tous dans ce dossier.

Dans Claude Code, `/mcp` doit montrer `plugin:aoi:rhino`, connecté une fois Rhino ouvert.

## Licence

`rhinomcp` est distribué sous licence MIT par Jingcheng Chen : https://github.com/jingcheng-chen/rhinomcp. Les licences des librairies se trouvent dans chaque dossier `libs/*.dist-info`.
