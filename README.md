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
  skills/
    report/                       /report : contrôle et rapport des librairies Python
    regen/                        /regen : met le poste à la version imposée par la console
VERSIONS.md                       versions de référence validées
```

## Règles

- **Aucun secret** dans ce dépôt public : ni clé, ni mot de passe, ni configuration propre à un poste, ni donnée de projet.
- **Seule l'IT écrit** dans le dépôt. Chaque validation reçoit une étiquette datée (`2026-10-12`).
- **Pas de mise à jour automatique** : une nouvelle version d'un outil est relue, ajoutée, étiquetée, puis l'étiquette est mise à jour dans les managed settings. Augmenter aussi la version de `plugin.json`, sinon les postes ne voient pas la mise à jour.
- **Sur les postes**, `/regen` dans Claude Code récupère la nouvelle version (catalogue, plugin, add-ins), sans relancer `installer-poste.ps1`. L'installeur reste nécessaire pour un poste neuf.
- Les licences des projets d'origine sont conservées dans chaque dossier.

## Préparer un poste

Copier [`installer-poste.ps1`](installer-poste.ps1) et [`installer-poste.cmd`](installer-poste.cmd) dans un même dossier, puis **double-cliquer sur `installer-poste.cmd`**, sans élévation, une fois par utilisateur et par poste. Le lanceur contourne la politique d'exécution de PowerShell pour cette seule exécution. Pour un script téléchargé depuis GitHub, lever d'abord la marque « Internet » : `Unblock-File .\installer-poste.ps1`.

En ligne de commande :

```powershell
powershell -ExecutionPolicy Bypass -File .\installer-poste.ps1 -DryRun   # diagnostic seul, ne modifie rien
powershell -ExecutionPolicy Bypass -File .\installer-poste.ps1           # installation
```

Le script installe ou vérifie Git for Windows et Claude Code, signale une éventuelle clé `ANTHROPIC_API_KEY`, enregistre le jeton de veille **s'il y en a un** (facultatif ; `plugin:aoi:veille` est retiré du plugin pour l'instant, le jeton servira à son retour ; option `-SansVeille` pour ne pas être interrogé), retire les anciennes déclarations MCP, installe ou met à jour le plugin `aoi` et copie les add-ins Rhino et Revit (en sauvegardant le registre de commandes Revit existant). Il termine par un bilan. Il est rejouable sans risque.

## Prérequis sur les postes (installés une fois par l'IT)

Python 3.12 et Node.js 25 sont fournis par l'atelier : le **Python AOI** et le **Node AOI** sont des archives publiées à part (versions GitHub `python-aoi-*` et `node-aoi-*`), installées dans `%LOCALAPPDATA%\aoi` par l'installeur ou `/regen`, et retéléchargées seulement quand leur version change. Le petit Python de `skills/report/runtime/` sert à `/report` et `/regen`.

| Prérequis | Pour |
|---|---|
| Git for Windows, installable sans élévation : `winget install --id Git.Git -e --scope user`. Sur un poste sans winget, l'installeur l'installe pour l'utilisateur depuis les versions officielles de [microsoft/winget-cli](https://github.com/microsoft/winget-cli/releases) | récupérer ce dépôt, et Git Bash pour le hook qui active le contrôle des imports |
| Plugin Rhino : `mcp/rhino/addin/` copié dans `%APPDATA%\McNeel\Rhinoceros\packages\8.0\` | `rhino` |
| *Facultatif* : jeton d'accès personnel au service de veille, dans la variable `AOI_VEILLE_TOKEN` (jamais dans ce dépôt), pour les personnes qui y ont accès | `plugin:aoi:veille` (retiré du plugin pour l'instant, depuis 2026.10.13.8) |
| Add-in Revit : `mcp/revit/addin/2025/` copié dans `%APPDATA%\Autodesk\Revit\Addins\2025\` | `revit` |

## Consigne d'organisation

Les managed settings contiennent une clé `claudeMd` : à chaque session, Claude lance `/aoi:report` au chargement des serveurs MCP et après chaque script Python, et ne contourne jamais le contrôle des librairies. Le texte exact figure dans l'annexe de la charte IA de l'atelier (`securite_ia.md`).

## Vérifier

```
claude plugin validate .
claude plugin validate ./plugins/aoi
```
Puis, sur un poste, dans Claude Code : `/plugin` (catalogue `aoi`, plugin `aoi`), `/mcp` (serveurs `plugin:aoi:*`), `/report` (ou `/aoi:report` si une autre commande porte déjà ce nom).
