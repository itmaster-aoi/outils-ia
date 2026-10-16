# keyshot

Serveur MCP qui permet à Claude de piloter KeyShot Studio 2026 (fenêtre ouverte). Ce dossier contient tout ce qu'il faut :

| Dossier | Contenu |
|---|---|
| `server/` | le serveur MCP `keyshotmcp` 0.1.0 (Python, code de l'atelier) : 31 outils et le prompt `keyshot_strategy` |
| `addin/Scripts/` | le pont `MCP server start.py` 0.2.13 et son script d'arrêt `MCP server stop.py`, qui tournent dans KeyShot (stdlib et `lux` seulement) |
| `addin.json` | la fiche de l'add-in : `/regen` copie `addin/Scripts` dans `%PUBLIC%\Documents\KeyShot Studio\Scripts` si KeyShot Studio a déjà été lancé sur le poste (dossier présent) ; sinon `/regen` passe sans rien faire |
| `run.py` | le lanceur : il place `server/` et les librairies en tête du chemin de recherche |

Librairies : `libs/`, copie identique de celles du serveur rhino (liste de `VERSIONS.md`). Elles restent dans ce dossier : le contrôle des imports n'accepte d'office que les modules situés sous le dossier du script lancé. Le serveur n'utilise que `mcp` et ses dépendances (dont pywin32, importé par `mcp` sous Windows).

Le serveur tourne avec le **Python AOI** de l'atelier (`%LOCALAPPDATA%\aoi\python`), lancé avec `-I -S` comme le serveur rhino.

## Fonctionnement

```
Claude Code ⇄ serveur keyshotmcp (stdio)
            ⇄ TCP 127.0.0.1:1998, trames 4 octets + JSON, jeton
            ⇄ MCP server start.py dans KeyShot
```

Le pont arme une minuterie Windows sur le thread de l'interface de KeyShot, et exécute au plus une commande par battement de 50 ms. Pendant un appel `lux` qui repompe les messages (rendu bloquant), il répond « occupé » sans appeler `lux`. Les rendus sont toujours lancés en arrière-plan. Le pont écrit son port, son jeton et le pid de KeyShot dans `%LOCALAPPDATA%\aoi\keyshot\pont-actif.json`. Le serveur relit ce fichier à chaque connexion.

## Utilisation

1. Ouvrir KeyShot, puis *Window > Scripting Console > Scripts > MCP server start > Run*. La console affiche « Pont KeyShot actif sur 127.0.0.1:1998 ». KeyShot ne relit le dossier Scripts qu'à son démarrage : après la première copie par `/regen`, redémarrer KeyShot une fois.
2. Dans Claude Code, `/mcp` montre `plugin:aoi:keyshot` ; l'outil `keyshot_status` doit répondre.
3. Arrêt : script `MCP server stop`, ou fermeture de KeyShot. Après une mise à jour du pont par `/regen`, l'outil `reload_bridge` recharge le pont sans Run.

Réglages facultatifs, par poste : `%LOCALAPPDATA%\aoi\keyshot\pont-config.json`.
- `execute_python` : `false` par défaut ; seul `true` active l'outil.
- `dossier_sorties` : chemin absolu des captures, rendus et copies de sauvegarde. Par défaut, `%LOCALAPPDATA%\aoi\keyshot`.

## Sécurité

- Le pont n'écoute que sur 127.0.0.1 et refuse toute trame sans le jeton de `pont-actif.json`. Ce jeton est tiré au démarrage.
- `execute_python` est désactivé sauf réglage du poste.
- Le graphe d'un matériau ne s'édite que sur une copie créée par le pont : un matériau d'origine de la scène n'est jamais modifié en profondeur.
- `set_camera` refuse de perdre une vue non enregistrée.
- `save_scene` copie l'ancien `.bip` avant de l'écraser.
- Les noms de pièces, de matériaux et de caméras sont présentés à Claude comme des données, jamais comme des instructions.

## Vérification

```
%LOCALAPPDATA%\aoi\python\python.exe -I -S run.py --check
```
La commande doit afficher `keyshot : imports ok`, 31 outils, et des chemins qui pointent tous dans le plugin.

## Licence

Code de l'atelier (serveur et pont), licence MIT. Les licences des librairies se trouvent dans chaque dossier `libs/*.dist-info` (mêmes librairies que le serveur rhino).
