---
name: cortexdb
description: Mémoire durable de l'utilisateur dans CortexDB (serveur plugin:aoi:cortexdb, base locale). Utiliser quand l'utilisateur demande de retenir, mémoriser ou noter un fait, une préférence ou une décision, de se souvenir ou de retrouver ce qui a été dit dans une session précédente, de faire le bilan d'une session à mémoriser, ou tape /aoi:remember ou /aoi:recall. Ne pas utiliser pour la mémoire des fichiers de Claude Code (MEMORY.md) ni pour chercher dans le code.
---

<!-- Skill de ce dépôt, version 4 du 24.11.2026 : identifiants, métadonnées et compartiment des mémoires
     selon la convention du composant memo (plugin aoi). Le serveur et les commandes viennent de liliang-cn/cortexdb v2.170.0 :
     voir plugins/aoi/mcp/cortexdb/README.md et VERSION-AOI.txt. -->

# CortexDB : mémoire durable

CortexDB garde des faits d'une session à l'autre. La base est un seul fichier sur le poste : `%USERPROFILE%\.cortexdb\cortexdb.db`.

Le serveur `plugin:aoi:cortexdb` n'appelle aucun modèle : ni service d'embeddings, ni modèle de langage. C'est toi qui fais ce travail, dans la session :
- avant une recherche, tu prépares les mots-clés, les reformulations et les entités ;
- avant un enregistrement, tu cherches les faits que le nouveau fait remplace ;
- à la demande, tu fais le bilan d'une session.

Le serveur cherche par mots (mode lexical) et par le graphe des entités. Un mot absent du fait enregistré ne le trouve pas, sauf par une entité commune.

## Convention de nommage (composant memo)

Toute écriture suit la convention commune de l'atelier, gardée par le composant memo du plugin aoi. Charge la skill `/aoi:memo` avant le premier enregistrement de la session. Un crochet du plugin aoi refuse une écriture hors convention : lis son message, corrige l'appel et relance-le.

En bref :
- identifiant `<nature>:<theme>:<sujet>`, mots en minuscules joints par des tirets, sans accent, sans date ni numéro de version ;
- métadonnées `nature`, `theme`, `status` (`current` ou `replaced`), `date` (AAAA-MM-JJ) pour une nature datée, `produit_par` (`claude-code` pour un texte que tu écris) ;
- auteur : `user_id` (mémoire) ou `author` (document) = le login Windows de la personne (`%USERNAME%`), normalisé (minuscules, sans accent, « . », « _ » et espace remplacés par « - ») ;
- compartiment des mémoires : `scope=user`, `user_id=<login>`, `namespace=assistant`, toujours, à l'écriture comme à la recherche. Le projet va dans la métadonnée `projet`, jamais dans le `namespace`.

## Compartiment des mémoires

Le serveur range chaque mémoire dans un compartiment, `memory:<scope>:<user_id>:<namespace>`. Une recherche de mémoire lit un seul compartiment. Sans filtre, elle lit `memory:global:default`, où la convention ne range aucune mémoire : le résultat est vide, même si la mémoire existe.

Donne donc toujours les 3 filtres `scope=user`, `user_id=<login>` et `namespace=assistant` à `memory_save`, `memory_search`, `knowledge_memory_recall` et `knowledge_memory_build_context_pack`. Le crochet du plugin aoi refuse un appel sans ces filtres et donne les valeurs. Les documents (`knowledge_save`, `knowledge_search`) n'ont pas de compartiment.

Les listes de natures et de thèmes sont dans `memo/convention.yaml` du plugin aoi. Ne les recopie pas de mémoire.

## Quand mémoriser

Mémorise un fait seulement si l'utilisateur le demande, ou s'il confirme ta proposition.

Mémorise :
- une préférence de travail (« réponses en français », « cotes en mm ») ;
- une décision et sa raison ;
- une convention d'équipe ou de projet.

Ne mémorise jamais :
- un mot de passe, un jeton, une clé ou un identifiant ;
- une donnée personnelle d'un client ou d'un collaborateur ;
- un contenu copié d'un fichier de projet. Mémorise le chemin et le fait, pas le contenu.

## Mémoriser

1. Cherche les faits proches avec `memory_search` (voir « Retrouver », étapes 1 et 2).
2. Si un fait trouvé dit la même chose avec une autre valeur, note son identifiant. Un fait sur le même sujet, sans contradiction, ne compte pas.
3. Appelle `memory_save` :
   - `memory_id` : selon la convention, par exemple `preference:travail-assistant:unites-cotes` ;
   - `content` : une phrase, un fait. Nomme les entités en toutes lettres (projet, logiciel, personne par son rôle) ;
   - `metadata` : `nature`, `theme`, `status`, `date` si la nature est datée, `produit_par`, et `projet` si le fait touche un projet ;
   - `scope=user`, `user_id` = le login de la personne, et `namespace=assistant` (section « Compartiment des mémoires ») ;
   - `supersedes` : les identifiants notés à l'étape 2. Le fait remplacé reste stocké, mais il n'est plus rappelé.
4. Confirme en une ligne ce qui est enregistré et ce qui est remplacé.

Si le fait est une connaissance de référence et pas une préférence, utilise `knowledge_save`, avec les mêmes règles (`knowledge_id`, `metadata`, `author`).

## Retrouver

1. Prépare le plan de recherche à partir de la question :
   - `keywords` : 5 à 15 mots-clés, avec les synonymes, les abréviations et les termes en français et en anglais ;
   - `alternate_queries` : 2 ou 3 reformulations de la question ;
   - `entity_names` : les entités que la question nomme (projet, logiciel, lieu).
2. Appelle `knowledge_memory_recall` avec `query`, ce plan, et les 3 filtres du compartiment : `scope=user`, `user_id=<login>`, `namespace=assistant`.
3. Si le résultat est vide, appelle `memory_search` avec le même plan et les mêmes filtres, puis `knowledge_search`.
   Avant de conclure « rien trouvé », contrôle les filtres de l'appel. Un résultat vide sans les filtres ne prouve rien.
4. Résume ce qui est trouvé et cite les identifiants.
5. Si rien n'est trouvé, dis-le.

Un souvenir peut être dépassé. Vérifie dans le fichier ou le projet avant de donner un chiffre ou un chemin rappelé.

## Bilan d'une session

Fais un bilan seulement si l'utilisateur le demande.

1. Relis la session. Relève les préférences, les décisions et les conventions durables. Ignore les étapes de travail et les essais abandonnés.
2. Montre la liste à l'utilisateur, un fait par ligne.
3. Mémorise les faits qu'il confirme, un par un, avec la procédure « Mémoriser ».

## Limites

- Ne configure pas de modèle externe : les variables `CORTEXDB_EMBED_*`, `CORTEXDB_LLM_*`, `CORTEXDB_RERANK_*` et `OPENAI_*` restent vides. Les outils qui exigent un modèle côté serveur (par exemple `import_agent_memory` avec les transcriptions de sessions) restent inactifs. Fais ce travail toi-même avec la procédure « Bilan d'une session ».
- N'appelle pas le binaire `cortexdb-mcp.exe` en ligne de commande. Utilise les outils MCP. Seule exception : la migration d'un cerveau par le script `memo/convention.py migrer`, que l'utilisateur lance lui-même, Claude Code fermé.
- Le serveur partagé `cortexdb-grpc` n'est pas utilisé.
