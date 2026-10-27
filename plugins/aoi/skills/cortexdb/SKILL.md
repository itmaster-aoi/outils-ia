---
name: cortexdb
description: Mémoire durable de l'utilisateur dans CortexDB (serveur plugin:aoi:cortexdb, base locale). Utiliser quand l'utilisateur demande de retenir, mémoriser ou noter un fait, une préférence ou une décision, de se souvenir ou de retrouver ce qui a été dit dans une session précédente, ou tape /aoi:remember ou /aoi:recall. Ne pas utiliser pour la mémoire des fichiers de Claude Code (MEMORY.md) ni pour chercher dans le code.
---

<!-- Skill écrite par l'IT de l'atelier (AOI), 27.10.2026. Le serveur et les commandes viennent de
     liliang-cn/cortexdb v2.139.1 : voir plugins/aoi/mcp/cortexdb/README.md et VERSION-AOI.txt. -->

# CortexDB : mémoire durable

CortexDB garde des faits d'une session à l'autre. La base est un seul fichier sur le poste : `%USERPROFILE%\.cortexdb\cortexdb.db`. Le serveur `plugin:aoi:cortexdb` travaille sans service externe : la recherche se fait par mots (mode lexical).

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

1. Appelle l'outil `memory_save`.
2. Donne un `memory_id` stable et descriptif, par exemple `pref-unites-cotes`.
3. Écris un `content` court : une phrase, un fait.
4. Mets `scope=user` et `namespace=assistant`, sauf si l'utilisateur précise autre chose.
5. Confirme en une ligne ce qui est enregistré.

Si le fait est une connaissance de référence et pas une préférence, utilise `knowledge_save`.

## Retrouver

1. Développe la question en mots-clés et en synonymes. La recherche est lexicale : un mot absent du fait enregistré ne le trouve pas.
2. Appelle `knowledge_memory_recall`.
3. Si le résultat est vide, essaie `memory_search`, puis `knowledge_search`.
4. Résume ce qui est trouvé et cite les identifiants.
5. Si rien n'est trouvé, dis-le.

Un souvenir peut être dépassé. Vérifie dans le fichier ou le projet avant de donner un chiffre ou un chemin rappelé.

## Limites

- Les fonctions qui demandent un modèle de langage ou un service d'embeddings restent inactives. N'essaie pas de les activer.
- N'appelle pas le binaire `cortexdb-mcp.exe` en ligne de commande. Utilise les outils MCP.
- Le serveur partagé `cortexdb-grpc` n'est pas utilisé à l'atelier.
