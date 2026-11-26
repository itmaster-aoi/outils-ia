# Journal des changements

## 2026-11-26.4 (plugin 2026.11.26.4)

memo : nouveau crochet `UserPromptSubmit`, `convention.py rappel`. Pour une question (`?`) ou un message qui contient un mot comme « notre », « règle », « décision », « stratégie », « politique », « convention », « sécurité », « procédure » ou « pourquoi », il demande à Claude de chercher dans CortexDB avant de répondre (`knowledge_search`, puis `memory_search` avec les 3 filtres du compartiment). Il ne fait rien pour une commande `/…`. Le texte du message n'est pas recopié. Une erreur ne bloque jamais le message. `MEMO_RAPPEL=0` désactive le crochet. Raison : le 26.11.2026, une question sur la stratégie de sécurité a reçu une réponse tirée du dépôt seul, alors que la référence était dans le cerveau. Skill `cortexdb` version 5 : description élargie et section « Chercher avant de répondre ».

## 2026-11-26.2 (plugin 2026.11.26.2)

Le serveur MCP `governance` est retiré de `plugins/aoi/.mcp.json` et de `VERSIONS.md`. La passerelle `th.governance.news` demande une clé : `/mcp` répond `401` (`a key issued by the gateway is required`), et le cerveau `kg-governance` est servi seulement par `/mcp`. Claude Code tentait alors une inscription OAuth, que la passerelle refuse (`unknown brain "/register"`). Aucun autre changement.

## 2026-11-26.1 (plugin 2026.11.26.1)

Nouveau serveur MCP `governance` dans `plugins/aoi/.mcp.json` : serveur distant, type `http`, adresse `https://th.governance.news/mcp`, sans jeton. Ce service est externe à l'atelier : les données que Claude lui envoie quittent le poste. Le plugin ne contient aucun code pour ce serveur. Voir `VERSIONS.md`.

## 2026-11-24.6 (plugin 2026.11.24.6)

Serveur MCP `cortexdb` 2.170.0 (avant : 2.139.1). Binaire `cortexdb-mcp-windows-amd64.exe` de `liliang-cn/cortexdb` `v2.170.0`, empreinte conforme au `.sha256` publié, livré par l'archive `cortexdb-server-2.170.0`. Les commandes `/aoi:recall` et `/aoi:remember` sont reprises de la même version, avec une phrase sur le compartiment des mémoires. Voir `VERSIONS.md`.

memo, convention version 3 : toutes les mémoires vont dans un seul compartiment, `scope=user`, `user_id` = login Windows, `namespace=assistant`. Le serveur cherche une mémoire dans un seul compartiment, et une recherche sans filtre lit `memory:global:default` : elle ne trouvait donc rien. Le crochet `PreToolUse` refuse maintenant `memory_save`, `memory_search`, `knowledge_memory_recall` et `knowledge_memory_build_context_pack` sans ces 3 filtres, et donne les valeurs. `convention.py analyser` propose de déplacer une mémoire d'un autre compartiment (action `renommer`, même identifiant), et `migrer` la déplace. La skill `cortexdb` (version 4) et la skill `memo` donnent la règle. La version 2.170.0 du serveur ne change pas ce comportement : le correctif est dans le plugin.

## 2026-11-24.5 (plugin 2026.11.24.5)

memo : après une migration réussie, une seconde passe de `convention.py migrer --simuler` donne `Écritures : 0`. Une ligne `renommer` qui garde son identifiant, et dont le texte, les métadonnées et l'auteur sont déjà égaux à la base, compte dans « déjà faits ». Avant, elle était toujours réécrite, sans effet sur les données. Aucun autre changement.

## 2026-11-24.4 (plugin 2026.11.24.4)

memo : `/aoi:memo` lancé sans demande précise propose 3 choix : écrire un élément, ingérer une mémoire dossier, analyser ou migrer un cerveau. L'agent `aoi:memo-cerveau` devient `aoi:memo-analyse`. `/aoi:memo-importer tout` demande une confirmation avant de lancer la liste, puis montre la liste avant d'ingérer. Aucun autre changement.

## 2026-11-24.3 (plugin 2026.11.24.3)

Tous les composants de memo portent le nom memo : skill `/aoi:memo` (au lieu de `/aoi:convention`), commandes `/aoi:memo-bilan` et `/aoi:memo-importer` (au lieu de `/aoi:importer-memoire`), agent `aoi:memo-cerveau` (au lieu de `aoi:convention-cortexdb`). Aucun autre changement.

## 2026-11-24.2 (plugin 2026.11.24.2)

memo fait maintenant partie du plugin `aoi`. Le plugin séparé `memo` de l'étiquette `2026-11-24.1`, jamais activé, est retiré du catalogue : `maj.py` met à jour seulement `aoi@aoi`, et un plugin séparé n'aurait jamais été mis à jour sur les postes. Nouveaux noms : skill `/aoi:convention`, commandes `/aoi:memo-bilan` et `/aoi:importer-memoire`, agent `aoi:convention-cortexdb` (premier dossier `agents/` du plugin). Script `plugins/aoi/memo/convention.py`. Deux crochets s'ajoutent au crochet de démarrage dans `hooks/hooks.json` : `PreToolUse` (contrôle des écritures CortexDB) et `PostToolUse` (miroir de la mémoire Claude Code). Rien à ajouter dans `enabledPlugins` : seule l'étiquette du catalogue change dans les réglages gérés. Voir `plugins/aoi/memo/LISEZMOI.md`.

## 2026-11-24.1 (plugin aoi 2026.11.24.1, plugin memo 2026.11.24.8)

Nouveau plugin `memo` dans le catalogue : la convention de nommage commune des cerveaux CortexDB de l'atelier. Identifiant `<nature>:<theme>:<sujet>`, métadonnées `nature`, `theme`, `status`, `date` pour une nature datée et `produit_par`, auteur = login Windows normalisé. Un crochet `PreToolUse` refuse une écriture CortexDB hors convention et donne la correction. Un crochet `PostToolUse` recopie chaque fichier de la mémoire Claude Code dans le cerveau local (phase de transition, double écriture). Skill `/memo:convention`, commandes `/memo:bilan` et `/memo:importer-memoire`, agent `memo:convention-cortexdb` (analyse d'un cerveau, table de renommage, migration préparée ; la migration finale reste un geste de l'utilisateur). Script `plugins/memo/convention/convention.py` en bibliothèque standard, lancé avec le Python AOI. Le plugin s'active par `"memo@aoi": true` dans les réglages gérés. Voir `plugins/memo/LISEZMOI.md` et `plugins/memo/CHANGELOG.md`.

Plugin `aoi` : skill `cortexdb` version 3. Les identifiants et les métadonnées suivent la convention du plugin `memo` ; la migration d'un cerveau par `convention.py migrer`, lancée par l'utilisateur, est la seule exception à la règle « pas de `cortexdb-mcp.exe` en ligne de commande ».

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
