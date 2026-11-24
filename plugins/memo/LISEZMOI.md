# memo : convention de nommage des cerveaux CortexDB

Le plugin memo garde la convention de nommage commune à l'atelier oï pour les cerveaux CortexDB. Il reprend la forme de thalamus (github.com/lfoletti/thalamus, `gateway/convention/`) : la même convention sert en local et sur le serveur, et les cerveaux pourront être fusionnés ou séparés par thème.

Le plugin est publié dans le catalogue aoi (`itmaster-aoi/outils-ia`, dossier `plugins/memo`). Il dépend du plugin aoi : Python AOI (`%LOCALAPPDATA%\aoi\python\python.exe`) et serveur CortexDB (`plugin:aoi:cortexdb`).

## Contenu du plugin

| Fichier | Rôle |
|---|---|
| `convention/convention.yaml` | La convention : natures, natures datées, thèmes, thème d'attente, producteurs. Source unique. |
| `convention/convention.py` | Le script : crochet de contrôle, vérification, analyse d'un cerveau, migration, tests. Bibliothèque standard seulement. |
| `convention/indices.json` | Les indices qui aident l'analyse à proposer une nature et un thème. Ne fait pas partie de la convention. |
| `hooks/hooks.json` | Le crochet `PreToolUse` qui contrôle les écritures CortexDB, et le crochet `PostToolUse` du miroir de la mémoire Claude Code. |
| `commands/bilan.md` | La commande `/memo:bilan` : proposer les faits de la session à retenir. |
| `commands/importer-memoire.md` | La commande `/memo:importer-memoire tout` ou `<chemin du projet>` : importer les mémoires Claude Code déjà écrites. |
| `skills/convention/SKILL.md` | La skill `/memo:convention` : comment nommer un élément avant de l'écrire. |
| `agents/convention-cortexdb.md` | L'agent `memo:convention-cortexdb` : le processus ci-dessous, phase par phase, avec un arrêt à chaque validation. |
| `CHANGELOG.md` | Les changements de la convention et du plugin. |

Les rapports d'analyse sont des données de l'utilisateur. Ils ne sont jamais écrits dans le plugin : ils vont dans `%MEMO_RAPPORTS%` si la variable existe, sinon dans `%USERPROFILE%\Documents\memo\rapports\<cerveau>-<date>\`.

Dans les commandes ci-dessous, `<plugin>` est le dossier du plugin installé, par exemple `%USERPROFILE%\.claude\plugins\cache\aoi\memo\<version>`. L'agent trouve ce dossier lui-même et écrit les commandes avec les vrais chemins.

## Règles de la convention

- Identifiant : `<nature>:<theme>:<sujet>`, en mots minuscules joints par des tirets, sans accent.
- Métadonnées obligatoires : `nature`, `theme`, `status` (`current` ou `replaced`), `produit_par`.
- Une nature datée demande aussi `date` au format AAAA-MM-JJ.
- Un thème inconnu : `theme=<thème d'attente>`, `theme_proposed=<nouveau-theme>`, et l'identifiant `<nature>:<nouveau-theme>:<sujet>`.
- Un document `theme:<sujet>` déclare un nouveau thème.
- Un élément qui existe déjà garde son identifiant, mais ses métadonnées sont contrôlées à chaque réécriture.
- Le projet n'est pas un thème : il va dans la métadonnée `projet`.
- Le sujet ne porte ni date ni numéro de version : une nouvelle version réécrit le même identifiant.
- Auteur : `author` (document) ou `user_id` (mémoire) = login Windows de la personne (`%USERNAME%`), normalisé : minuscules, sans accent, « . », « _ » et espace remplacés par « - » (`Jean.Dupont` devient `jean-dupont`). Une seule identité par personne. Sur un poste, le crochet exige le login Windows de la session. Ce n'est ni une métadonnée ni une collection : c'est le champ que la recherche et la provenance de thalamus affichent. Sur le serveur, le gateway le pose depuis la clé `th/<login>/<cerveau>`.
- Métadonnée `produit_par` = l'agent qui a écrit le texte : `claude-code`, `agent-relecture` ou `humain`.

## Contrôle des écritures

Le crochet lance `convention.py garde` avant chaque appel à `knowledge_save`, `ingest_document`, `memory_save` et `knowledge_update` (avec métadonnées) du serveur `plugin:aoi:cortexdb`. Une écriture hors convention est refusée, avec la correction à faire. Si `convention.yaml` est illisible, toute écriture est refusée.

Pour contrôler un identifiant sans rien écrire :

```
& "$env:LOCALAPPDATA\aoi\python\python.exe" "<plugin>\convention\convention.py" verifier decision:postes:exemple --auteur jdupont --meta '{\"nature\":\"decision\",\"theme\":\"postes\",\"status\":\"current\",\"date\":\"2026-11-24\",\"produit_par\":\"humain\"}'
```

Limite : le crochet ne contrôle pas les copies presque identiques (seuil `near`). Seul le gateway thalamus le fait.

## Alimenter le cerveau local : miroir de la mémoire Claude Code

Phase de transition : double écriture. Claude Code tient sa propre mémoire, un fichier par fait dans `%USERPROFILE%\.claude\projects\<projet>\memory\` (indexés par `MEMORY.md`). Il l'écrit au moment où le fait apparaît, pas à la fermeture. Chaque écriture de ce fichier produit aussi une entrée dans le cerveau CortexDB local :

1. Le crochet `PostToolUse` (`convention.py miroir`) suit `Write`, `Edit` et `MultiEdit` sur ces fichiers, `MEMORY.md` exclu.
2. Il lit l'en-tête du fichier (`name`, `type`) et donne à Claude une consigne immédiate : écrire le même fait par `memory_save`, avec l'identifiant proposé selon la convention, le login Windows comme auteur, `produit_par=claude-code` et `source` = chemin du fichier.
3. Claude fait l'écriture par le serveur CortexDB de la session. Le crochet de convention la contrôle.
4. Si le cerveau contient déjà un élément de même `source`, Claude réécrit cet élément.

Le crochet ne fait pas l'écriture lui-même : un second processus sur la même base, session ouverte, fausserait l'index de recherche du serveur de la session.

Correspondance des types : `user` → `preference` ; `feedback` → `preference`, ou `decision` pour un choix et sa raison ; `project` → `decision`, `fait` ou `etat` selon le texte ; `reference` → `reference`.

Limites : le cerveau reçoit seulement ce que la mémoire Claude Code retient ; une mémoire supprimée par une commande shell n'est pas suivie ; les mémoires écrites avant l'installation ne sont pas copiées. Pour le désactiver sur un poste : variable d'environnement `MEMO_MIROIR=0`.

Sur demande, `/memo:bilan` propose en plus 1 à 5 faits de la session ; rien n'est enregistré sans l'accord de la personne.

### Importer les mémoires déjà écrites

`/memo:importer-memoire tout` (tous les projets) ou `/memo:importer-memoire <chemin du projet>` (un projet ; le chemin du dossier `memory` est aussi accepté) :

1. La commande liste, en lecture seule, les fichiers de mémoire (`convention.py memoires`), avec l'identifiant proposé et l'état : `nouveau`, `a-mettre-a-jour`, `deja-importe` ou `doublon-probable`.
2. Un fichier est un doublon probable quand son texte est déjà dans le cerveau : ressemblance de Jaccard ou inclusion des trigrammes de mots au moins égale au seuil `near` (0,8). Il n'est pas importé, sauf demande de la personne.
3. Claude montre le plan et demande une seule confirmation. Il écrit ensuite chaque fichier par `memory_save`, selon la convention, avec `source` = chemin du fichier. Un second import ne crée pas de doublon.

Le passage vers un cerveau partagé du bureau viendra avec le serveur thalamus (`th_add`, relu par un curateur).

## Processus : analyser un cerveau et obtenir un livrable à jour

Le livrable d'un cerveau est sa table de renommage relue et validée, `<rapports>\<cerveau>-<date>\renommage.csv`, faite avec la dernière version de la convention. L'agent `memo:convention-cortexdb` applique ce processus.

1. **Analyser le cerveau avec la convention actuelle.** La base doit être sur C: (copie si besoin). L'analyse lit la base en lecture seule et dure quelques secondes.

   ```
   & "$env:LOCALAPPDATA\aoi\python\python.exe" "<plugin>\convention\convention.py" analyser "<chemin>\cortexdb.db" --nom <cerveau> [--auteur-defaut <login>] [--alias <ancien-login>=<login>]
   ```

   `--auteur-defaut` donne le login des éléments sans auteur lisible ; sans cette option, c'est le login Windows normalisé de la session. `--alias` réunit 2 identités de la même personne (répéter l'option au besoin). Résultat : `inventaire.csv` (une ligne par élément, avec une proposition) et `synthese.md` (bilan, éléments sans nature, natures candidates).

2. **Proposer de nouvelles natures si nécessaire.** Lire les sections « Éléments sans nature » et « Natures candidates » de `synthese.md`. Une nouvelle nature est proposée seulement si toutes ces conditions sont vraies :
   - elle dit ce qu'est un document (sa forme ou son rôle), pas de quoi il parle ;
   - au moins 5 éléments (seuil `emerge`), dans un ou plusieurs cerveaux, n'entrent dans aucune nature existante ;
   - ce n'est pas un projet ni un thème ;
   - son nom suit la règle des noms et n'est pas proche d'une nature existante.

3. **Faire valider les natures par l'utilisateur.** Aucune nature n'entre dans `convention.yaml` sans sa validation.

4. **Mettre la convention à jour** (seulement si l'étape 3 ajoute ou retire une nature ou un thème). La convention est commune au bureau : elle change dans le dépôt de développement de memo, tenu par l'IT.
   1. Modifier `convention/convention.yaml` et augmenter `version` de 1.
   2. Ajouter les indices de la nouvelle nature dans `convention/indices.json`.
   3. Écrire l'entrée de `CHANGELOG.md`.
   4. Lancer les tests : `convention.py tests`. Résultat attendu : `OK`.
   5. Commiter, puis publier une nouvelle version du plugin (voir « Publier »).
   6. Relancer l'étape 1 sur chaque cerveau déjà analysé.

5. **Proposer la table de renommage.** Copier `inventaire.csv` vers `renommage.csv` dans le même dossier, puis relire chaque ligne :
   - les lignes `a-classer` reçoivent une nature et un thème ;
   - les lignes de confiance `moyenne` sont vérifiées ;
   - les séries (`fusionner`) et les doublons sont confirmés ;
   - les lignes à supprimer prennent l'action `supprimer`.

6. **Faire valider la table par l'utilisateur.** Une ligne peut donner un texte nouveau dans la colonne `contenu` (chemin relatif au dossier de la table, par exemple `contenus\x.md`).

7. **Migrer le cerveau.** La migration écrit par le serveur CortexDB (`cortexdb-mcp.exe`), jamais dans la base SQLite directement. La migration finale est un geste de l'utilisateur : l'agent lui donne les commandes exactes.
   1. Simuler (lecture seule, à tout moment) :

      ```
      & "$env:LOCALAPPDATA\aoi\python\python.exe" "<plugin>\convention\convention.py" migrer "<rapports>\<cerveau>-<date>\renommage.csv" --simuler
      ```

      Résultat attendu : `problèmes : 0`, et un fichier `plan-migration-<heure>.txt` à relire.
   2. Fermer Claude Code. Sur la base par défaut, la migration refuse de partir si un serveur CortexDB tourne.
   3. Lancer la même commande sans `--simuler`. Le script sauvegarde la base dans `%USERPROFILE%\.cortexdb\sauvegardes\`, vérifie que le serveur lit la bonne base, écrit et relit chaque nouvel élément, puis supprime les anciens. Il écrit `journal-migration-<heure>.jsonl`, avec l'ancien contenu entier de chaque élément.
   4. Relancer avec `--simuler`. Résultat attendu : `Écritures : 0 ; suppressions : 0`.
   5. Relancer l'analyse : toutes les lignes sont `conforme`.

   Pour revenir en arrière : fermer Claude Code, puis copier la sauvegarde sur `%USERPROFILE%\.cortexdb\cortexdb.db`.

   Ce que la migration garde : contenu, titre, source, métadonnées utiles, namespace, portée, importance, liens des mémoires vers les entités du graphe. Ce qu'elle retire : les métadonnées que la convention remplace (`categorie`, `superseded_by`…) et les clés internes (`_chunk_size`…). Une base autre que la base par défaut (`--base`) sert aux essais sur une copie.

8. **Propager la convention** : copier le bloc `convention:` dans le `rights.yaml` de chaque cerveau du serveur thalamus. Le plugin memo porte la même version sur tous les postes.

## Tests

```
& "$env:LOCALAPPDATA\aoi\python\python.exe" "<plugin>\convention\convention.py" tests
```

Les tests couvrent les refus (forme, nature, thème, status, date, auteur, producteur), le crochet, la lecture seule sur C:, le dossier des rapports hors du plugin, les propositions de l'analyse, les séries et les collisions, et la planification de la migration.

## Publier (IT de l'atelier)

Le dépôt de développement de memo contient le plugin à sa racine, plus les dossiers `rapports/` (données de l'IT) et `integration/` (consignes pour le dépôt `outils-ia`), qui ne sont pas publiés.

1. Lancer `powershell -NoProfile -ExecutionPolicy Bypass -File "<dépôt>\preparer-paquet.ps1"`. Résultat : `dist\memo\`, sans chemin personnel.
2. Suivre `integration\INTEGRATION.md`.
