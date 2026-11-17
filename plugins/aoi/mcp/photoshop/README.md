# photoshop

Serveur MCP qui permet à Claude de piloter Adobe Photoshop (fenêtre ouverte) par un plugin UXP (Unified Extensibility Platform). Code repris tel quel de [lfoletti/photoshop-mcp](https://github.com/lfoletti/photoshop-mcp), étiquette `v0.1.0` (commit `ec99ff5`) : voir `VERSION-AOI.txt`. Ne pas modifier ces fichiers à la main : les changements se font dans le projet d'origine.

| Dossier | Contenu |
|---|---|
| `photoshopmcp/` | le serveur MCP `photoshopmcp` 0.1.0 : 4 outils (`status`, `snapshot`, `batch`, `execute_script`) |
| `run.py` | le lanceur : il ajoute ce dossier au chemin de recherche |
| `addin/photoshop-mcp.claude-mcp_PS.ccx` | le plugin UXP « Claude MCP Photoshop » 0.1.0 pour Photoshop : panneau d'état « Claude MCP » et 27 commandes de lot |
| `addin.json` | la fiche de l'add-in, forme `uxp` : la mise à jour pose le plugin UXP par l'installateur d'Adobe, si Photoshop est installé sur ce compte (dossier `%APPDATA%\Adobe\UXP\PluginsStorage\PHSP` présent) |
| `addin/installer.cmd` | pose à la main, en secours : installe le plugin UXP pour l'utilisateur, sans droits administrateur |
| `addin/desinstaller.cmd` | retire le plugin UXP |
| `LICENSE` | licence MIT du projet d'origine |

Librairies : aucune dans ce dossier. Le serveur utilise `mcp` 2.3.0 des librairies du Python AOI (`plugins/aoi/python-libs.json`). Le WebSocket est écrit avec la bibliothèque standard (`photoshopmcp/ws.py`).

Le serveur tourne avec le **Python AOI** (`%LOCALAPPDATA%\aoi\python`), **sans** `-I -S`, comme les serveurs indesign et illustrator.

## Fonctionnement

```
Claude Code ⇄ serveur photoshopmcp (stdio)
            ⇄ WebSocket 127.0.0.1:8767, messages JSON
            ⇄ plugin UXP « Claude MCP Photoshop » dans Photoshop
```

Un plugin UXP ne peut pas écouter sur un port. Le serveur écoute donc, et le plugin se connecte après un clic sur « Connecter ». Le plugin ne tente rien seul.

Le plugin s'appelle « Claude MCP Photoshop » et non « Claude MCP » : l'installateur d'Adobe retire un plugin par son nom, et le plugin d'InDesign porte déjà le nom « Claude MCP ». Le panneau garde le titre « Claude MCP ».

## Installation du plugin UXP

La mise à jour (`upgrader-outils.cmd`) pose le plugin UXP. Elle demande de fermer Photoshop, comme pour les autres add-ins.

1. Lancez `upgrader-outils.cmd`. Résultat attendu : « Photoshop : plugin UXP 0.1.0 posé ».
2. Ouvrez Photoshop, puis le menu Modules externes > Claude MCP Photoshop > Claude MCP.

`maj.py` lance l'installateur de plugins d'Adobe (`UnifiedPluginInstallerAgent.exe`) avec les droits de l'utilisateur, sans élévation. L'installateur écrit dans `%APPDATA%\Adobe\UXP\Plugins\External` et dans `%APPDATA%\Adobe\UXP\PluginsInfo\v1\PS.json`. Creative Cloud doit être installé sur le poste. Le mode développeur de Photoshop n'est pas nécessaire.

Cette étape ne bloque jamais la mise à jour. Un échec s'affiche en clair, avec la mention « ÉCHEC NON BLOQUANT » et son motif. La mise à jour continue, et la pose est retentée à la mise à jour suivante. Si Photoshop reste ouvert, la pose est remise sans échec. Un Photoshop plus ancien que la version 25 refuse le plugin : l'échec est affiché de la même façon.

Pose à la main, en secours : fermez Photoshop, puis lancez `addin\installer.cmd`.

## Utilisation

1. Ouvrez une session Claude Code. `/mcp` montre `plugin:aoi:photoshop`.
2. Dans Photoshop, cliquez sur « Connecter » dans le panneau Claude MCP. La pastille passe au vert.
3. L'outil `status` doit répondre `"connecte":true`.
4. La connexion se ferme avec la session Claude Code. Cliquez de nouveau sur « Connecter » dans la session suivante.

Méthode économe : un `snapshot`, puis un seul `batch`. Un lot fait une seule étape d'historique (Ctrl+Z) dans Photoshop. `dry_run=true` vérifie un lot sans modifier le document. Toutes les mesures sont en pixels.

Réglages :
- `execute_script` (JavaScript UXP) est refusé tant que la case « Autoriser les scripts JavaScript (UXP) » du panneau n'est pas cochée. La case est décochée à la pose.
- `close_document` exige le paramètre `save` (`true` ou `false`) : une fermeture sans enregistrement n'est jamais implicite.
- Chemins de fichiers : le serveur accepte le lecteur C: seulement. Il refuse les autres lecteurs et les chemins réseau `\\serveur\partage`, avant l'envoi au plugin. `PHOTOSHOP_MCP_LECTEURS` (lettres acceptées, `C` par défaut) et `PHOTOSHOP_MCP_UNC=1` changent cette règle ; `.mcp.json` ne les définit pas.
- Autres variables d'environnement : `PHOTOSHOP_MCP_PORT` (8767), `PHOTOSHOP_MCP_TIMEOUT` (60 s), `PHOTOSHOP_MCP_LOG_LEVEL` (INFO).

## Limites connues

- Un seul serveur peut écouter sur le port 8767. Une deuxième session Claude Code ouverte en même temps n'a pas accès à Photoshop.
- Le plugin ne vérifie pas l'identité du programme qui écoute sur le port 8767.
- Si Photoshop affiche une boîte de dialogue ou si un outil est en cours, une commande rend l'erreur `occupe`.
- Vérifié avec Photoshop 28.0 seulement. Le manifeste accepte Photoshop 25 et suivants.
- Défaut vu une fois, non reproduit : dans la première session de Photoshop après son installation, le panneau n'a plus réagi aux clics. Un redémarrage de Photoshop l'a levé. Cause inconnue.

## Vérification

```
%LOCALAPPDATA%\aoi\python\python.exe run.py --check
```
La commande doit afficher 4 outils et un chemin `photoshopmcp` qui pointe dans le plugin.

## Licence

MIT (`LICENSE`). Projet sans lien avec Adobe.
