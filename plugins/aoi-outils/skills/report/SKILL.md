---
name: report
description: Rapport des librairies Python chargées par les scripts que Claude exécute sur ce poste, comparées à la liste blanche de l'atelier (acceptées, refusées, dépendances). Utiliser quand l'utilisateur tape /report, demande quelles librairies Python ont été chargées ou refusées, ou quand un script échoue avec « Import de '…' refusé ».
---

# /report : imports Python contrôlés

La commande se tape `/report`. Si une autre commande porte déjà ce nom, utiliser `/aoi-outils:report`.

Le plugin `aoi-outils` contrôle chaque librairie Python que chargent les scripts lancés par Claude sur ce poste. Le contrôle (`guard/sitecustomize.py`) est actif dans toutes les commandes de la session :
- il **journalise** chaque librairie chargée dans `%LOCALAPPDATA%\aoi\imports.jsonl` ;
- il **compare** son nom à `whitelist.txt` ;
- il **refuse l'import** d'une librairie non identifiée. Le script échoue alors avec `Import de '<nom>' refusé`.

Sont toujours acceptés : la bibliothèque standard de Python, les dépendances importées par une librairie acceptée, et les modules du dossier de travail.

## Ce que tu fais quand on t'appelle

1. Relève les **serveurs MCP chargés** dans ta session, sous le nom qu'affiche `/mcp`. Tes outils MCP s'appellent `mcp__<serveur>__<outil>`, et pour un plugin `mcp__plugin_<plugin>_<serveur>__<outil>`, ce qui correspond à `plugin:<plugin>:<serveur>`. Les connecteurs claude.ai s'appellent `claude.ai <nom>`.
2. Lance le rapport avec le Python fourni dans `runtime/` (le poste n'a pas forcément de Python), en passant ces serveurs :
   ```
   "<dossier de cette skill>/runtime/python.exe" "<dossier de cette skill>/scripts/report.py" --jours 7 --mcp "plugin:aoi-outils:aoi-rhino,plugin:aoi-outils:aoi-veille"
   ```
   Utilise `--jours N` si l'utilisateur précise une autre période. Le rapport compare les serveurs à `mcp-whitelist.txt` et les librairies Python à `whitelist.txt`.
3. Présente le résultat, en commençant par ce qui pose problème : **serveurs MCP non identifiés**, puis **librairies refusées**. Pour chaque librairie refusée, indique **quel script ou quelle commande** l'a demandée et **pour quel utilisateur**. Reste bref quand tout est conforme : une ligne suffit.
4. Pour une librairie refusée ou un serveur non identifié, **n'essaie jamais de contourner le refus** : pas de `-I`, `-S` ou `-E` pour désactiver le contrôle, pas de modification de `whitelist.txt` ou de `PYTHONPATH`, pas d'installation. Propose plutôt :
   - une solution qui n'utilise que des librairies acceptées ;
   - ou de demander à l'IT de valider la librairie, en donnant son nom d'import, son nom pip et l'usage prévu.
5. Si le journal est vide, vérifie que `PYTHONPATH` contient le dossier `guard` de cette skill. Sinon, le contrôle n'est pas actif : signale-le à l'utilisateur.

## Pour l'IT

- **Ajouter un serveur MCP** : l'inscrire dans `mcp-whitelist.txt`, puis créer une nouvelle étiquette du dépôt.
- **Ajouter une librairie** : l'inscrire dans `whitelist.txt` (nom d'import et nom pip en commentaire), puis créer une nouvelle étiquette du dépôt.
- **Mode d'essai** : `AOI_IMPORT_MODE=report` journalise sans refuser, ce qui permet de recenser les besoins avant d'activer le blocage.
- **Limite** : le contrôle ne vaut que pour les processus Python que lance Claude Code. Un Python lancé avec `-I`, `-S` ou `-E` l'ignore. C'est un garde-fou, pas une barrière : le refus d'installer des paquets reste assuré par les managed settings.
