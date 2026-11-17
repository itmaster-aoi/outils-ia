# illustrator

Serveur MCP qui permet à Claude de piloter Adobe Illustrator (fenêtre ouverte) par un panneau CEP (Common Extensibility Platform). Code repris tel quel de [lfoletti/illustrator-mcp](https://github.com/lfoletti/illustrator-mcp), étiquette `v0.1.0` (commit `c47f52f`) : voir `VERSION-AOI.txt`. Ne pas modifier ces fichiers à la main : les changements se font dans le projet d'origine.

| Dossier | Contenu |
|---|---|
| `illustratormcp/` | le serveur MCP `illustratormcp` 0.1.0 : 4 outils (`status`, `snapshot`, `batch`, `execute_script`) |
| `run.py` | le lanceur : il ajoute ce dossier au chemin de recherche |
| `addin/illustrator-mcp.claude-mcp/` | le panneau CEP « Claude MCP » 0.1.0 pour Illustrator, signé : panneau d'état et moteur ExtendScript de 26 commandes de lot |
| `addin.json` | la fiche de l'add-in, forme `source` : la mise à jour copie le panneau dans `%APPDATA%\Adobe\CEP\extensions`, si Illustrator 2026 a déjà été lancé sur ce compte (dossier `%APPDATA%\Adobe\Adobe Illustrator 30 Settings` présent) |
| `addin/installer.cmd` | pose à la main, en secours : copie le panneau pour l'utilisateur, sans droits administrateur |
| `addin/desinstaller.cmd` | retire le panneau |
| `LICENSE` | licence MIT du projet d'origine |

Librairies : aucune dans ce dossier. Le serveur utilise `mcp` 2.3.0 des librairies du Python AOI (`plugins/aoi/python-libs.json`). Le WebSocket est écrit avec la bibliothèque standard (`illustratormcp/ws.py`).

Le serveur tourne avec le **Python AOI** (`%LOCALAPPDATA%\aoi\python`), **sans** `-I -S`, comme le serveur indesign.

## Fonctionnement

```
Claude Code ⇄ serveur illustratormcp (stdio)
            ⇄ WebSocket 127.0.0.1:8766, messages JSON
            ⇄ panneau CEP « Claude MCP » dans Illustrator
            ⇄ moteur ExtendScript (moteur.jsx), par evalScript
```

Illustrator 2026 n'accepte pas de plugin UXP tiers : le panneau est donc une extension CEP. Le serveur écoute, et le panneau se connecte après un clic sur « Connecter ». Le panneau ne tente rien seul. Sans cette connexion, Claude ne peut rien lire ni modifier dans Illustrator.

## Signature du panneau

Illustrator charge une extension CEP seulement si elle est signée. Le dossier `addin/illustrator-mcp.claude-mcp` est signé : il contient `META-INF/signatures.xml`. Aucun réglage du poste n'est nécessaire, et le mode débogage de CEP (`PlayerDebugMode`) reste fermé.

- Toute modification d'un fichier de ce dossier annule la signature : Illustrator ne charge plus le panneau. `.gitattributes` marque ce dossier `-text` pour que git ne change pas les fins de ligne.
- Le certificat est auto-signé, sans horodatage. Il expire le 14.11.2036 : il faut signer de nouveau avant cette date.
- Le certificat et son mot de passe ne sont pas dans ce dépôt.

## Installation du panneau

La mise à jour (`upgrader-outils.cmd`) copie le panneau. Elle demande de fermer Illustrator, comme pour les autres add-ins.

1. Lancez `upgrader-outils.cmd`. Résultat attendu : « Illustrator : add-in recopié vers … ».
2. Ouvrez Illustrator, puis le menu Fenêtre > Extensions > Claude MCP.

Pose à la main, en secours : fermez Illustrator, puis lancez `addin\installer.cmd`.

## Utilisation

1. Ouvrez une session Claude Code. `/mcp` montre `plugin:aoi:illustrator`.
2. Dans Illustrator, cliquez sur « Connecter » dans le panneau Claude MCP. La pastille passe au vert.
3. L'outil `status` doit répondre `"connecte":true`.
4. La connexion se ferme avec la session Claude Code. Cliquez de nouveau sur « Connecter » dans la session suivante.

Méthode économe : un `snapshot`, puis un seul `batch`. Un lot fait une seule annulation (Ctrl+Z) dans Illustrator. `dry_run=true` vérifie un lot sans modifier le document.

Coordonnées : relatives au plan de travail, Y vers le bas, dans l'unité des règles du document.

Réglages :
- `execute_script` (ExtendScript) est refusé tant que la case « Autoriser les scripts ExtendScript (JSX) » du panneau n'est pas cochée.
- Chemins de fichiers : le serveur accepte le lecteur C: seulement. Il refuse les autres lecteurs et les chemins réseau `\\serveur\partage`, avant l'envoi au panneau. `ILLUSTRATOR_MCP_LECTEURS` (lettres acceptées, `C` par défaut) et `ILLUSTRATOR_MCP_UNC=1` changent cette règle ; `.mcp.json` ne les définit pas.
- Autres variables d'environnement : `ILLUSTRATOR_MCP_PORT` (8766), `ILLUSTRATOR_MCP_TIMEOUT` (60 s), `ILLUSTRATOR_MCP_LOG_LEVEL` (INFO).
- Le projet d'origine a un second canal, `ILLUSTRATOR_MCP_CANAL=com`, sans panneau. Il n'est pas utilisable ici : `.mcp.json` ne le règle pas, et `panneau/moteur.jsx` n'est pas repris.

## Limites connues

- Un seul serveur peut écouter sur le port 8766. Une deuxième session Claude Code ouverte en même temps n'a pas accès à Illustrator.
- Le panneau ne vérifie pas l'identité du programme qui écoute sur le port 8766.
- Vérifié avec Illustrator 30.8.2 seulement. La fiche de l'add-in vaut pour Illustrator 2026 (version 30) : une version 31 demande une seconde fiche.
- Un identifiant d'objet vaut pour la session : il change à la réouverture du document.
- Un script (`execute_script`) qui ferme un document juste après l'avoir modifié peut arrêter Illustrator.
- Adobe annonce la fin de CEP par défaut pour décembre 2028.

## Vérification

```
%LOCALAPPDATA%\aoi\python\python.exe run.py --check
```
La commande doit afficher 4 outils et un chemin `illustratormcp` qui pointe dans le plugin.

## Licence

MIT (`LICENSE`). Projet sans lien avec Adobe.
