# cortexdb

Mémoire d'agent et graphe de connaissances dans un seul fichier SQLite. Projet d'origine : [liliang-cn/cortexdb](https://github.com/liliang-cn/cortexdb), repris par le fork [itmaster-aoi/cortexdb](https://github.com/itmaster-aoi/cortexdb), étiquette `v2.139.1` (commit `a808c12`). Voir `VERSION-AOI.txt`.

| Élément | Origine |
|---|---|
| serveur `plugin:aoi:cortexdb` | binaire `cortexdb-mcp-windows-amd64.exe` publié par l'auteur pour `v2.139.1`, renommé `cortexdb-mcp.exe`, livré par l'archive `cortexdb-server-2.139.1` (fiche `plugins/aoi/cortexdb-server-aoi.json`) et installé par `upgrader-outils.cmd` dans `%LOCALAPPDATA%\aoi\cortexdb-server-2.139.1` |
| `/aoi:remember`, `/aoi:recall` | `commands/remember.md` et `commands/recall.md` du plugin d'origine, repris tels quels par `amont/importer_cortexdb.py` |
| skill `/aoi:cortexdb` | écrite pour l'atelier (`skills/cortexdb/SKILL.md`) |
| `LICENSE` | licence MIT du projet d'origine |

## Données

La base est `%USERPROFILE%\.cortexdb\cortexdb.db`, sur le poste de l'utilisateur. `plugins/aoi/.mcp.json` vide les variables des services externes (`OPENAI_*`, `CORTEXDB_EMBED_*`, `CORTEXDB_LLM_*`, `CORTEXDB_RERANK_*`) et celles du serveur partagé (`CORTEXDB_REMOTE`, `CORTEXDB_GRPC_TOKEN`). Le serveur travaille donc en mode lexical, sans service externe. Les fonctions qui demandent un modèle de langage restent inactives.

Non repris : la skill d'origine (documentation de la librairie Go), les 11 autres commandes, les crochets (rappel à chaque requête, contexte avant chaque lecture de fichier), le mod `cortexdb-live`.

## Vérification

1. `/mcp` montre `plugin:aoi:cortexdb` connecté.
2. `/aoi:remember Test : le poste de l'IT utilise cortexdb.`
3. `/aoi:recall cortexdb` retrouve ce fait.

## Licence

MIT, « Copyright (c) 2025 liliang-cn » (`LICENSE`).
