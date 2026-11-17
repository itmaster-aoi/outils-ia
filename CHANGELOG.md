# Journal des changements

## 2026-11-17.2 (plugin 2026.11.17.2)

Serveur MCP `photoshop` : Claude pilote Adobe Photoshop par un plugin UXP. Le serveur a 4 outils (`status`, `snapshot`, `batch`, `execute_script`) et 27 commandes de lot, en pixels. Un lot forme une seule étape d'historique. Il tourne avec le Python AOI, sans `-I -S` et sans dossier `libs/`, comme les serveurs `indesign` et `illustrator`. La mise à jour pose le plugin UXP « Claude MCP Photoshop » par l'installateur d'Adobe, si Photoshop est installé sur le compte. Nouvelle fiche `mcp/photoshop/addin.json`, forme `uxp` ; `maj.py` ne change pas. Le mode développeur de Photoshop n'est pas nécessaire. Le panneau se connecte seulement après un clic sur « Connecter ». `execute_script` exécute du JavaScript UXP ; il reste fermé tant que la case du panneau n'est pas cochée. Origine : `lfoletti/photoshop-mcp` `v0.1.0`, licence MIT. Vérifié avec Photoshop 28.0. Voir `mcp/photoshop/README.md` et `VERSIONS.md`.

## 2026-11-17.1 (plugin 2026.11.17.1)

Serveur MCP `illustrator` : Claude pilote Adobe Illustrator par un panneau CEP. Le serveur a 4 outils (`status`, `snapshot`, `batch`, `execute_script`) et 26 commandes de lot. Il tourne avec le Python AOI, sans `-I -S` et sans dossier `libs/`, comme le serveur `indesign`. Le panneau « Claude MCP » est signé : aucun réglage du poste n'est nécessaire. La mise à jour le copie dans `%APPDATA%\Adobe\CEP\extensions`, si Illustrator 2026 a déjà été lancé sur le compte. Nouvelle fiche `mcp/illustrator/addin.json`, forme `source` ; `maj.py` ne change pas. Le panneau se connecte seulement après un clic sur « Connecter ». Origine : `lfoletti/illustrator-mcp` `v0.1.0`, licence MIT. Vérifié avec Illustrator 30.8.2. Voir `mcp/illustrator/README.md` et `VERSIONS.md`.

## 2026-11-16.3 (plugin 2026.11.16.3)

La mise à jour affiche le détail du plugin installé, une ligne par composant : chaque serveur MCP avec sa version, chaque skill, chaque commande et chaque style de sortie, avec son état (« nouveau », « mis à jour », « inchangé », « retiré »). Les étapes suivantes ont un titre : add-ins des applications de ce compte, puis contrôle des imports, Python AOI et Node AOI. Cet affichage ne change pas le résultat de la mise à jour.

## 2026-11-16.2 (plugin 2026.11.16.2)

Le plugin UXP d'InDesign est posé par la mise à jour. `maj.py` reconnaît une nouvelle forme de fiche d'add-in, `uxp` : il lance l'installateur de plugins d'Adobe avec les droits de l'utilisateur, sans élévation. Cette étape ne bloque jamais la mise à jour : un échec est affiché en clair (« ÉCHEC NON BLOQUANT ») et la pose est retentée à la mise à jour suivante. Nouvelle fiche `mcp/indesign/addin.json`. `addin/installer.cmd` reste comme pose à la main. Le serveur `indesign` cite maintenant son origine publiée, `lfoletti/indesign-mcp` `v0.1.0`, et reprend sa licence MIT.

## 2026-11-16.1 (plugin 2026.11.16.1)

Serveur MCP `indesign` : Claude pilote Adobe InDesign par un plugin UXP. Le serveur a 4 outils (`status`, `snapshot`, `batch`, `execute_script`). Il tourne avec le Python AOI, sans `-I -S` et sans dossier `libs/`. Le plugin UXP « Claude MCP » n'est pas posé par la mise à jour : chaque utilisateur lance une fois `mcp/indesign/addin/installer.cmd`, sans droits administrateur. Vérifié avec InDesign 21.6. Voir `mcp/indesign/README.md` et `VERSIONS.md`.

## 2026-11-12.3 (plugin 2026.11.12.3)

Version initiale du dépôt de travail. Contenu : plugin `aoi` avec les serveurs MCP rhino, revit, keyshot, autocad et cortexdb, les skills adhd, cortexdb, d5-lite-rhino et graphify, les commandes `/aoi:remember` et `/aoi:recall`, et le style de sortie `aoi:ste`. Les versions des composants sont dans `VERSIONS.md`.
