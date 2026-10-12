# rhino

Serveur MCP qui permet à Claude de piloter Rhino 8. Ce dossier contient tout ce qu'il faut :

| Dossier | Contenu |
|---|---|
| `server/` | le serveur MCP `rhinomcp` 0.3.2 (Python) |
| `libs/` | ses librairies Python, figées : rien n'est téléchargé à l'installation |
| `addin/rhinomcp/` | le plugin Rhino 8 `rhinomcp` 0.4.1.1, qui reçoit les commandes dans Rhino |
| `run.py` | le lanceur : il place `server/` et `libs/` en tête du chemin de recherche |

Le serveur tourne avec le **Python AOI** de l'atelier (`%LOCALAPPDATA%\aoi\python`, Python 3.12.10 portable), installé à part par `/regen` ou `installer-poste.cmd` : il n'est pas retéléchargé quand ce dossier change.

## Installation sur un poste (une fois, par l'IT)

1. Python : le Python AOI, installé par `installer-poste.cmd` ou `/regen`.
2. **Plugin Rhino** : copier `addin/rhinomcp/` dans `%APPDATA%\McNeel\Rhinoceros\packages\8.0\`, puis relancer Rhino.
3. Le serveur MCP lui-même s'installe tout seul : Claude Code récupère le plugin `aoi` depuis le dépôt de l'atelier.

## Vérification

```
%LOCALAPPDATA%\aoi\python\python.exe -I -S run.py --check
```
La commande doit afficher `rhino : imports ok`, avec des chemins qui pointent tous dans ce dossier.

Dans Claude Code, `/mcp` doit montrer `plugin:aoi:rhino`, connecté une fois Rhino ouvert.

## Licence

`rhinomcp` est distribué sous licence MIT par Jingcheng Chen : https://github.com/jingcheng-chen/rhinomcp. Les licences des librairies se trouvent dans chaque dossier `libs/*.dist-info`.
