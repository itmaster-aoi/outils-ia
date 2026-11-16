# indesign

Serveur MCP qui permet à Claude de piloter Adobe InDesign (fenêtre ouverte) par un plugin UXP (Unified Extensibility Platform). Code repris tel quel du projet `indesign-mcp`, commit `138b31d` : voir `VERSION-AOI.txt`. Ne pas modifier ces fichiers à la main : les changements se font dans le projet d'origine.

| Dossier | Contenu |
|---|---|
| `indesignmcp/` | le serveur MCP `indesignmcp` 0.1.0 : 4 outils (`status`, `snapshot`, `batch`, `execute_script`) |
| `run.py` | le lanceur : il ajoute ce dossier au chemin de recherche |
| `addin/indesign-mcp.claude-mcp_ID.ccx` | le plugin UXP « Claude MCP » 0.1.0 pour InDesign : panneau d'état et 18 commandes de lot |
| `addin/installer.cmd` | installe le plugin UXP pour l'utilisateur, sans droits administrateur |
| `addin/desinstaller.cmd` | retire le plugin UXP |

Librairies : aucune dans ce dossier. Le serveur utilise `mcp` 2.3.0 des librairies du Python AOI (`plugins/aoi/python-libs.json`). Le WebSocket est écrit avec la bibliothèque standard (`indesignmcp/ws.py`).

Le serveur tourne avec le **Python AOI** (`%LOCALAPPDATA%\aoi\python`), **sans** `-I -S` : il a besoin des librairies du Python AOI. C'est la différence avec les serveurs rhino et keyshot, qui embarquent `mcp` 1.28.1 dans `libs/`.

## Fonctionnement

```
Claude Code ⇄ serveur indesignmcp (stdio)
            ⇄ WebSocket 127.0.0.1:8765, messages JSON
            ⇄ plugin UXP « Claude MCP » dans InDesign
```

Un plugin UXP ne peut pas écouter sur un port. Le serveur écoute donc, et le plugin se connecte après un clic sur « Connecter ». Le plugin ne tente rien seul.

## Installation du plugin UXP

La mise à jour du plugin `aoi` ne pose pas le plugin UXP dans InDesign : il n'y a pas de fiche `addin.json`. L'installation se fait une fois par poste et par utilisateur.

1. Fermez InDesign.
2. Lancez `addin\installer.cmd`. Résultat attendu : « Installation Successful », sans demande d'élévation.
3. Ouvrez InDesign, puis le menu Fenêtre > Modules externes > Claude MCP.

`installer.cmd` lance l'installateur de plugins d'Adobe (`UnifiedPluginInstallerAgent.exe`) avec les droits de l'utilisateur. L'installateur écrit dans `%APPDATA%\Adobe\UXP\Plugins\External` et dans `%APPDATA%\Adobe\UXP\PluginsInfo\v1\ID.json`. Creative Cloud doit être installé sur le poste.

## Utilisation

1. Ouvrez une session Claude Code. `/mcp` montre `plugin:aoi:indesign`.
2. Dans InDesign, cliquez sur « Connecter » dans le panneau Claude MCP. La pastille passe au vert.
3. L'outil `status` doit répondre `"connecte":true`.
4. La connexion se ferme avec la session Claude Code. Cliquez de nouveau sur « Connecter » dans la session suivante.

Méthode économe : un `snapshot`, puis un seul `batch`. Un lot fait une seule annulation (Ctrl+Z) dans InDesign. `dry_run=true` vérifie un lot sans modifier le document.

Réglages :
- `execute_script` (ExtendScript) est refusé tant que la case « Autoriser les scripts ExtendScript (JSX) » du panneau n'est pas cochée.
- Chemins de fichiers : le serveur accepte le lecteur C: seulement. Il refuse les autres lecteurs et les chemins réseau `\\serveur\partage`, avant l'envoi au plugin. `INDESIGN_MCP_LECTEURS` (lettres acceptées, `C` par défaut) et `INDESIGN_MCP_UNC=1` changent cette règle ; `.mcp.json` ne les définit pas.
- Autres variables d'environnement : `INDESIGN_MCP_PORT` (8765), `INDESIGN_MCP_TIMEOUT` (60 s), `INDESIGN_MCP_LOG_LEVEL` (INFO).

## Limites connues

- Un seul serveur peut écouter sur le port 8765. Une deuxième session Claude Code ouverte en même temps n'a pas accès à InDesign.
- Le plugin ne vérifie pas l'identité du programme qui écoute sur le port 8765.
- Vérifié avec InDesign 21.6 seulement. Le manifeste accepte InDesign 18.5 et suivants.

## Vérification

```
%LOCALAPPDATA%\aoi\python\python.exe run.py --check
```
La commande doit afficher 4 outils et un chemin `indesignmcp` qui pointe dans le plugin.

## Licence

Le projet d'origine n'a pas encore de fichier de licence. À ajouter avant sa publication.
