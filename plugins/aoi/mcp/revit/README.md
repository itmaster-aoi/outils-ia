# revit

Serveur MCP qui permet à Claude de piloter Revit 2025 et d'en tenir un **graphe de connaissances (KG)**.

Il repose sur le projet [mcp-servers-for-revit](https://github.com/mcp-servers-for-revit/mcp-servers-for-revit), dans la version de l'atelier : la branche `kg-tools-vendoring` du fork [lfoletti/mcp-servers-for-revit](https://github.com/lfoletti/mcp-servers-for-revit), au commit `90eefab` (11.08.2026). Elle ajoute au projet d'origine les outils `kg_*`.

| Dossier | Contenu |
|---|---|
| `../../revit-server-aoi.json` | la fiche du serveur MCP compilé (`build/`, 55 outils, dont 28 `kg_*`, avec ses dépendances de production figées `node_modules/`) : version, adresse de l'archive, empreinte SHA-256 |
| `addin.json` | la fiche de l'add-in Revit 2025 : version, adresse de l'archive, empreinte SHA-256 |

Le serveur (environ 26 Mo) et l'add-in (environ 90 Mo) **ne sont plus dans le plugin** : ils sont publiés comme versions GitHub du dépôt (`revit-server-<version>`, `revit-addin-<version>`), construites par `archives/construire.py` à partir de `archives/build/` (non publié). Le serveur s'installe dans `%LOCALAPPDATA%\aoi\revit-server-<version>`, la version que désigne `.mcp.json`. L'archive de l'add-in contient `mcp-servers-for-revit.addin` et le dossier `revit_mcp_plugin/`, avec le jeu de commandes d'origine (`Commands/RevitMCPCommandSet/`, 22 commandes) et le jeu KG (`Commands/RevitMCPCommandSet.KG/`, 28 commandes `kg_*`, avec le moteur BimKg).
| `LICENSE` | licence MIT du projet d'origine |
| `LICENSE-KG` | licence MIT de la partie KG (Lauro Foletti) |

## Installation sur un poste (une fois, par l'IT)

1. Node : le **Node AOI** (Node.js 25.8.2, `%LOCALAPPDATA%\aoi\node`), publié à part et installé par `installer-poste.cmd` ou `/regen`. C'est la version pour laquelle le module natif `better-sqlite3` est compilé : changer de version de Node impose de recompiler le serveur.
2. **Add-in Revit** : `installer-poste.cmd` ou `/regen` téléchargent l'archive (seulement si sa version manque sur le poste, dans `%LOCALAPPDATA%\aoi\addins`), vérifient son empreinte et la copient dans `%APPDATA%\Autodesk\Revit\Addins\2025\`, Revit fermé. Relancer ensuite Revit.
3. **Serveur MCP** : `installer-poste.cmd` ou `/regen` téléchargent l'archive de la version validée (seulement si elle manque), vérifient son empreinte et l'installent à côté des versions précédentes, ce qui permet de mettre à jour pendant qu'une session utilise l'ancienne. Les anciennes versions sont effacées dès qu'elles ne servent plus.

L'add-in autonome **BIM KG** (`BimKg.addin`) n'est pas nécessaire. Le jeu de commandes KG embarque son propre moteur et fonctionne seul. S'il trouve l'add-in BIM KG, il cohabite avec lui.

## Commandes activées dans Revit

Le registre (`revit_mcp_plugin/Commands/commandRegistry.json`) active **50 commandes** : 22 d'origine et 28 KG. Le jeu `RevitMCPCommandSet.Extended` du poste de référence n'est pas repris.

**L'exécution de code C# arbitraire reste désactivée.** La commande d'origine `send_code_to_revit`, qui fait exécuter dans Revit du code C# écrit par Claude, n'est pas inscrite au registre. L'outil serveur `revit_execute`, qui en est un alias, est donc sans effet. Pour l'activer, l'IT doit l'ajouter au registre en connaissance de cause.

## Vérification

Dans Claude Code, avec Revit ouvert : `/mcp` doit montrer `plugin:aoi:revit` connecté. Demander « dis bonjour dans Revit » doit afficher la boîte de dialogue `say_hello`, et `kg_session_info` doit répondre.

## Données locales

Le serveur crée un fichier `revit-data.db` dans son dossier (`%LOCALAPPDATA%\aoi\revit-server-<version>`), qui peut contenir des informations sur les maquettes (graphe de connaissances). À chaque nouvelle version du serveur, ce fichier est **repris** de la version précédente (`conserver` dans la fiche). Auparavant, il était dans le cache du plugin et disparaissait à chaque mise à jour. Ce fichier ne doit **jamais** être publié : `archives/construire.py` exclut les `*.db` et le `.gitignore` aussi.

## Licences

- Projet d'origine : MIT (`LICENSE`).
- Outils et jeu de commandes KG : MIT, © 2026 Lauro Foletti (`LICENSE-KG`).
