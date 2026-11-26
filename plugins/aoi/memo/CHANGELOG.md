# Changements de la convention et de memo

## memo dans le plugin aoi 2026.11.26.4 (2026-11-26), convention version 3

- Nouvelle sous-commande `rappel`, crochet `UserPromptSubmit` : pour une question ou un message qui contient un mot de `MOTS_RAPPEL`, elle ajoute au contexte la consigne de chercher dans CortexDB (`knowledge_search`, `memory_search` avec `scope=user`, `user_id=<login>`, `namespace=assistant`) avant de répondre. Aucun rappel pour un message vide ou une commande `/…`. Le texte du message n'apparaît jamais dans la sortie. Toute erreur donne une sortie vide et le code 0. `MEMO_RAPPEL=0` la désactive.
- 12 tests ajoutés (`TestsRappel`), dont 3 tests de bout en bout par un sous-processus. Les tests ont échoué avant le code (5 rouges). 2 mutations ont été faites : retirer le test du `?` et retirer le test du `/`. Chaque mutation fait échouer un test.

## memo dans le plugin aoi 2026.11.24.6 (2026-11-24), convention version 3

- Compartiment unique des mémoires : `scope=user`, `user_id` = login Windows, `namespace=assistant` (`memoire_scope` et `memoire_namespace` dans `convention.yaml`). Le projet va dans la métadonnée `projet`, jamais dans le namespace.
- Crochet `garde` : refuse `memory_save` hors de ce compartiment, et `memory_search`, `knowledge_memory_recall`, `knowledge_memory_build_context_pack` sans les 3 filtres (au premier niveau ou dans `plan.filters`). Une recherche avec `disable_memory` reste libre.
- `analyser` : une mémoire d'un autre compartiment reçoit l'action `renommer` avec le même identifiant ; son ancien namespace devient la métadonnée `projet` si elle n'en a pas.
- `migrer` : écrit chaque mémoire dans le compartiment de la convention, puis contrôle le compartiment à la relecture. Le serveur met à jour la ligne de même identifiant : la mémoire change de compartiment, sans doublon.

## memo dans le plugin aoi 2026.11.24.5 (2026-11-24), convention version 2

- `migrer` : une ligne `renommer` qui garde son identifiant, et dont le texte, les métadonnées et l'auteur sont déjà égaux à la base, compte dans « déjà faits ». Une seconde passe de `migrer --simuler` après une migration réussie donne `Écritures : 0`. Un document qui porte encore une clé retirée est toujours réécrit.

## memo dans le plugin aoi 2026.11.24.4 (2026-11-24), convention version 2

- `/aoi:memo` lancé sans demande précise pose une seule question, « Que voulez-vous faire avec la mémoire centrale ? », avec 3 choix : écrire un élément, ingérer une mémoire dossier, analyser ou migrer un cerveau. « Corriger un refus » n'est plus proposé.
- L'agent `aoi:memo-cerveau` devient `aoi:memo-analyse` (fichier `agents/memo-analyse.md`).
- `/aoi:memo-importer tout` demande une confirmation avant de lancer la liste, puis montre la liste avant d'ingérer.

## memo dans le plugin aoi 2026.11.24.3 (2026-11-24), convention version 2

- Tous les composants portent le nom memo : skill `/aoi:memo` (au lieu de `/aoi:convention`), commandes `/aoi:memo-bilan` et `/aoi:memo-importer` (au lieu de `/aoi:importer-memoire`), agent `aoi:memo-cerveau` (au lieu de `aoi:convention-cortexdb`).

## memo dans le plugin aoi 2026.11.24.2 (2026-11-24), convention version 2

- memo n'est plus un plugin séparé : il fait partie du plugin aoi, que `maj.py` met à jour sur les postes. Un plugin séparé n'aurait jamais été mis à jour.
- Nouveaux noms : skill `/aoi:convention`, commandes `/aoi:memo-bilan` et `/aoi:importer-memoire`, agent `aoi:convention-cortexdb`. Script dans `plugins/aoi/memo/convention.py`. Les crochets sont dans `plugins/aoi/hooks/hooks.json`, avec le crochet de démarrage d'aoi.
- Rien à ajouter dans `enabledPlugins` : seule l'étiquette du catalogue change dans les réglages gérés.
- Le plugin `memo` de l'étiquette `2026-11-24.1`, jamais activé, est retiré du catalogue.

## Plugin memo 2026.11.24.8 (2026-11-24), convention version 2

- Le plugin harmonie s'appelle maintenant **memo**. Les entrées ci-dessous gardent l'ancien nom.
- Nouveaux noms : commandes `/memo:convention`, `/memo:bilan`, `/memo:importer-memoire` ; agent `memo:convention-cortexdb` ; variables `MEMO_RAPPORTS` et `MEMO_MIROIR` (au lieu de `HARMONIE_*`) ; rapports dans `%USERPROFILE%\Documents\memo\rapports\` ; catalogue `plugins/memo`, activation `"memo@aoi": true`.

## Plugin harmonie 2026.11.24.7 (2026-11-24), convention version 2

- Le cerveau par défaut est le cerveau racine de l'utilisateur (`%USERPROFILE%\.cortexdb\cortexdb.db`), comme le serveur CortexDB. Si une autre base est lue (`CORTEXDB_PATH`, chemin donné), `analyser`, `memoires` et `migrer` l'annoncent par un avertissement, que l'agent reprend.

## Plugin harmonie 2026.11.24.6 (2026-11-24), convention version 2

- Commande `/harmonie:importer-memoire tout` ou `<chemin du projet>` : import des mémoires Claude Code déjà écrites, après un plan et une confirmation. Sous-commande `memoires` (lecture seule) avec l'état de chaque fichier ; doublons probables détectés par ressemblance ou inclusion (seuil `near`).
- L'agent ne passe plus de base par défaut à `analyser` : il prend la base du serveur de la session (`CORTEXDB_PATH`), comme le script.

## Plugin harmonie 2026.11.24.5 (2026-11-24), convention version 2

- Miroir de la mémoire Claude Code (phase de transition : double écriture) : un crochet PostToolUse suit l'écriture des fichiers `.claude\projects\<projet>\memory\*.md` et demande à Claude d'écrire le même fait dans le cerveau local, selon la convention. `HARMONIE_MIROIR=0` le désactive.
- Retrait du bilan automatique (crochet Stop) : aucun crochet ne peut faire parler Claude à la fermeture d'une session. `/harmonie:bilan` reste sur demande.

## Plugin harmonie 2026.11.24.4 (2026-11-24), convention version 2

- Auteur = login Windows de la personne (%USERNAME%), normalisé : minuscules, sans accent, « . », « _ » et espace remplacés par « - ».
- Le crochet exige le login Windows de la session et donne la valeur attendue ; la migration garde les auteurs de la table.
- `analyser` prend le login Windows comme auteur par défaut et l'affiche ; l'agent et la skill ne demandent plus le login.

## Plugin harmonie 2026.11.24.3 (2026-11-24), convention version 2

- Bilan de session : un crochet Stop, une fois par session de travail (au moins 3 demandes et 15 appels d'outils), demande à Claude de proposer 1 à 5 faits à retenir dans le cerveau local. Rien n'est enregistré sans l'accord de la personne. `HARMONIE_BILAN=0` le désactive.
- Commande `/harmonie:bilan` : le même bilan, sur demande.

## Plugin harmonie 2026.11.24.2 (2026-11-24), convention version 2

- Paquet neutre : aucune donnée d'un poste ni d'un projet (exemples génériques dans la convention, l'agent, la skill et les tests). La construction refuse un paquet qui en contient.
- `--help` sur chaque sous-commande ; `analyser` et `migrer` refusent une base absente et affichent la base lue.
- Base par défaut de `analyser` et `migrer` : `CORTEXDB_PATH` s'il est défini, comme le crochet.
- L'agent ne cite que des données de la base analysée ; il demande le login de l'auteur par défaut, sans le supposer.

## Plugin harmonie 2026.11.24.1 (2026-11-24), convention version 2

- Premier paquet du plugin harmonie, pour le catalogue aoi : crochet PreToolUse, skill /harmonie:convention, agent harmonie:convention-cortexdb, script convention/convention.py.
- Les rapports d'analyse vont hors du plugin : %HARMONIE_RAPPORTS%, sinon Documents\harmonie\rapports de l'utilisateur.
- L'agent ne modifie jamais le plugin installé : une nouvelle nature devient une proposition pour l'IT (phase C).
- La migration finale est un geste de l'utilisateur : l'agent rend une procédure prête à copier.
- Un refus liste toutes les erreurs à corriger ensemble ; commande `lire` pour le texte d'un élément ; le crochet lit une entrée avec marque BOM et refuse un appel CortexDB illisible.

## Convention version 2 (2026-11-24)

- Règle d'auteur : author (document) ou user_id (mémoire) = login de l'atelier de la personne responsable, le même login que la clé thalamus th/<login>/<cerveau>. Une seule identité par personne.
- Nouvelle métadonnée obligatoire produit_par : claude-code, agent-relecture ou humain (liste producteurs).
- La règle d'auteur est hors du bloc convention : sur le serveur, le gateway thalamus pose l'auteur lui-même.
- Le crochet refuse un document sans author, une mémoire sans user_id, et un produit_par hors de la liste.

## Convention version 1 (2026-11-24)

- 12 natures : decision, fait, piege, preference, etat, plan, methode, relecture, resultats, reference, rappel, compte-rendu.
- Natures datées : decision, fait, etat, relecture, resultats, rappel, compte-rendu.
- 9 thèmes de départ : outils-cao, postes, outils-ia, developpement, travail-assistant, projets, mise-en-page, materiaux, administration.
- Thème d'attente : a-trier. Ressemblance : 0.8. Seuil d'émergence : 5.
- La nature procedure est fusionnée dans methode.
- Contrôle local par le crochet PreToolUse de Claude Code (convention.py garde).
