# rhino

Serveur MCP qui permet à Claude de piloter Rhino 8. Ce dossier contient tout ce qu'il faut :

| Dossier | Contenu |
|---|---|
| `server/` | le serveur MCP `rhinomcp` 0.3.2 (Python) |
| `libs/` | ses librairies Python, figées : rien n'est téléchargé à l'installation |
| `addin/rhinomcp/` | le plugin Rhino 8 `rhinomcp` 0.4.1.1, qui reçoit les commandes dans Rhino |
| `runtime/` | Python 3.12.10 officiel, version portable (« embeddable ») de python.org : rien à installer sur le poste |
| `run.py` | le lanceur : il n'utilise que `runtime/`, `server/` et `libs/`, jamais le Python ni les paquets du poste |

## Installation sur un poste (une fois, par l'IT)

1. Rien à installer pour le serveur : Python 3.12 est fourni dans `runtime/`.
2. **Plugin Rhino** : copier `addin/rhinomcp/` dans `%APPDATA%\McNeel\Rhinoceros\packages\8.0\`, puis relancer Rhino.
3. Le serveur MCP lui-même s'installe tout seul : Claude Code récupère le plugin `aoi` depuis le dépôt de l'atelier.

## Vérification

```
runtime\python.exe -I -S run.py --check
```
La commande doit afficher `rhino : imports ok`, avec des chemins qui pointent tous dans ce dossier.

Dans Claude Code, `/mcp` doit montrer `plugin:aoi:rhino`, connecté une fois Rhino ouvert.

## Licence

`rhinomcp` est distribué sous licence MIT par Jingcheng Chen : https://github.com/jingcheng-chen/rhinomcp. Les licences des librairies se trouvent dans chaque dossier `libs/*.dist-info`.
