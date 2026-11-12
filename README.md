# outils-ia

Dépôt de travail : un catalogue de plugins pour Claude Code. Il contient le plugin `aoi`, avec des serveurs MCP (Model Context Protocol) pour des logiciels de CAO et de rendu, des skills et un style de sortie.

Le contenu change souvent et n'a pas de garantie. Les étiquettes datées (`2026-11-12.3`) marquent des états cohérents du dépôt.

## Contenu

```
.claude-plugin/marketplace.json   catalogue « aoi »
plugins/aoi/                      le plugin
  .claude-plugin/plugin.json
  .mcp.json                       déclaration des serveurs MCP
  mcp/                            un dossier par serveur MCP, avec son README
    rhino/                          Rhino 8 : serveur Python, librairies figées
    revit/                          Revit 2025 : serveur Node avec outils de graphe de connaissances (KG)
    keyshot/                        KeyShot Studio 2026 : serveur et pont
    autocad/                        AutoCAD 2027 : add-in qui est aussi le serveur
    cortexdb/                       mémoire durable locale (SQLite)
  commands/                       /aoi:remember et /aoi:recall (cortexdb)
  controle/                       contrôle des imports Python (liste blanche) et Python embarqué
  lanceur/                        lanceur des serveurs publiés à part
  skills/
    adhd/                         idéation en parallèle
    cortexdb/                     mémoire durable de l'utilisateur
    d5-lite-rhino/                pilotage de D5 Lite dans Rhino 8
    graphify/                     graphe de connaissances d'un dossier
    regen/scripts/                mise à jour du plugin et des archives (maj.py)
  output-styles/
    ste.md                        style de sortie aoi:ste : rédaction technique simplifiée (ASD-STE100)
tests/                            tests des scripts du plugin
VERSIONS.md                       versions des composants, sources et empreintes
CHANGELOG.md                      journal des changements
```

Les parties lourdes (Python embarqué, Node, serveurs compilés, add-ins) sont publiées comme versions GitHub du dépôt. Chaque fiche JSON du plugin donne l'adresse et l'empreinte SHA-256 de son archive.

## Licences

Les licences des projets d'origine sont conservées dans chaque dossier. Voir `VERSIONS.md` pour la source de chaque composant.

## Vérifier

```
claude plugin validate .
claude plugin validate ./plugins/aoi
```
