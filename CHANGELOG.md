# Journal des changements

## 2026-11-16.1 (plugin 2026.11.16.1)

Serveur MCP `indesign` : Claude pilote Adobe InDesign par un plugin UXP. Le serveur a 4 outils (`status`, `snapshot`, `batch`, `execute_script`). Il tourne avec le Python AOI, sans `-I -S` et sans dossier `libs/`. Le plugin UXP « Claude MCP » n'est pas posé par la mise à jour : chaque utilisateur lance une fois `mcp/indesign/addin/installer.cmd`, sans droits administrateur. Vérifié avec InDesign 21.6. Voir `mcp/indesign/README.md` et `VERSIONS.md`.

## 2026-11-12.3 (plugin 2026.11.12.3)

Version initiale du dépôt de travail. Contenu : plugin `aoi` avec les serveurs MCP rhino, revit, keyshot, autocad et cortexdb, les skills adhd, cortexdb, d5-lite-rhino et graphify, les commandes `/aoi:remember` et `/aoi:recall`, et le style de sortie `aoi:ste`. Les versions des composants sont dans `VERSIONS.md`.
