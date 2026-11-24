---
name: memo
description: Convention de nommage commune des cerveaux CortexDB de l'atelier oï (composant memo du plugin aoi). Utiliser avant toute écriture dans CortexDB (memory_save, knowledge_save, ingest_document, knowledge_update), quand un crochet refuse une écriture « Convention CortexDB », ou quand l'utilisateur demande quel identifiant, quelle nature ou quel thème donner à une note. Pour analyser ou migrer un cerveau entier, utiliser l'agent aoi:memo-analyse.
---

# Convention CortexDB de l'atelier

Le composant memo du plugin aoi garde une convention commune à tous les cerveaux CortexDB de l'atelier. Les cerveaux pourront ainsi être fusionnés ou séparés par thème (thalamus, fiche docs/upstream/13). Un crochet refuse toute écriture hors convention, avec la correction à faire.

La convention elle-même est dans le fichier `memo/convention.yaml` de ce plugin. Lis ce fichier pour connaître les listes à jour : natures, natures datées, thèmes, producteurs. Ne recopie jamais ces listes de mémoire.

## Lancement sans demande précise

Si `/aoi:memo` (ou `/memo`) est lancé sans demande précise, pose une seule question : « Que voulez-vous faire avec la mémoire centrale ? ». Propose ces choix, dans cet ordre :

1. **Écrire un élément** : suis la section « Écrire un élément ».
2. **Ingérer une mémoire dossier** : demande « tout » (tous les projets) ou le chemin d'un projet, puis suis la commande `/aoi:memo-importer` avec cette réponse. Ne devine pas la réponse. Pour « tout », la commande demande une confirmation avant de lancer la liste, puis montre la liste avant d'ingérer.
3. **Analyser ou migrer un cerveau** : passe la main à l'agent aoi:memo-analyse.

Ne propose pas « corriger un refus » : un refus du crochet se corrige au moment où il arrive (section « Quand le crochet refuse »).

## Écrire un élément

1. Choisis la **nature** : ce qu'est l'élément (décision, fait, piège, préférence, état…), pas de quoi il parle.
2. Choisis le **thème** : le domaine durable de l'atelier. Le projet n'est pas un thème : il va dans la métadonnée `projet`.
3. Écris le **sujet** : mots en minuscules joints par des tirets, sans accent, sans date ni numéro de version. Une nouvelle version réécrit le même identifiant.
4. Identifiant : `<nature>:<theme>:<sujet>`, par exemple `decision:postes:choix-du-navigateur`.
5. Métadonnées obligatoires :
   - `nature`, `theme`, `status` (`current` ou `replaced`) ;
   - `date` au format AAAA-MM-JJ pour une nature datée ;
   - `produit_par` : `claude-code` pour un texte que tu écris, `agent-relecture` pour une relecture par un agent tiers, `humain` pour un texte de la personne.
6. Auteur : `author` (document) ou `user_id` (mémoire) = le login Windows de la personne (`%USERNAME%`), normalisé : minuscules, sans accent, « . », « _ » et espace remplacés par « - » (`Jean.Dupont` devient `jean-dupont`). Lis-le dans l'environnement, ne le demande pas. Jamais le nom d'un agent ni d'une session. Le crochet refuse tout autre auteur et donne la valeur attendue.
7. Thème absent de la liste : `theme` = le thème d'attente de la convention, `theme_proposed` = le thème voulu, et l'identifiant `<nature>:<theme voulu>:<sujet>`. Ne crée pas de thème toi-même.

## Quand le crochet refuse

Lis le message : il dit ce qui manque. Corrige l'appel et relance-le. Ne contourne pas le crochet (pas d'écriture directe dans la base, pas d'autre outil).

## Ce qui n'est pas permis

- Modifier `convention.yaml` du plugin installé : il est remplacé à chaque mise à jour. Une nouvelle nature ou un nouveau thème passe par l'agent aoi:memo-analyse (proposition, validation de l'utilisateur, puis l'IT de l'atelier).
- Lancer la migration réelle d'un cerveau : c'est un geste de l'utilisateur, Claude Code fermé. L'agent aoi:memo-analyse lui donne la commande exacte.
