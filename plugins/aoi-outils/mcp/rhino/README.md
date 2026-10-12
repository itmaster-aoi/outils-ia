# aoi-rhino

Serveur MCP qui permet à Claude de piloter Rhino 8. Ce dossier contient tout ce qu'il faut :

| Dossier | Contenu |
|---|---|
| `server/` | le serveur MCP `rhinomcp` 0.3.2 (Python) |
| `libs/` | ses librairies Python, figées : rien n'est téléchargé à l'installation |
| `addin/rhinomcp/` | le plugin Rhino 8 `rhinomcp` 0.4.1.1, qui reçoit les commandes dans Rhino |
| `run.py` | le lanceur : il n'utilise que `server/` et `libs/`, jamais les paquets installés sur le poste |

## Installation sur un poste (une fois, par l'IT)

1. **Python 3.12 64 bits** doit être installé. Les librairies de `libs/` sont compilées pour cette version.
2. Définir la variable d'environnement **`AOI_PYTHON`** avec le chemin complet de ce Python, par exemple `C:\Program Files\Python312\python.exe`. Sans elle, Claude Code utilise `python`, qui sur beaucoup de postes est la mauvaise version.
3. **Plugin Rhino** : copier `addin/rhinomcp/` dans `%APPDATA%\McNeel\Rhinoceros\packages\8.0\`, puis relancer Rhino.
4. Le serveur MCP lui-même s'installe tout seul : Claude Code récupère le plugin `aoi-outils` depuis le dépôt de l'atelier.

## Vérification

```
"%AOI_PYTHON%" -I -S run.py --check
```
La commande doit afficher `aoi-rhino : imports ok`, avec des chemins qui pointent tous dans ce dossier.

Dans Claude Code, `/mcp` doit montrer `plugin:aoi-outils:aoi-rhino`, connecté une fois Rhino ouvert.

## Licence

`rhinomcp` est distribué sous licence MIT par Jingcheng Chen : https://github.com/jingcheng-chen/rhinomcp. Les licences des librairies se trouvent dans chaque dossier `libs/*.dist-info`.
