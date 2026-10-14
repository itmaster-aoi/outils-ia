# Journal des changements

Une entrée par étiquette du dépôt, la plus récente en haut. L'étiquette est celle que la console impose aux postes (`extraKnownMarketplaces` et `strictKnownMarketplaces`) ; les postes la récupèrent avec `/regen`. Les versions de chaque composant sont dans [`VERSIONS.md`](VERSIONS.md), le détail dans les messages de commit.

À chaque nouvelle étiquette : ajouter son entrée ici, dans le même commit que le changement de version de `plugins/aoi/.claude-plugin/plugin.json`. À chaque modification de `installer-poste.ps1` : changer `$VersionInstalleur` (date du jour), sinon les copies dépassées ne sont pas signalées.

## Installeur 2026-10-14 (branche main, hors étiquette)

- `installer-poste.ps1` compare sa version (`$VersionInstalleur`) à celle du dépôt et avertit si la copie lancée est dépassée, par exemple sur un partage réseau oublié. La personne choisit de continuer ou non. Les copies antérieures à cette version n'ont pas ce contrôle.

## 2026-10-14.1 (plugin 2026.10.14.1)

- **Revit** : `send_code_to_revit` est activée par défaut. Claude peut faire exécuter du code C# dans Revit ; l'outil `revit_execute`, son alias, devient effectif. Add-in `revit-addin-2026-10-14` (51 commandes : 23 d'origine et 28 KG).
- **Installeur** : sur un poste sans winget, App Installer est réenregistré pour l'utilisateur, ou installé depuis les versions officielles de [microsoft/winget-cli](https://github.com/microsoft/winget-cli/releases), sans élévation, avant l'installation de Git.

## 2026-10-13.8 (plugin 2026.10.13.8)

- Serveur `plugin:aoi:veille` retiré pour l'instant (déclaration à reprendre de l'étiquette `2026-10-13.7`). Le jeton `AOI_VEILLE_TOKEN` est gardé.
- Ligne de démarrage : un outil retiré s'affiche « outils retirés : … ».

## 2026-10-13.7 (plugin 2026.10.13.7)

- Ligne de démarrage : « Outils IA atelier oï, v<version> : … · vos librairies sont à jour ».

## 2026-10-13.6 (plugin 2026.10.13.6)

- Ligne de démarrage : un simple changement de version ne s'affiche plus comme « nouveaux outils : » suivi de rien.

## 2026-10-13.5 (plugin 2026.10.13.5)

- Au démarrage de chaque session, une ligne de bilan : version, serveurs, Python AOI, mises à jour disponibles, alerte si le contrôle des imports est inactif (trace dans `%LOCALAPPDATA%\aoi\demarrage.log`).
- Le crochet de démarrage ne lance plus de `claude` imbriqué, qui pouvait bloquer le démarrage.

## 2026-10-13.4 (plugin 2026.10.13.4)

- Serveur MCP Revit (`revit-server-2026-10-12`) et add-in Rhino (`rhino-addin-2026-10-12`) publiés à part. Plugin ramené à 56 Mo.
- `revit-data.db` (graphe de connaissances) est repris d'une version du serveur à l'autre ; auparavant il était effacé à chaque mise à jour.
- `archives/construire.py` construit toutes les archives publiées à part.

## 2026-10-13.3 (plugin 2026.10.13.3)

- Add-in Revit 2025 publié à part (`revit-addin-2026-10-12`), téléchargé seulement si sa version manque, refusé si son empreinte diffère. Plugin : 185 → 93 Mo.
- Rapport des nouveautés au démarrage de la session.
- `/regen` efface les anciennes versions du plugin gardées dans le cache.

## 2026-10-13.2 (plugin 2026.10.13.2)

- `/regen` relit les règles de la console sans redémarrer la session et signale les nouvelles skills.

## 2026-10-13.1 (plugin 2026.10.13.1)

- Nouvelle skill `/aoi:adhd` (copie relue de UditAkhourii/adhd, sans la partie `npm install -g`).
- Installeur : bilan en étape « 8. Bilan ».

## 2026-10-12.13 (plugin 2026.10.12.13)

- Node AOI (Node.js 25.8.2) publié à part, installé dans `%LOCALAPPDATA%\aoi\node` ; le serveur Revit l'utilise.
- Installeur : affichage dans le style de la toolbox AOI.

## 2026-10-12.12 (plugin 2026.10.12.12)

- Python AOI : Python 3.12.10 portable avec les paquets de la liste blanche, publié à part, installé dans `%LOCALAPPDATA%\aoi\python` ; le serveur Rhino l'utilise.
- Liste blanche : `pymupdf`/`fitz`, `sklearn`, `skimage`.
- Installeur : roue animée pendant les opérations longues.

## 2026-10-12.11 (plugin 2026.10.12.11)

- Skills lisibles sur les postes (`*.md` en fins de ligne LF) : `/aoi:report` et `/regen` n'apparaissaient pas.
- Contrôle des imports compatible avec Python < 3.10 ; avant, il plantait et laissait tout passer.

## 2026-10-12.10 (plugin 2026.10.12.10)

- `/regen` de nouveau exécutable (inutilisable depuis 2026.10.12.8).

## 2026-10-12.9 (plugin 2026.10.12.9)

- Chemin `C:\ProgramData\aoi\guard` rétabli dans `/report` et l'installeur.
- Installeur : fin d'une récursion infinie à l'étape 6.

## 2026-10-12.8 (plugin 2026.10.12.8)

- Contrôle des imports actif aussi dans PowerShell : la console impose `PYTHONPATH=C:\ProgramData\aoi\guard`.

## 2026-10-12.7 (plugin 2026.10.12.7)

- `SKILL.md` de `/regen` lisible. **Ne pas utiliser l'étiquette `2026-10-12.6`.**

## 2026-10-12.6 (plugin 2026.10.12.6)

- `/regen` et l'installeur réinstallent le plugin après le retrait du catalogue.

## 2026-10-12.5 (plugin 2026.10.12.5)

- Nouvelle skill `/regen` : aligne le poste sur l'étiquette imposée par la console et recopie les add-ins qui ont changé.
- Installeur : jeton de veille facultatif (`-SansVeille`).

## 2026-10-12.4

- Plugin renommé `aoi` : serveurs `plugin:aoi:rhino`, `plugin:aoi:revit`, `plugin:aoi:veille`.
- Nouvel installeur `installer-poste.cmd` / `installer-poste.ps1` : préparation d'un poste sans élévation.

## 2026-10-12.3

- Python et Node.js embarqués dans le plugin : plus besoin de les installer sur les postes.

## 2026-10-12.2

- Jeton du service de veille lu dans `AOI_VEILLE_TOKEN`.

## 2026-10-12.1

- Licence MIT de la partie KG du serveur Revit.

## 2026-10-12

- Première version : catalogue `aoi`, plugin `aoi-outils` avec les serveurs Rhino (rhinomcp 0.3.2), Revit (avec les outils KG ; exécution de code C# désactivée) et veille, skill `/report` (contrôle des imports Python par liste blanche).
