# autocad

Serveur MCP qui permet à Claude de lire, nettoyer, modifier, tracer et exporter des dessins dans **AutoCAD 2027** (version complète, pas LT).

Le serveur est un add-in d'AutoCAD, développé à l'atelier dans `Documents\IT\autocad-mcp`. Il tourne dans AutoCAD et répond sur `http://127.0.0.1:1997/mcp`. Claude Code s'y connecte par l'entrée `autocad` de `.mcp.json` (type `http`). Il n'y a pas de programme à lancer à part.

| Fichier | Contenu |
|---|---|
| `addin.json` | la fiche de l'add-in : version, adresse de l'archive, empreinte SHA-256 |
| `LICENSE` | licence MIT de l'atelier |

L'add-in (bundle `aoi-autocad-mcp.bundle`) **n'est pas dans le plugin** : il est publié comme version GitHub du dépôt (`autocad-addin-<version>`), construite par `archives/construire.py` à partir de `archives/build/autocad-addin/` (non publié).

## Installation sur un poste

1. Ouvrez AutoCAD 2027 une première fois sur ce compte : le dossier `%APPDATA%\Autodesk\AutoCAD 2027` doit exister.
2. Fermez AutoCAD : il verrouille les fichiers de l'add-in.
3. Tapez `/aoi:regen` dans Claude Code. L'add-in est copié dans `%APPDATA%\Autodesk\ApplicationPlugins\aoi-autocad-mcp.bundle`.
4. Ouvrez AutoCAD. Au premier chargement, AutoCAD peut demander s'il faut charger l'add-in : choisissez « Toujours charger ».
5. Quittez et relancez Claude Code.

## Vérification

1. Dans AutoCAD, tapez `AOI_MCP_STATUS`. Résultat attendu : la version et l'adresse `http://127.0.0.1:1997/mcp`.
2. Dans Claude Code, tapez `/mcp`. Résultat attendu : `plugin:aoi:autocad` connecté.
3. Si AutoCAD était fermé au démarrage de Claude Code, ouvrez AutoCAD, puis tapez de nouveau `/mcp`.

## Ce que fait le serveur

37 outils : état et variables, entités, calques, blocs et attributs, styles, présentations, xrefs, purge, audit, tracé PDF, export DWG et DXF, lot sur un dossier (`batch_run`), AutoLISP et commandes AutoCAD.

- Une demande qui modifie le dessin s'annule par un seul `U` dans AutoCAD.
- Le serveur n'interrompt jamais votre commande : si AutoCAD est occupé, Claude reçoit « occupé ».
- Les fichiers ne sont lus et écrits que dans les dossiers autorisés (par défaut `Documents`). Rien n'est jamais écrasé.
- `batch_run` prépare un lot et donne la commande : c'est vous qui la lancez.

**Avertissement :** `execute_lisp` et `run_command` sont actifs par défaut. Ils permettent à Claude d'exécuter du code dans AutoCAD. Leurs filtres évitent des erreurs, mais ne sont pas une frontière de sécurité. Un texte placé dans un dessin reçu peut tenter de les faire appeler. Pour les fermer sur un poste, créez `%LOCALAPPDATA%\autocad-mcp\config.json` avec le contenu `{"enable_execute": false}`.

## Configuration

Fichier facultatif `%LOCALAPPDATA%\autocad-mcp\config.json` : `port` (1997), `allowed_folders` (dossiers autorisés, disque C: seulement), `output_folder` (sorties, sauvegardes et lots), `enable_execute`, `token`. Journal : `%LOCALAPPDATA%\autocad-mcp\serveur.log`.

## Pièges connus

- Le dossier `%USERPROFILE%\.dotnet` ne doit pas exister : sinon AutoCAD 2027 ne démarre pas sur un poste où la variable `DOTNET_ROOT` y pointe.
- AutoCAD verrouille l'add-in : `/aoi:regen` ne le met à jour que si AutoCAD est fermé.
