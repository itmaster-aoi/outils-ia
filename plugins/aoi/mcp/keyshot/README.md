# keyshot

Serveur MCP qui permet à Claude de piloter KeyShot Studio 2026 (fenêtre ouverte). Code repris tel quel de [lfoletti/keyshot-mcp](https://github.com/lfoletti/keyshot-mcp), étiquette `v1.0.0` (commit `266c26a`), par `amont/importer_keyshot.py` : voir `VERSION-AOI.txt`. Ne pas modifier ces fichiers à la main, les changements se font dans le projet d'origine puis passent par une nouvelle importation.

| Dossier | Contenu |
|---|---|
| `server/` | le serveur MCP `keyshotmcp` 1.0.0 : 33 outils, prompts `keyshot_materiaux`, `keyshot_strategy` |
| `addin/Scripts/` | le pont `MCP start.py` 1.0.0 et son script d'arrêt `MCP stop.py`, qui tournent dans KeyShot (stdlib et `lux` seulement) |
| `addin.json` | la fiche de l'add-in : `upgrader-outils.cmd` copie `addin/Scripts` dans `%PUBLIC%\Documents\KeyShot Studio\Scripts` si KeyShot Studio a déjà été lancé sur le poste (dossier présent), après avoir effacé les scripts des versions précédentes (`MCP server start.py`, `MCP server stop.py`, `aoi_keyshot_*.py`) |
| `run.py` | le lanceur : il place `server/` et `libs/` (avec les dossiers de pywin32) en tête du chemin de recherche |
| `LICENSE` | licence MIT du projet d'origine |

Librairies : `libs/`, copie identique de celles du serveur rhino (liste de `VERSIONS.md`), hors importation. Elles restent dans ce dossier : le contrôle des imports n'accepte d'office que les modules situés sous le dossier du script lancé. Le serveur n'utilise que `mcp` et ses dépendances.

Le serveur tourne avec le **Python AOI** de l'atelier (`%LOCALAPPDATA%\aoi\python`), lancé avec `-I -S` comme le serveur rhino (`plugins/aoi/.mcp.json`).

## Fonctionnement

```
Claude Code ⇄ serveur keyshotmcp (stdio)
            ⇄ TCP 127.0.0.1:1998, trames 4 octets + JSON, jeton
            ⇄ MCP start.py dans KeyShot
```

Le pont écrit son port, son jeton et le pid de KeyShot dans `%LOCALAPPDATA%\keyshot-mcp\pont-actif.json`, et son journal dans `pont.log` du même dossier. Le serveur relit ce fichier à chaque connexion.

## Utilisation

1. Après `upgrader-outils.cmd`, redémarrer KeyShot une fois (il ne relit le dossier Scripts qu'à son démarrage).
2. Dans KeyShot : *Window > Scripting Console > Scripts > MCP start > Run*.
3. Dans Claude Code, `/mcp` montre `plugin:aoi:keyshot` ; l'outil `keyshot_status` doit répondre.
4. Arrêt : script `MCP stop`, ou fermeture de KeyShot. Après une mise à jour du pont par `upgrader-outils.cmd`, l'outil `reload_bridge` recharge le pont sans Run.

Réglages facultatifs, par poste : `%LOCALAPPDATA%\keyshot-mcp\pont-config.json` (avant la 1.0.0 : `%LOCALAPPDATA%\aoi\keyshot\`, plus lu).
- `execute_python` : `false` par défaut ; seul `true` active l'outil (ou la variable `KEYSHOT_MCP_EXECUTE_PYTHON=1`).
- `dossier_sorties` : chemin absolu des captures, rendus et copies de sauvegarde.
- `dossiers_textures` : dossiers où les textures peuvent être lues (les chemins réseau sont refusés).

## Vérification

```
%LOCALAPPDATA%\aoi\python\python.exe -I -S run.py --check
```
La commande doit afficher 33 outils et des chemins qui pointent tous dans le plugin.

## Licence

MIT, « Copyright (c) 2026 Lauro Foletti » (`LICENSE`). Projet sans lien avec Luxion. Les licences des librairies se trouvent dans chaque dossier `libs/*.dist-info`.
