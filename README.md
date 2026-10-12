# outils-ia : outils Claude Code de l'atelier

Ce dépôt est le **seul catalogue** de plugins autorisé dans Claude Code sur les postes de l'atelier. Il est imposé par les managed settings de l'organisation (`strictKnownMarketplaces`, figé sur une étiquette). Tout ce qui s'y trouve a été relu et validé par l'IT.

## Contenu

```
.claude-plugin/marketplace.json   catalogue « aoi »
plugins/aoi-outils/               le plugin de l'atelier
  .claude-plugin/plugin.json
  .mcp.json                       déclaration des serveurs MCP
  hooks/hooks.json                active le contrôle des imports Python à chaque session
  mcp/                            un dossier par serveur MCP, avec tout le nécessaire
    rhino/                          serveur, librairies figées, plugin Rhino, README
    revit/                          serveur compilé avec outils KG, dépendances figées, add-in Revit 2025, README
  skills/
    report/                       /report : contrôle et rapport des librairies Python
VERSIONS.md                       versions de référence validées
```

## Règles

- **Aucun secret** dans ce dépôt public : ni clé, ni mot de passe, ni configuration propre à un poste, ni donnée de projet.
- **Seule l'IT écrit** dans le dépôt. Chaque validation reçoit une étiquette datée (`2026-10-12`).
- **Pas de mise à jour automatique** : une nouvelle version d'un outil est relue, ajoutée, étiquetée, puis l'étiquette est mise à jour dans les managed settings.
- Les licences des projets d'origine sont conservées dans chaque dossier.

## Prérequis sur les postes (installés une fois par l'IT)

| Prérequis | Pour |
|---|---|
| Python 3.12 64 bits, chemin dans la variable `AOI_PYTHON` | `aoi-rhino`, `/report` |
| Git Bash (Git for Windows) | le hook de session qui active le contrôle des imports |
| Plugin Rhino : `mcp/rhino/addin/` copié dans `%APPDATA%\McNeel\Rhinoceros\packages\8.0\` | `aoi-rhino` |
| Node.js 25, chemin dans la variable `AOI_NODE` | `aoi-revit` |
| Add-in Revit : `mcp/revit/addin/2025/` copié dans `%APPDATA%\Autodesk\Revit\Addins\2025\` | `aoi-revit` |

## Consigne d'organisation

Les managed settings contiennent une clé `claudeMd` : à chaque session, Claude lance `/aoi-outils:report` au chargement des serveurs MCP et après chaque script Python, et ne contourne jamais le contrôle des librairies. Le texte exact figure dans l'annexe de la charte IA de l'atelier (`securite_ia.md`).

## Vérifier

```
claude plugin validate .
claude plugin validate ./plugins/aoi-outils
```
Puis, sur un poste, dans Claude Code : `/plugin` (catalogue `aoi`, plugin `aoi-outils`), `/mcp` (serveurs `plugin:aoi-outils:aoi-*`), `/report` (ou `/aoi-outils:report` si une autre commande porte déjà ce nom).
