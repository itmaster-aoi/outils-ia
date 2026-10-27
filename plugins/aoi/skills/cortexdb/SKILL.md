---
name: cortexdb
description: Mémoire durable de l'utilisateur dans CortexDB (serveur plugin:aoi:cortexdb, base locale). Utiliser quand l'utilisateur demande de retenir, mémoriser ou noter un fait, une préférence ou une décision, de se souvenir ou de retrouver ce qui a été dit dans une session précédente, de faire le bilan d'une session à mémoriser, ou tape /aoi:remember ou /aoi:recall. Ne pas utiliser pour la mémoire des fichiers de Claude Code (MEMORY.md) ni pour chercher dans le code.
---

<!-- Skill écrite par l'IT de l'atelier (AOI), version 2 du 27.10.2026. Le serveur et les commandes viennent de
     liliang-cn/cortexdb v2.139.1 : voir plugins/aoi/mcp/cortexdb/README.md et VERSION-AOI.txt. -->

# CortexDB : mémoire durable

CortexDB garde des faits d'une session à l'autre. La base est un seul fichier sur le poste : `%USERPROFILE%\.cortexdb\cortexdb.db`.

Le serveur `plugin:aoi:cortexdb` n'appelle aucun modèle : ni service d'embeddings, ni modèle de langage. C'est toi qui fais ce travail, avec l'abonnement Claude de l'atelier :
- avant une recherche, tu prépares les mots-clés, les reformulations et les entités ;
- avant un enregistrement, tu cherches les faits que le nouveau fait remplace ;
- à la demande, tu fais le bilan d'une session.

Le serveur cherche par mots (mode lexical) et par le graphe des entités. Un mot absent du fait enregistré ne le trouve pas, sauf par une entité commune.

## Quand mémoriser

Mémorise un fait seulement si l'utilisateur le demande, ou s'il confirme ta proposition.

Mémorise :
- une préférence de travail (« réponses en français », « cotes en mm ») ;
- une décision et sa raison ;
- une convention de l'atelier ou d'un projet.

Ne mémorise jamais :
- un mot de passe, un jeton, une clé ou un identifiant ;
- une donnée personnelle d'un client ou d'un collaborateur ;
- un contenu copié d'un fichier de projet. Mémorise le chemin et le fait, pas le contenu.

## Mémoriser

1. Cherche les faits proches avec `memory_search` (voir « Retrouver », étapes 1 et 2).
2. Si un fait trouvé dit la même chose avec une autre valeur, note son identifiant. Un fait sur le même sujet, sans contradiction, ne compte pas.
3. Appelle `memory_save` :
   - `memory_id` : stable et descriptif, par exemple `pref-unites-cotes` ;
   - `content` : une phrase, un fait. Nomme les entités en toutes lettres (projet, logiciel, personne par son rôle) ;
   - `scope=user` et `namespace=assistant`, sauf si l'utilisateur précise autre chose ;
   - `supersedes` : les identifiants notés à l'étape 2. Le fait remplacé reste stocké, mais il n'est plus rappelé.
4. Confirme en une ligne ce qui est enregistré et ce qui est remplacé.

Si le fait est une connaissance de référence et pas une préférence, utilise `knowledge_save`.

## Retrouver

1. Prépare le plan de recherche à partir de la question :
   - `keywords` : 5 à 15 mots-clés, avec les synonymes, les abréviations et les termes en français et en anglais ;
   - `alternate_queries` : 2 ou 3 reformulations de la question ;
   - `entity_names` : les entités que la question nomme (projet, logiciel, lieu).
2. Appelle `knowledge_memory_recall` avec `query` et ce plan.
3. Si le résultat est vide, appelle `memory_search` avec le même plan, puis `knowledge_search`.
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
- N'appelle pas le binaire `cortexdb-mcp.exe` en ligne de commande. Utilise les outils MCP.
- Le serveur partagé `cortexdb-grpc` n'est pas utilisé à l'atelier.
