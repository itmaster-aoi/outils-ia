# Journal des changements

## 2026-11-16.3 (plugin 2026.11.16.3)

La mise à jour affiche le détail du plugin installé, une ligne par composant : chaque serveur MCP avec sa version, chaque skill, chaque commande et chaque style de sortie, avec son état (« nouveau », « mis à jour », « inchangé », « retiré »). Les étapes suivantes ont un titre : add-ins des applications de ce compte, puis contrôle des imports, Python AOI et Node AOI. Cet affichage ne change pas le résultat de la mise à jour.

## 2026-11-16.2 (plugin 2026.11.16.2)

Le plugin UXP d'InDesign est posé par la mise à jour. `maj.py` reconnaît une nouvelle forme de fiche d'add-in, `uxp` : il lance l'installateur de plugins d'Adobe avec les droits de l'utilisateur, sans élévation. Cette étape ne bloque jamais la mise à jour : un échec est affiché en clair (« ÉCHEC NON BLOQUANT ») et la pose est retentée à la mise à jour suivante. Nouvelle fiche `mcp/indesign/addin.json`. `addin/installer.cmd` reste comme pose à la main. Le serveur `indesign` cite maintenant son origine publiée, `lfoletti/indesign-mcp` `v0.1.0`, et reprend sa licence MIT.

## 2026-11-16.1 (plugin 2026.11.16.1)

Serveur MCP `indesign` : Claude pilote Adobe InDesign par un plugin UXP. Le serveur a 4 outils (`status`, `snapshot`, `batch`, `execute_script`). Il tourne avec le Python AOI, sans `-I -S` et sans dossier `libs/`. Le plugin UXP « Claude MCP » n'est pas posé par la mise à jour : chaque utilisateur lance une fois `mcp/indesign/addin/installer.cmd`, sans droits administrateur. Vérifié avec InDesign 21.6. Voir `mcp/indesign/README.md` et `VERSIONS.md`.

## 2026-11-12.3 (plugin 2026.11.12.3)

Version initiale du dépôt de travail. Contenu : plugin `aoi` avec les serveurs MCP rhino, revit, keyshot, autocad et cortexdb, les skills adhd, cortexdb, d5-lite-rhino et graphify, les commandes `/aoi:remember` et `/aoi:recall`, et le style de sortie `aoi:ste`. Les versions des composants sont dans `VERSIONS.md`.
