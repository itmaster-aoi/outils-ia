# revit

Serveur MCP qui permet à Claude de piloter Revit 2025 et d'en tenir un **graphe de connaissances (KG)**.

Il repose sur le projet [mcp-servers-for-revit](https://github.com/mcp-servers-for-revit/mcp-servers-for-revit), dans la version de l'atelier : la branche `kg-tools-vendoring` du fork [lfoletti/mcp-servers-for-revit](https://github.com/lfoletti/mcp-servers-for-revit), au commit `90eefab` (11.08.2026). Elle ajoute au projet d'origine les outils `kg_*`.

| Dossier | Contenu |
|---|---|
| `server/` | le serveur MCP compilé (`build/`, 55 outils, dont 28 `kg_*`), avec ses dépendances de production figées (`node_modules/`) |
| `addin/2025/` | l'add-in Revit 2025 : `mcp-servers-for-revit.addin` et le dossier `revit_mcp_plugin/` |
| `addin/2025/revit_mcp_plugin/Commands/RevitMCPCommandSet/` | le jeu de commandes d'origine (22 commandes) |
| `addin/2025/revit_mcp_plugin/Commands/RevitMCPCommandSet.KG/` | le jeu de commandes KG (28 commandes `kg_*`), avec le moteur BimKg (`BimKg.Core`, `BimKg.Runtime`) |
| `runtime/node.exe` | Node.js 25.8.2 officiel (nodejs.org), signé par l'OpenJS Foundation : rien à installer sur le poste |
| `LICENSE` | licence MIT du projet d'origine |
| `LICENSE-KG` | licence MIT de la partie KG (Lauro Foletti) |

## Installation sur un poste (une fois, par l'IT)

1. Rien à installer pour le serveur : Node.js 25.8.2 est fourni dans `runtime/`. C'est la version pour laquelle le module natif `better-sqlite3` est compilé.
2. **Add-in Revit** : copier le contenu de `addin/2025/` dans `%APPDATA%\Autodesk\Revit\Addins\2025\`, puis relancer Revit.
3. Le serveur MCP s'installe tout seul : Claude Code récupère le plugin `aoi` depuis le dépôt de l'atelier.

L'add-in autonome **BIM KG** (`BimKg.addin`) n'est pas nécessaire. Le jeu de commandes KG embarque son propre moteur et fonctionne seul. S'il trouve l'add-in BIM KG, il cohabite avec lui.

## Commandes activées dans Revit

Le registre (`revit_mcp_plugin/Commands/commandRegistry.json`) active **50 commandes** : 22 d'origine et 28 KG. Le jeu `RevitMCPCommandSet.Extended` du poste de référence n'est pas repris.

**L'exécution de code C# arbitraire reste désactivée.** La commande d'origine `send_code_to_revit`, qui fait exécuter dans Revit du code C# écrit par Claude, n'est pas inscrite au registre. L'outil serveur `revit_execute`, qui en est un alias, est donc sans effet. Pour l'activer, l'IT doit l'ajouter au registre en connaissance de cause.

## Vérification

Dans Claude Code, avec Revit ouvert : `/mcp` doit montrer `plugin:aoi:revit` connecté. Demander « dis bonjour dans Revit » doit afficher la boîte de dialogue `say_hello`, et `kg_session_info` doit répondre.

## Données locales

Le serveur crée un fichier `server/revit-data.db`, qui peut contenir des informations sur les maquettes. Ce fichier ne doit **jamais** être publié : il est exclu par le `.gitignore` du dépôt.

## Licences

- Projet d'origine : MIT (`LICENSE`).
- Outils et jeu de commandes KG : MIT, © 2026 Lauro Foletti (`LICENSE-KG`).
