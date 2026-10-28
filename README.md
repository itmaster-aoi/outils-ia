# outils-ia : outils Claude Code

Ce dépôt est le **seul catalogue** de plugins autorisé dans Claude Code sur les postes de l'atelier. Il est imposé par les managed settings de l'organisation (`strictKnownMarketplaces`, figé sur une étiquette). Tout ce qui s'y trouve a été relu et validé par l'IT.

## Contenu

```
.claude-plugin/marketplace.json   catalogue « aoi »
plugins/aoi/               le plugin de l'atelier
  .claude-plugin/plugin.json
  .mcp.json                       déclaration des serveurs MCP
  mcp/                            un dossier par serveur MCP, avec tout le nécessaire
    rhino/                          serveur, librairies figées, plugin Rhino, README
    revit/                          serveur compilé avec outils KG, dépendances figées, add-in Revit 2025, README
    keyshot/                        serveur et pont KeyShot (lfoletti/keyshot-mcp), librairies figées, README
    cortexdb/                       licence, README et provenance de cortexdb (binaire publié à part, archive cortexdb-server)
    autocad/                        fiche, README et licence de l'add-in AutoCAD 2027, qui est le serveur (archive autocad-addin)
  commands/                       /aoi:remember et /aoi:recall (cortexdb, importées par amont/importer_cortexdb.py)
  controle/                       contrôle des imports Python (guard, liste blanche) et Python embarqué
  skills/
    regen/scripts/                maj.py, moteur de la mise à jour (ancienne skill /regen, chemin conservé)
    cortexdb/                     /cortexdb : mémoire durable de l'utilisateur (skill de l'atelier, serveur cortexdb)
    graphify/                     /graphify : graphe de connaissances d'un dossier (Graphify-Labs/graphify, Python AOI), généré par python-aoi/adapter_skill_graphify.py
  output-styles/
    ste.md                        style de sortie aoi:ste : rédaction technique simplifiée (ASD-STE100)
amont/importer_keyshot.py         importe une étiquette de lfoletti/keyshot-mcp (clone fait hors de Claude Code) dans mcp/keyshot
amont/importer_autocad.py         importe une étiquette de lfoletti/autocad-mcp (clone fait hors de Claude Code) dans mcp/autocad et vérifie le commit des DLL de l'archive
amont/importer_cortexdb.py        importe /remember et /recall d'une étiquette de itmaster-aoi/cortexdb (clone fait hors de Claude Code)
tests/                            tests du plugin sur un poste simulé (dossiers, messages)
docs/upgrader-outils.md           mise à jour des postes : ce que maj.py fournit à upgrader-outils.cmd
VERSIONS.md                       versions de référence validées
CHANGELOG.md                      journal des changements, une entrée par étiquette
```

## Règles

- **Aucun secret** dans ce dépôt public : ni clé, ni mot de passe, ni configuration propre à un poste, ni donnée de projet.
- **Seule l'IT écrit** dans le dépôt. Chaque validation reçoit une étiquette datée (`2026-10-12`).
- **Pas de mise à jour automatique** : une nouvelle version d'un outil est relue, ajoutée, étiquetée, puis l'étiquette est mise à jour dans les managed settings. Augmenter aussi la version de `plugin.json`, sinon les postes ne voient pas la mise à jour.
- **Sur les postes**, `upgrader-outils.cmd`, lancé Claude Code fermé, récupère la nouvelle version (catalogue, plugin, add-ins), sans relancer l'installeur. L'installeur reste nécessaire pour un poste neuf. Voir [`docs/upgrader-outils.md`](docs/upgrader-outils.md).
- Les licences des projets d'origine sont conservées dans chaque dossier.

## Préparer un poste

Les scripts des postes (`installer-poste.cmd`, `installer-claude.cmd`, `upgrader-outils.cmd`) ne sont pas dans ce dépôt public depuis le 28.10.2026. L'IT les tient dans un dépôt interne, non publié, et les copie sur le partage de l'atelier. Lancer `installer-poste.cmd` par un double-clic, sans élévation, une fois par utilisateur et par poste.

`installer-claude.cmd` installe Claude Code s'il manque, ajoute `%USERPROFILE%\.local\bin` en tête du PATH du compte (registre `HKCU\Environment`), puis vérifie que `claude` désigne bien ce fichier dans un nouveau terminal. `installer-poste.cmd` l'appelle à son étape 2.

L'installeur installe ou vérifie Git for Windows et Claude Code, signale une éventuelle clé `ANTHROPIC_API_KEY`, ouvre la connexion à claude.ai à la première fois, retire les anciennes déclarations MCP, installe ou met à jour le plugin `aoi` et copie les add-ins Rhino et Revit (en sauvegardant le registre de commandes Revit existant). Il termine par un bilan. Il est rejouable sans risque.

## Prérequis sur les postes (installés une fois par l'IT)

Python 3.12 et Node.js 25 sont fournis par l'atelier : le **Python AOI** et le **Node AOI** sont des archives publiées à part (versions GitHub `python-aoi-*` et `node-aoi-*`), installées dans `%LOCALAPPDATA%\aoi` par l'installeur ou `/regen`, et retéléchargées seulement quand leur version change. Une librairie s'ajoute au Python AOI sans le reconstruire : une ligne dans `python-aoi/ajouts.txt`, puis `python-aoi/verrouiller.py` (hors de Claude Code) inscrit ses roues et leurs empreintes dans `plugins/aoi/python-libs.json` ; les postes les installent dans `%LOCALAPPDATA%\aoi\python-libs-<version>` au prochain `/regen`. Le petit Python de `controle/runtime/` sert au crochet de démarrage, à `/regen` et à l'installeur.

| Prérequis | Pour |
|---|---|
| Git for Windows, installable sans élévation : `winget install --id Git.Git -e --scope user`. Sur un poste sans winget, l'installeur l'installe pour l'utilisateur depuis les versions officielles de [microsoft/winget-cli](https://github.com/microsoft/winget-cli/releases) | récupérer ce dépôt, et Git Bash pour le hook qui active le contrôle des imports |
| Plugin Rhino : `mcp/rhino/addin/` copié dans `%APPDATA%\McNeel\Rhinoceros\packages\8.0\` | `rhino` |
| Add-in Revit : `mcp/revit/addin/2025/` copié dans `%APPDATA%\Autodesk\Revit\Addins\2025\` | `revit` |

## Consigne d'organisation

Les managed settings contiennent une clé `claudeMd` : Claude ne contourne jamais le contrôle des librairies. Le texte exact figure dans l'annexe de la charte IA de l'atelier (`securite_ia.md`).

## Vérifier

```
claude plugin validate .
claude plugin validate ./plugins/aoi
```
Puis, sur un poste, dans Claude Code : `/plugin` (catalogue `aoi`, plugin `aoi`), `/mcp` (serveurs `plugin:aoi:*`).
