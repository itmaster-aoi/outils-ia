# Journal des changements

Une entrée par étiquette du dépôt, la plus récente en haut. L'étiquette est celle que la console impose aux postes (`extraKnownMarketplaces` et `strictKnownMarketplaces`) ; les postes la récupèrent avec `/regen`. Les versions de chaque composant sont dans [`VERSIONS.md`](VERSIONS.md), le détail dans les messages de commit.

À chaque nouvelle étiquette : ajouter son entrée ici, dans le même commit que le changement de version de `plugins/aoi/.claude-plugin/plugin.json`. À chaque modification de `installer-poste.ps1` : changer `$VersionInstalleur` (date du jour), sinon les copies dépassées ne sont pas signalées.

## 2026-10-28.2 (plugin 2026.10.28.2)

- Nouvelle organisation des dossiers ([`docs/organisation-dossiers.md`](docs/organisation-dossiers.md)) : `%LOCALAPPDATA%\aoi\serveurs`, `donnees` et `journal`. Cette étiquette lit les deux organisations. Un poste reste sur l'ancienne tant que `migrer-dossiers.cmd` n'a pas été lancé.
  - `.mcp.json` lance cortexdb et le serveur Revit par `lanceur/lancer.py`, sans numéro de version. Le lanceur choisit le dossier du serveur et, après migration, la base cortexdb (`CORTEXDB_PATH`). Le serveur s'arrête avec le lanceur (Job Object).
  - `migrer-dossiers.cmd` (dossier du plugin, chemin complet donné par `maj.py --verifier-dossiers`) : à lancer une fois par compte Windows, Claude Code et logiciels hôtes fermés. Il copie les serveurs, la base cortexdb (copie contrôlée) et les journaux, sans rien effacer. `--annuler` revient à l'ancienne organisation.
  - `/regen` et le démarrage de session affichent l'état des dossiers (« à migrer » ou « migré »).
- Correction de `/regen` : un serveur de la même version, endommagé, est réinstallé sans perdre ses fichiers `conserver` (`revit-data.db`). Un dossier de serveur encore utilisé n'est plus effacé à moitié.
- `archives/construire.py` ne réécrit plus `.mcp.json`.
- Nouveau `tests/test_migration_dossiers.py` : 32 tests sur un poste simulé, avec le Python embarqué du plugin.

## 2026-10-28.1 (plugin 2026.10.28.1)

- Nouveau serveur `plugin:aoi:autocad` pour AutoCAD 2027 (version complète, pas LT) : 37 outils pour lire, contrôler, nettoyer, modifier, tracer en PDF et exporter des dessins DWG, et préparer des lots.
  - Le serveur est l'add-in lui-même : il tourne dans AutoCAD et répond sur `http://127.0.0.1:1997/mcp`. Entrée `autocad` de `.mcp.json`, type `http`, délai de 600 s pour le tracé et l'export.
  - Add-in 0.3.6, importé de [lfoletti/autocad-mcp](https://github.com/lfoletti/autocad-mcp), étiquette `v0.3.6`, commit `f5e64fbf3fdd4b224d367ed886d31b34c47566e5` par `amont/importer_autocad.py` (provenance et empreintes dans `mcp/autocad/VERSION-AOI.txt`). Livré par l'archive `autocad-addin-2026-10-28` (`archives/construire.py autocad-addin`). `/regen` le copie dans `%APPDATA%\Autodesk\ApplicationPlugins\aoi-autocad-mcp.bundle`, AutoCAD fermé, si le dossier `%APPDATA%\Autodesk\AutoCAD 2027` existe.
  - Sans jeton (écoute sur 127.0.0.1, en-tête `Origin` étrangère refusée). DLL non signées : AutoCAD peut demander une fois de charger l'add-in.
  - `execute_lisp` et `run_command` sont actifs. `"enable_execute": false` dans `%LOCALAPPDATA%\autocad-mcp\config.json` les ferme sur un poste.
- `archives/construire.py` : partie `autocad-addin`.
- Nouveau `amont/importer_autocad.py` : importe une étiquette d'un clone de lfoletti/autocad-mcp dans `mcp/autocad/` (contrôle du clone, README, licence, fiche add-in, provenance). Il vérifie que les DLL de l'archive portent le commit importé ; avec `--plugin`, il écrit les versions de `plugin.json` et de `VERSIONS.md`.

## 2026-10-27.3 (plugin 2026.10.27.3)

- Skill `/aoi:cortexdb`, version 2 : Claude remplace le modèle de langage de cortexdb, avec l'abonnement de l'atelier. Aucun modèle externe n'est configuré, les variables de `.mcp.json` restent vides.
  - Recherche : Claude prépare `keywords`, `alternate_queries` et `entity_names` avant `knowledge_memory_recall` et `memory_search`.
  - Enregistrement : Claude cherche d'abord les faits contredits et les remplace avec `supersedes`.
  - Nouveau « Bilan d'une session », sur demande : Claude propose les faits durables, l'utilisateur confirme.

## 2026-10-27.2 (plugin 2026.10.27.2)

- Serveur `plugin:aoi:contaixt` retiré (`https://contaixt.ai/mcp`, ajouté au plugin 2026.10.15.5). `installer-poste.ps1` continue de retirer une déclaration user `contaixt` laissée par le script du fournisseur.
- `/regen` (`maj.py`, `plugin_installe()`) : pour le plugin en portée `managed`, `claude plugin update` met la nouvelle version dans le cache sans toujours corriger `installed_plugins.json`. `maj.py` lisait alors l'ancienne version et installait les archives de celle-ci : au passage à 2026.10.27.1, `cortexdb-server` n'était pas installé et `plugin:aoi:cortexdb` échouait (« Connection closed »). `maj.py` prend désormais la version du catalogue inscrit quand elle est déjà dans le cache. Le crochet de démarrage affiche aussi la bonne version.
  - Le premier `/regen` vers 2026.10.27.2 tourne encore avec l'ancien `maj.py`. Après le redémarrage de Claude Code, lancer `/regen` une 2e fois : il installe `cortexdb-server` s'il manque.

## 2026-10-27.1 (plugin 2026.10.27.1)

- Nouveau serveur `plugin:aoi:cortexdb` : mémoire d'agent et graphe de connaissances dans un fichier SQLite local (`~/.cortexdb/cortexdb.db`). Projet [liliang-cn/cortexdb](https://github.com/liliang-cn/cortexdb) 2.139.1, fork de référence [itmaster-aoi/cortexdb](https://github.com/itmaster-aoi/cortexdb), commit `a808c1296002043eea5f5c3e7d550530ce1a5755`.
  - Serveur : binaire Windows publié par l'auteur, empreinte vérifiée, livré par l'archive `cortexdb-server-2.139.1` (`archives/construire.py cortexdb-server`) et installé par `/regen` dans `%LOCALAPPDATA%\aoi\cortexdb-server-2.139.1`. Le lanceur d'origine, qui téléchargeait le binaire au premier lancement, n'est pas repris.
  - `.mcp.json` vide les variables des services externes (embeddings, modèle de langage, reranker) et du serveur partagé : mode lexical, sans service externe, même si le poste a une clé `OPENAI_API_KEY`.
  - Commandes `/aoi:remember` et `/aoi:recall` reprises telles quelles par le nouveau `amont/importer_cortexdb.py`. Nouvelle skill `/aoi:cortexdb`, écrite pour l'atelier : quand mémoriser, ce qu'il ne faut jamais mémoriser.
  - Non repris : la skill d'origine (documentation de la librairie Go), les 11 autres commandes (appels du binaire en bash), les crochets (rappel à chaque requête, contexte avant chaque lecture de fichier), le mod `cortexdb-live`.
- `archives/construire.py` : partie `cortexdb-server` ; la mise à jour de `.mcp.json` vaut pour `revit-server` et `cortexdb-server`. `/regen` affiche « Serveur MCP CortexDB ».

## 2026-10-19.2 (plugin 2026.10.19.2)

- Serveur `plugin:aoi:keyshot` : keyshot-mcp 1.0.0, importé de [lfoletti/keyshot-mcp](https://github.com/lfoletti/keyshot-mcp), étiquette `v1.0.0`, commit `266c26a1ef90ed5882213d7818d207207a335d1d` par `amont/importer_keyshot.py`, sans adaptation du code (provenance et empreintes dans `mcp/keyshot/VERSION-AOI.txt`). Remplace le serveur 0.1.1 et le pont 0.2.13. Le pont et le serveur portent désormais le même numéro.
  - 33 outils (+ `set_visibility`, `save_material_to_library`) et un second prompt, `keyshot_materiaux`.
  - Couleurs `#RRGGBB` lues en sRGB : elles sortent plus sombres qu'avant. Les textures ne sont lues que dans les dossiers autorisés (`dossiers_textures`), jamais sur un chemin réseau. Les noms de matériaux refusent les caractères interdits dans un nom de fichier.
  - Noms du projet d'origine : scripts KeyShot « MCP start » et « MCP stop » (au lieu de « MCP server start » et « MCP server stop », que `/regen` efface), réglages et journal dans `%LOCALAPPDATA%\keyshot-mcp\` (l'ancien `%LOCALAPPDATA%\aoi\keyshot\pont-config.json` n'est plus lu : le recopier si un poste en avait un), variable `KEYSHOT_MCP_EXECUTE_PYTHON`.
  - Après `/regen` : redémarrer KeyShot, puis lancer « MCP start ».
- Nouveau `amont/importer_keyshot.py` : importe une étiquette d'un clone de lfoletti/keyshot-mcp dans `mcp/keyshot/` (contrôle du clone, copie, fiche add-in, README, provenance ; avec `--plugin`, versions de `plugin.json`, `VERSIONS.md` et brouillon de cette entrée).

## 2026-10-19.1 (plugin 2026.10.19.1)

- Nouveau style de sortie `aoi:ste` (`output-styles/ste.md`) : rédaction technique simplifiée inspirée d'ASD-STE100, en français et en anglais. Phrases courtes, une action par instruction, voix active, termes constants, mises en garde avant l'étape concernée. `keep-coding-instructions: true` garde les consignes de développement de Claude Code. Pour l'imposer : `"outputStyle": "aoi:ste"` dans les managed settings de la console. Sans ce réglage, chaque utilisateur peut le choisir avec `/output-style aoi:ste`. Après `/regen`, redémarrer Claude Code : les styles sont lus au démarrage.

## 2026-10-16.6 (plugin 2026.10.16.6)

- Scripts KeyShot renommés : `aoi_keyshot_bridge` devient « MCP server start » et `aoi_keyshot_stop` devient « MCP server stop » (noms affichés dans l'onglet Scripts de la console de scripting). Pont 0.2.13 et serveur 0.1.1 : seuls les noms changent dans les messages et dans le chemin relu par `reload_bridge`. Après `/regen`, redémarrer KeyShot (il ne voit les scripts renommés qu'à son démarrage ; `reload_bridge` ne peut pas recharger un pont 0.2.12 dont le fichier a été retiré), puis lancer « MCP server start ».
- `/regen` : nouvelle clé facultative `retirer` dans `addin.json`, avec la liste des fichiers d'une version précédente à effacer de la destination avant la copie. KeyShot l'utilise pour retirer `aoi_keyshot_bridge.py` et `aoi_keyshot_stop.py`.

## 2026-10-16.5 (plugin 2026.10.16.5)

- Scripts KeyShot (`aoi_keyshot_bridge`, `aoi_keyshot_stop`) : auteur affiché dans la console de scripting « Lauro Foletti » au lieu de « atelier oi (IT) ». Code inchangé (pont 0.2.12, arrêt 0.1.0). `/regen` recopie les deux scripts.

## 2026-10-16.4 (plugin 2026.10.16.4)

- Nouveau serveur `plugin:aoi:keyshot` : Claude pilote KeyShot Studio 2026 (fenêtre ouverte) par un pont lancé dans KeyShot (`aoi_keyshot_bridge`, onglet Scripts). 31 outils : scène et pièces, capture, caméras (dont une caméra cadrée automatiquement), matériaux de la scène et de la bibliothèque (copies, réglages, graphe, annulation), rendus en arrière-plan, enregistrement avec copie de l'ancien `.bip`. `execute_python` est désactivé sauf réglage du poste.
- Add-in KeyShot : `/regen` copie le pont dans `%PUBLIC%\Documents\KeyShot Studio\Scripts` si ce dossier existe. Un poste sans KeyShot Studio est ignoré sans message. Pas de version minimale : la clé de registre prévue (`HKLM\SOFTWARE\Luxion\KeyShot`) n'a pas pu être vérifiée. KeyShot ne voit le script qu'après un redémarrage.
- Librairies : copie identique de celles de rhino dans `mcp/keyshot/libs` (`mcp` 1.28.1). Les partager avec `../rhino/libs` ne fonctionne pas : le contrôle des imports refuse `mcp` hors du dossier du serveur.

## 2026-10-16.3 (plugin 2026.10.16.3, librairies du Python AOI 2026-10-16)

- Librairies ajoutées au Python AOI sans le reconstruire : demandées dans `python-aoi/ajouts.txt`, résolues par `python-aoi/verrouiller.py` (hors de Claude Code, essai d'import avec la liste blanche du dépôt), inscrites avec leur empreinte SHA-256 dans `plugins/aoi/python-libs.json`. `/regen` et l'installeur (`archives_aoi.py`) téléchargent les roues depuis PyPI, refusent toute empreinte différente, les décompressent dans `%LOCALAPPDATA%\aoi\python-libs-<version>` et les branchent sur le Python AOI par `aoi-libs.pth`. Plus d'archive à reconstruire pour une librairie de plus.
- Premières librairies : `mcp` 2.3.0, `pydantic` 2.14.1, `pywin32` 312 et leurs dépendances (27 roues, 14 Mo).
- `controle/whitelist.txt` : la ligne `pywin32`, qui n'est pas un nom de module, est remplacée par `pywintypes`, `pythoncom`, `win32com`, `win32api`, `win32con`, `win32gui`, `win32process`, `win32file`, `win32clipboard`.

## 2026-10-16.2 (plugin 2026.10.16.2)

- Serveur `plugin:aoi:contaixt` : nouvelle adresse `https://contaixt.ai/mcp`, à la place de `https://veille.casual-labs.ch/mcp` (même serveur, 83.228.221.151). Toujours sans jeton. Au 16.10.2026, le filtrage web FortiGuard du pare-feu de l'atelier bloque encore `contaixt.ai` (refus provisoire).

## 2026-10-16.1 (plugin 2026.10.16.1)

- `controle/whitelist.txt` : nouvelle section « Développement » avec `mcp`, `pydantic` et `pywin32`. Ces paquets ne font pas partie du Python AOI (`python-aoi/paquets.txt` inchangé) : l'import n'est plus refusé par le contrôle, mais ils doivent être présents dans l'environnement qui les importe.

## 2026-10-15.5 (plugin 2026.10.15.5, installeur 2026-10-15.3)

- Nouveau serveur `plugin:aoi:contaixt` : service distant HTTP `https://veille.casual-labs.ch/mcp`, sans jeton (page d'installation du fournisseur : `https://veille.casual-labs.ch/setup`). Remplace l'ancien `veille` (même hôte, avec `AOI_VEILLE_TOKEN`), qui reste retiré.
- `installer-poste.ps1` : l'étape 5 retire aussi les déclarations user `kg` et `contaixt`, que le script d'installation du fournisseur ajoute en scope user, pour éviter un doublon avec le plugin.

## 2026-10-15.4 (plugin 2026.10.15.4, installeur 2026-10-15.2)

- Add-in Rhino : Rhino 8.32 minimum. Une version plus ancienne ne peut pas charger l'add-in. Nouvelle clé `version_min` dans `addin.json` (version lue dans le registre) : en dessous, `/regen` et l'installeur ne téléchargent ni ne copient l'add-in et affichent « ÉCHEC : version … installée, l'add-in demande 8.32 ou plus récente ». Le démarrage de session affiche une alerte. Un add-in déjà copié n'est pas retiré.
- `installer-poste.ps1` : un plugin présent mais incomplet (`skills\regen` absent, après une installation interrompue) est désinstallé puis réinstallé à la même étiquette. Avant, `claude plugin update` répondait « déjà à jour » et le bilan affichait « ok ». S'il reste incomplet, le bilan affiche « INCOMPLET ». L'étape Python et Node AOI n'est plus sautée en silence quand `archives_aoi.py` manque.

## 2026-10-15.3 (plugin 2026.10.15.3, Python AOI 2026-10-15)

- **graphify** ([Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify)) entre dans l'outillage : clone GitHub relu par l'IT, installé dans le Python AOI par `python-aoi/construire.ps1` (aucun `pip` sur les postes), dépendances en roues binaires dans `python-aoi/paquets.txt` (grammaires tree-sitter limitées aux langages de l'atelier). `graphify` et `networkx` ajoutés à `controle/whitelist.txt`.
- Nouvelle skill `/aoi:graphify` (`skills/graphify/`), générée par `python-aoi/adapter_skill_graphify.py` à partir du même clone : texte d'origine (variante Windows), le Python AOI remplace les installeurs (uv, pipx, pip), les appels `graphify …` deviennent `python.exe -m graphify …`.
- Python AOI `2026-10-15` (85 Mo, empreinte dans `plugins/aoi/python-aoi.json`) : Python 3.12.10 et paquets précédents, plus graphify 0.9.91 (commit `10130e79`), networkx 3.7, rapidfuzz 3.14, tree-sitter 0.25 et sept grammaires. Les postes le téléchargent au prochain `/regen` ou à l'installation, le Python AOI n'étant rechargé que quand sa version change.

## 2026-10-15.2 (plugin 2026.10.15.2)

- `/regen` passe la main à la nouvelle version : après l'installation du plugin, `maj.py --finir` de la version installée prépare le poste (add-ins, contrôle des imports, Python et Node AOI, cache) avec ses propres chemins. Corrige le cas de la 2026-10-15.1, où un `/regen` depuis la 2026-10-14.1 ne recopiait pas le contrôle des imports, déplacé dans `controle/`.
- Au démarrage de chaque session, le contrôle des imports est recopié s'il diffère de celui du plugin (`activer_controle.py --si-besoin`).
- Cache : un reste d'effacement verrouillé n'est plus renommé à chaque passage (`.a-effacer.a-effacer`).
- Un script attendu absent du plugin s'affiche « ÉCHEC : … introuvable » au lieu d'être passé en silence. Le bilan de `/regen` indique aussi les skills retirées.
- Règle ajoutée dans `skills/regen/SKILL.md` (« Pour l'IT ») : ne pas déplacer ce qu'utilise un ancien `/regen`.

## 2026-10-15.1 (plugin 2026.10.15.1, installeur 2026-10-15.1)

- Skill `/aoi:report` retirée, avec `report.py` et `mcp-whitelist.txt` (lu seulement par `report.py`). La consigne correspondante est retirée des managed settings.
- Le contrôle des imports reste actif et inchangé : `guard/sitecustomize.py`, `whitelist.txt`, `activer_controle.py` et le Python embarqué passent de `skills/report/` à `plugins/aoi/controle/`. Crochet de démarrage, `/regen`, installeur et scripts de construction suivent le nouveau chemin.
- `installer-poste.ps1` accepte encore un plugin antérieur (`skills/report/`) ; la ligne « /report » des vérifications finales est retirée.

## Installeur 2026-10-14.2 (branche main, hors étiquette)

- `installer-poste.ps1` compare sa version (`$VersionInstalleur`) à celle du dépôt et avertit si la copie lancée est dépassée, par exemple sur un partage réseau oublié. La personne choisit de continuer ou non. Les copies antérieures à cette version n'ont pas ce contrôle.
- Nouvelle étape 4, « Connexion à claude.ai » : à la première fois, la connexion s'ouvre depuis l'installeur, qui continue ensuite. Il n'est plus nécessaire de le lancer deux fois. Une connexion autre que claude.ai est signalée.
- Étape du jeton de veille retirée, avec l'option `-SansVeille`.

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
