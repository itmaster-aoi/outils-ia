# Versions de référence

Seules ces versions sont autorisées sur les postes de l'atelier. Toute nouvelle version est relue et validée par l'IT, puis inscrite ici avec une nouvelle étiquette du dépôt.

| Serveur | Composant | Source d'origine | Version de référence | Licence | Validée le |
|---|---|---|---|---|---|
| `aoi-rhino` | serveur MCP (`mcp/rhino/server`) | paquet Python `rhinomcp` ([jingcheng-chen/rhinomcp](https://github.com/jingcheng-chen/rhinomcp)) | 0.3.2 | MIT | 12.10.2026 |
| `aoi-rhino` | plugin Rhino 8 (`mcp/rhino/addin`) | paquet Rhino `rhinomcp` (même projet) | 0.4.1.1 | MIT | 12.10.2026 |
| `aoi-rhino` | librairies Python (`mcp/rhino/libs`) | copiées de l'environnement validé, voir la liste ci-dessous | Python 3.12, Windows 64 bits | voir chaque `*.dist-info` | 12.10.2026 |
| `aoi-revit` | serveur MCP avec outils KG (`mcp/revit/server`) | fork [lfoletti/mcp-servers-for-revit](https://github.com/lfoletti/mcp-servers-for-revit), branche `kg-tools-vendoring` (projet d'origine : mcp-servers-for-revit) | commit `90eefab82ab75e9a61e9c511c7e63b88e436d323` (11.08.2026), compilé par l'IT, Node 25 ; 55 outils dont 28 `kg_*` | MIT (origine) + MIT (KG) | 12.10.2026 |
| `aoi-revit` | add-in Revit 2025 (`mcp/revit/addin/2025`) | `RevitMCPCommandSet` (origine) + `RevitMCPCommandSet.KG` 0.1.0 avec BimKg (Lauro Foletti) | 50 commandes (22 + 28 KG) ; `send_code_to_revit` désactivée, `Extended` non repris | MIT (origine) + MIT (KG) | 12.10.2026 |
| `aoi-veille` | service distant | `https://veille.casual-labs.ch/mcp` | sans objet : le code tourne chez le fournisseur | – | 12.10.2026 |

## Librairies Python de `aoi-rhino` (`mcp/rhino/libs`)

annotated-doc 0.0.4 · annotated-types 0.7.0 · anyio 4.9.0 · attrs 23.1.0 · certifi 2025.1.31 · click 8.1.7 · colorama 0.4.6 · h11 0.14.0 · httpcore 1.0.2 · httpx 0.28.1 · httpx-sse 0.4.3 · idna 3.10 · jsonschema 4.23.0 · jsonschema-specifications 2023.7.1 · markdown-it-py 2.2.0 · mcp 1.28.1 · mdurl 0.1.0 · pydantic 2.13.4 · pydantic-core 2.46.4 · pydantic-settings 2.14.2 · pygments 2.20.0 · pyjwt 2.13.0 · python-dotenv 1.2.2 · python-multipart 0.0.22 · pywin32 312 · referencing 0.30.2 · rich 13.9.4 · rpds-py 0.10.6 · shellingham 1.5.4 · sniffio 1.3.1 · sse-starlette 3.4.5 · starlette 0.50.0 · typer 0.26.8 · typing-extensions 4.14.1 · typing-inspection 0.4.2 · uvicorn 0.54.0

Note : le plugin Rhino (0.4.1.1) et le serveur Python (0.3.2) n'ont pas le même numéro de version. C'est la combinaison qui fonctionne actuellement sur le poste de l'IT.
