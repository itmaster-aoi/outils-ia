# Organisation des dossiers d'installation AOI

Étude du 28.10.2026, version 2 : après des essais et une relecture adversariale. État : validée dans son principe. La migration n'a pas commencé.

## Objectif

Les outils de l'atelier s'installent aujourd'hui dans 14 emplacements (tableau ci-dessous). Aucune règle commune ne décide où va un fichier. Cette étude fixe une règle unique : **tout ce qui appartient à l'atelier va sous `%LOCALAPPDATA%\aoi`**. Les dossiers des logiciels hôtes reçoivent seulement un lanceur ou un manifeste.

Décisions :
1. Le Python AOI reste dans `%LOCALAPPDATA%\aoi\python`. Les managed settings et les instructions de Claude citent ce chemin. `node` et `python-libs-<v>` restent aussi à la racine.
2. Le code des add-ins reste dans `%LOCALAPPDATA%\aoi\addins`. Les dossiers hôtes reçoivent un lanceur qui pointe vers ce dossier.
3. La migration choisit le chemin le plus sûr pour les postes déjà installés.

## État actuel (28.10.2026)

| Emplacement | Contenu | Qui impose le dossier |
|---|---|---|
| `%LOCALAPPDATA%\aoi\python`, `python-libs-<v>`, `node` | Python AOI, librairies ajoutées, Node AOI | l'atelier |
| `%LOCALAPPDATA%\aoi\cortexdb-server-<v>` | serveur cortexdb | l'atelier |
| `%LOCALAPPDATA%\aoi\revit-server-<v>` | serveur Revit, avec sa base `revit-data.db` dans le dossier du programme (`build/database/db.js:8`) | l'atelier |
| `%LOCALAPPDATA%\aoi\addins\<slug>-<v>` | archives d'add-ins décompressées | l'atelier |
| `%LOCALAPPDATA%\aoi\imports.jsonl`, `demarrage.log`, `session.json` | journaux et état | l'atelier |
| `%LOCALAPPDATA%\aoi\keyshot` | ancien réglage KeyShot, plus lu depuis keyshot-mcp 1.0.0 | l'atelier |
| `%LOCALAPPDATA%\keyshot-mcp` | état du pont, réglages, journal, captures | projet keyshot-mcp |
| `%LOCALAPPDATA%\autocad-mcp` | configuration, journal, profil de console | projet autocad-mcp |
| `%USERPROFILE%\.cortexdb` | base de mémoire | réglage par défaut de cortexdb |
| `C:\ProgramData\aoi\guard`, `whitelist.txt` | contrôle des imports | managed settings |
| `~\.claude\plugins\cache\aoi\aoi\<v>` | plugin, avec les `libs/` de rhino et keyshot | Claude Code |
| `%APPDATA%\Autodesk\Revit\Addins\2025` | add-in Revit, copie complète | Revit |
| `%APPDATA%\Autodesk\ApplicationPlugins\aoi-autocad-mcp.bundle` | add-in AutoCAD, copie complète | AutoCAD |
| `%APPDATA%\McNeel\Rhinoceros\packages\8.0` | add-in Rhino, copie complète | Rhino |
| `%PUBLIC%\Documents\KeyShot Studio\Scripts` | pont KeyShot, copie complète, commun à tous les comptes du poste | KeyShot |

## Structure cible

```
%LOCALAPPDATA%\aoi\
  python\  python-libs-<v>\  node\        inchangés (décision 1)
  serveurs\<nom>-<v>\                     cortexdb, revit
  addins\<slug>-<v>\                      code des add-ins, source unique (décision 2)
  donnees\<serveur>\                      configuration, journaux, état, bases
  journal\                                imports.jsonl, demarrage.log, session.json, témoins
C:\ProgramData\aoi\guard\, whitelist.txt  seule exception machine
```

## Exceptions qui restent

| Emplacement | Raison | Ce qui y reste |
|---|---|---|
| `C:\ProgramData\aoi` | `PYTHONPATH` des managed settings et `._pth` de l'archive Python AOI 2026-10-15 | contrôle des imports |
| `~\.claude\plugins\cache\aoi` | Claude Code ; `libs/` à côté de `run.py`, imposé par le contrôle des imports (`_is_local`) | plugin |
| `%APPDATA%\McNeel\Rhinoceros\packages\8.0` | le gestionnaire de paquets de Rhino attend le `.rhp` dans ce dossier ; l'autre voie passe par le registre, que `/regen` évite | copie complète |
| `%APPDATA%\Autodesk\Revit\Addins\2025` | Revit | le manifeste `.addin`, avec un chemin absolu vers `aoi\addins` |
| `%APPDATA%\Autodesk\ApplicationPlugins\aoi-autocad-mcp.bundle` | AutoCAD n'accepte un bundle que dans `ApplicationPlugins` | `PackageContents.xml`, `AoiAutoCad.Boot.dll`, un pointeur |
| `%PUBLIC%\Documents\KeyShot Studio\Scripts` | KeyShot | `MCP start.py` réduit à un lanceur, `MCP stop.py` |

## Essais du 28.10.2026

Tous les essais utilisent le Python embarqué `controle/runtime` (Python 3.12, sans `site`). Script : hors dépôt, dans le dossier de travail de la session.

| Essai | Résultat | Conséquence pour l'étude |
|---|---|---|
| `CORTEXDB_PATH` avec un dossier personnel de test | la base est créée au chemin donné ; rien dans `.cortexdb` ; la vraie base est inchangée | la variable convient |
| `sqlite3` dans le Python embarqué | 3.49.1, API `backup` présente | copie possible sans librairie |
| E1 : lanceur Python qui enveloppe un serveur stdio (JSON UTF-8, message de 200 Ko) | octets identiques, 0,08 s pour 4 messages | le lanceur est possible ; les tubes sont hérités sans redirection explicite |
| E2 : lanceur tué, comme quand Claude Code ferme | **le serveur reste orphelin** | Job Object obligatoire |
| E2b : même essai avec un Job Object (`KILL_ON_JOB_CLOSE`, `ctypes`) | le serveur s'arrête avec le lanceur | solution retenue |
| E3 : `backup` d'une base WAL pendant qu'un autre processus écrit | copie intègre, mais 70 lignes sur 400 : les écritures suivantes sont perdues | copier seulement si aucun processus n'utilise la base |
| E4 : verrou `O_EXCL`, 20 démarrages simultanés | 1 seul gagnant | verrou retenu |
| E5 : `exec` du pont KeyShot avec `__file__` réglé | le code voit le vrai chemin | lanceur KeyShot possible |
| E6 : processus `cortexdb-mcp.exe` sur ce poste | 2 en cours : une session ouverte depuis le 27.10 et la session actuelle | plusieurs sessions simultanées : cas réel |
| Import d'un module voisin avec le Python embarqué | **échec** : le dossier du script n'est pas dans `sys.path` | chaque point d'entrée ajoute son dossier, comme `maj.py:30` |
| Profils Windows de ce poste | 4 comptes, aucun profil itinérant | plusieurs comptes : cas réel ; itinérance à confirmer sur les autres postes |
| Droits de `C:\ProgramData\aoi\guard\sitecustomize.py` | écriture : Système, Administrateurs, lauro ; les autres comptes ont seulement la lecture | un autre compte ne peut pas mettre le contrôle à jour (défaut actuel, indépendant de la migration) |

**Attention** : `cortexdb-mcp.exe` n'a pas d'option `--help`. Lancé sans variable, il ouvre et modifie la vraie base `~/.cortexdb` (constaté le 28.10.2026). Tout essai doit fixer `CORTEXDB_PATH` et un dossier personnel de test.

## Principes de sûreté

1. **Ajouter avant de retirer.** Une étiquette installe le nouvel emplacement à côté de l'ancien. Elle n'efface jamais un dossier qu'une session en cours, un hôte ouvert ou une ancienne étiquette peut encore utiliser. Le code actuel ne respecte pas ce principe : `archive_addin` efface les autres versions d'un add-in sans contrôler l'hôte (`maj.py:171-173`). L'étiquette A corrige ce défaut.
2. **Copier les données, ne jamais les déplacer.** L'ancienne base reste en place. Elle est ouverte en lecture seule pour la copie (`?mode=ro`). Un témoin `MIGRE-VERS-AOI.txt` y indique la date, la destination, la taille et la date de modification de la source au moment de la copie.
3. **Migrer une base par une règle unique, au démarrage du serveur :**
   1. Si la nouvelle base a son témoin « migration terminée », le lanceur l'utilise toujours, même si d'autres processus tournent.
   2. Sinon, il prend le verrou `donnees\<serveur>\migration.verrou` (`O_EXCL`). S'il ne l'obtient pas, il démarre sur l'ancienne base.
   3. Avec le verrou, il revérifie le témoin. Il contrôle ensuite qu'aucun processus du même serveur ne tourne pour le même compte (`tasklist /FI "USERNAME eq ..."`). Si un processus tourne, il démarre sur l'ancienne base et réessaie au démarrage suivant.
   4. Sinon, il copie vers `<base>.tmp`, contrôle `PRAGMA integrity_check` et le nombre de lignes, fait `os.replace`, puis écrit le témoin. Il libère le verrou.
4. **Détecter une divergence, ne jamais choisir en silence.** Si l'ancienne base a été modifiée après la copie (retour arrière de la console, puis nouvel aller), le lanceur garde la nouvelle base. Il note l'écart dans `journal\` et la ligne de démarrage l'affiche. L'IT décide de la reprise.
5. **Un composant par étiquette.** Seule l'étiquette A, qui ne change rien de visible, peut partir avec B. En cas de problème, la console revient à l'étiquette précédente.
6. **Retour arrière possible jusqu'au nettoyage.** Les anciens dossiers de programmes restent en place jusqu'à l'étiquette H. Un `/regen` vers une ancienne étiquette retrouve donc ses chemins.
7. **Respecter la règle de `/regen`.** `skills/regen/scripts/maj.py`, `controle/runtime/python.exe` et `--finir` ne bougent pas. Chaque nouvelle forme d'`addin.json` reste lisible par le plus ancien `maj.py` en service : une fiche « pointeur » garde `archive` et `destination`, et un ancien `maj.py` fait alors une copie complète, qui fonctionne.
8. **Prouver que la nouvelle version a fini.** `finir()` écrit le témoin `journal\finir-<version>.ok`. S'il manque, `--demarrage` affiche « relancez /aoi:regen ». C'est le cas d'un poste antérieur à 2026.10.15.2 (sans `--finir`) ou d'un `/regen` interrompu.
9. **Effacer seulement ce qui est libre.** Toute suppression passe par `effacer_si_libre()` (`archives_aoi.py:64-73`). Un dossier sans fichier ouvert (par exemple le pont KeyShot en `.py`) n'est pas protégé par ce test : il est effacé seulement si aucun pointeur ne le désigne.
10. **Un seul `/regen` à la fois.** Verrou `journal\regen.verrou`. Un second `/regen` s'arrête avec un message.

## Pièce centrale : module de chemins et lanceur de serveurs

- **`plugins/aoi/skills/regen/scripts/chemins_aoi.py`** : seule définition des dossiers (`AOI`, `SERVEURS`, `ADDINS`, `DONNEES`, `JOURNAL`) et des anciens chemins connus. Chaque point d'entrée (`maj.py`, `archives_aoi.py`, `lancer.py`) ajoute `skills/regen/scripts` à `sys.path` avant de l'importer. Un test lance chaque script avec `controle/runtime/python.exe`.
- **`plugins/aoi/lanceur/lancer.py`**, lancé par `${CLAUDE_PLUGIN_ROOT}/controle/runtime/python.exe`, pour cortexdb et le serveur Revit :
  1. Il lit la fiche du serveur et trouve `serveurs\<nom>-<v>`. Si ce dossier manque, il prend l'ancien `aoi\<nom>-<v>`.
  2. Il migre la base selon le principe 3.
  3. Il pose les variables du serveur (`CORTEXDB_PATH` ; pour Revit, la variable de sa base quand le serveur la lira).
  4. Il lance le serveur dans un Job Object (`KILL_ON_JOB_CLOSE`), avec les flux standard hérités, et renvoie son code de sortie.
  5. Il n'écrit jamais sur la sortie standard. Ses messages vont dans `journal\lanceur.log`.
  6. Il ignore Ctrl+C et laisse le serveur s'arrêter.
- Le serveur keyshot n'utilise pas ce lanceur : il est lancé par le Python AOI avec `-I -S`. `.mcp.json` lui donne `KEYSHOT_MCP_FICHE` dans `env`.
- **`archives/construire.py` doit cesser de réécrire `.mcp.json`** : retirer le dictionnaire `MCP` et la réécriture (`construire.py:46`, `:97-103`). Sinon, la construction suivante remplace le lanceur par le chemin de l'exécutable. Un test vérifie la forme de `.mcp.json`.

## Étapes de migration

| Étiquette | Contenu | Projet amont |
|---|---|---|
| A, socle | `chemins_aoi.py` ; `finir()` crée `serveurs\`, `donnees\`, `journal\` et écrit son témoin ; `--demarrage` lit le témoin ; `session.json` et `demarrage.log` dans `journal\`, avec lecture de l'ancien emplacement ; `maj.py --verifier-dossiers` ; verrou de `/regen` ; corrections ci-dessous | non |
| B, cortexdb | serveur dans `serveurs\` ; `.mcp.json` passe par `lancer.py cortexdb` ; migration de la base (principe 3) ; textes `skills/cortexdb/SKILL.md` et `mcp/cortexdb/README.md` à jour | non |
| C, serveur Revit | serveur dans `serveurs\`, par le lanceur ; `conserver` cherche aussi dans les anciens chemins ; la base est reprise au démarrage par le lanceur, et non pendant `/regen` (la session en cours l'utilise) | non ; plus tard, une variable pour la base dans le serveur Revit |
| D, KeyShot | code du pont dans `addins\keyshot-<v>\` ; lanceur dans `Scripts` ; données dans `donnees\keyshot` ; `processus` ajouté à `addin.json` | keyshot-mcp, nouvelle étiquette |
| E, AutoCAD | bundle réduit à `Boot.dll`, `PackageContents.xml` et un pointeur ; liste `retirer` pour l'ancienne copie complète ; données dans `donnees\autocad` | autocad-mcp, nouvelle étiquette |
| F, add-in Revit | `.addin` seul, avec un chemin absolu vers `addins\revit-2025-<v>` ; registre des commandes dans `donnees\revit` | non |
| G, journal des imports | le contrôle écrit `journal\imports.jsonl` ; copie atomique du contrôle (`.tmp`, puis `os.replace`) | non |
| H, nettoyage | effacement des anciens dossiers de programmes libres et non désignés par un pointeur ; les anciennes données sont signalées, jamais effacées automatiquement ; déclenché aussi quand le catalogue est à jour | non |

Corrections incluses dans l'étiquette A :
- `archive_addin` (`maj.py:171-173`) : passer par `effacer_si_libre` et ne jamais effacer la version désignée par l'hôte ou par un pointeur.
- `archive_addin` (`maj.py:153`) : `with_suffix` coupe une version qui contient un point.
- `finir()` (`maj.py:343-346`) : une exception dans `copier_addin` (fichier verrouillé) arrête la suite. Chaque étape est protégée, et un échec est affiché.
- `controle_si_besoin()` (`maj.py:375`) : un échec est affiché dans la ligne de démarrage, au lieu d'être ignoré.
- `installer-poste.ps1` (lignes 423 et 449) : il appelle `--finir`, sinon un poste neuf n'a ni dossiers, ni pointeurs, ni témoin.
- Étape 2 de `skills/regen/SKILL.md` : « catalogue à jour » ne suffit plus ; il faut aussi `--verifier-dossiers` sans écart.

### Détails par add-in (D, E, F)

**KeyShot (D)**
- Le lanceur dans `Scripts` calcule `%LOCALAPPDATA%` au moment de l'exécution. Il lit le pointeur dans le profil de l'utilisateur, car `%PUBLIC%` est commun à tous les comptes.
- `MSG_LANCER` exécute le script sans `__file__` (`server.py:33-36`). Le lanceur ne dépend donc pas de `__file__`. Il exécute le vrai pont avec `__file__` réglé (essai E5). `_chemin_source()` (`MCP start.py:1495-1503`) lit le pointeur, pour que `reload_bridge` recharge le vrai pont et non le lanceur.
- Le serveur lit `donnees\keyshot\pont-actif.json`, puis l'ancien chemin s'il manque : un pont lancé avant la mise à jour reste joignable.
- Le lanceur et le serveur vérifient la même version (`VERSION_PONT_ATTENDUE`), avec un message clair si elles diffèrent.
- Reprise : `pont-config.json` est copié. Les captures restent dans l'ancien dossier, signalées par `--verifier-dossiers`.

**AutoCAD (E)**
- `Extension.cs:84` lit le dossier du code dans le pointeur. Les 4 chemins `%LOCALAPPDATA%\autocad-mcp` (`Extension.cs:30`, `Job.cs:34`, `OutilsLot.cs:35`, `Config.cs:67`) passent par une seule fonction.
- Le pointeur porte une version de contrat. Si `Boot.dll` et le serveur ne correspondent pas, AutoCAD affiche un message dans sa ligne de commande, et pas seulement dans `serveur.log`.
- `processus` contrôle aussi `accoreconsole.exe`, qui peut verrouiller les DLL.
- À essayer avant publication : chargement depuis `%LOCALAPPDATA%` avec SECURELOAD à 1 et à 2.

**Revit (F)**
- Le registre des commandes (`commandRegistry.json`) va dans `donnees\revit`. Aujourd'hui, la copie de l'archive l'écrase et le nouveau registre gagne (`maj.py:278-282`). Reprendre l'ancien registre tel quel masquerait les commandes ajoutées : il faut le fusionner.
- L'ancienne copie complète `Addins\2025\revit_mcp_plugin` est retirée par une liste `retirer`.
- À essayer avant publication : l'avertissement de Revit sur les add-ins non signés réapparaît-il quand le chemin `<Assembly>` change à chaque version ?

## Plusieurs comptes Windows sur un poste

- Chaque compte a son propre `%LOCALAPPDATA%\aoi`. Le seul dossier partagé est `C:\ProgramData\aoi`, et `%PUBLIC%\Documents\KeyShot Studio\Scripts`.
- La détection des processus filtre par compte. Sinon, le cortexdb d'un autre compte bloque la migration indéfiniment.
- Défaut actuel, pris en compte par l'IT le 28.10.2026 et à traiter hors de cette migration : seul le compte qui a installé le contrôle peut le mettre à jour dans `C:\ProgramData\aoi`. Les droits du dossier doivent permettre la mise à jour, ou l'installation doit passer par un compte administrateur.

## Profils itinérants

L'IT confirme le 28.10.2026 qu'aucun poste de l'atelier n'utilise de profil itinérant. Les décisions 2 et B restent donc valables.

Si l'atelier introduit un jour des profils itinérants, ces décisions sont à revoir : les pointeurs de `%APPDATA%` (Revit, AutoCAD) voyageraient vers un poste où `%LOCALAPPDATA%\aoi\addins` n'a pas la même version, et la mémoire cortexdb ne suivrait plus l'utilisateur.

## Qui fait quoi

Règle : un geste reste humain seulement si Claude ou un script ne peut pas le faire, ou si une règle de l'atelier l'interdit.

### Gestes humains

| Geste | Qui | Pourquoi |
|---|---|---|
| Mettre l'étiquette dans la console | IT | Claude n'a pas accès à la console ; c'est la décision de publier |
| Cloner un projet amont sur son étiquette et compiler l'add-in (D, E) | IT | `importer_*.py` exige un clone fait hors de Claude Code |
| Fermer KeyShot, Revit, AutoCAD ou Rhino avant `/aoi:regen` | chaque utilisateur | un hôte ouvert verrouille ses fichiers ; le script met l'add-in « en attente » et ne ferme jamais l'application |
| Taper `/aoi:regen` | chaque utilisateur | le crochet de démarrage ne met rien à jour lui-même |
| Redémarrer Claude Code | chaque utilisateur | les serveurs se chargent seulement au démarrage |
| Ouvrir l'hôte une fois après D, E, F | IT, sur le poste de test | Claude ne lance pas les logiciels hôtes ; il appelle ensuite lui-même l'outil d'état |
| Décider d'une reprise après une divergence de base (principe 4) | IT | choix entre deux versions de données |
| Décider d'effacer les anciennes données (H) | chaque utilisateur | ces données lui appartiennent |

Pour un designer, une étiquette demande au plus : fermer ses logiciels hôtes, taper `/aoi:regen`, redémarrer Claude Code.

### Délégué à Claude, avec l'accord de l'IT pour chaque publication

- Écrire le code, les tests et la documentation.
- Commiter, créer les étiquettes, publier les archives, pousser vers `lfoletti/*` et `itmaster-aoi/outils-ia`.
- Lancer `/aoi:regen` et `maj.py --verifier-dossiers` sur le poste de test, puis lire le résultat.
- Après le redémarrage, appeler les outils MCP de contrôle (`memory_list_all`, `keyshot_status`, outil d'état AutoCAD).
- Faire les essais de sessions simultanées et de retour arrière sur le poste de test.

### Délégué aux scripts, sans geste sur les postes

- Créer `serveurs\`, `donnees\`, `journal\` et les témoins.
- Installer chaque serveur et chaque add-in au nouvel emplacement, sans effacer l'ancien.
- Migrer les bases au premier démarrage sûr, et signaler une divergence.
- Écrire les lanceurs et les pointeurs dans les dossiers hôtes.
- Afficher l'état des dossiers à la fin de `/aoi:regen` et dans la ligne de démarrage.
- Effacer les anciens dossiers de programmes libres (H).

## Vérification de chaque étiquette

Socle commun :
1. Lancez `/aoi:regen`. Le bilan se termine par l'état des dossiers (`--verifier-dossiers`).
2. Redémarrez Claude Code.
3. Tapez `/mcp`. Résultat attendu : le serveur de l'étiquette est connecté.

Essais en plus, une seule fois, sur le poste de test :

| Étiquette | Essai |
|---|---|
| A | chaque script lancé avec `controle/runtime/python.exe` importe `chemins_aoi` ; `construire.py` laisse `.mcp.json` intact |
| B | `memory_list_all` donne les mêmes souvenirs qu'avant ; 2 sessions démarrées au même moment ne migrent qu'une fois ; une session ouverte après la migration voit un souvenir écrit par la première ; le lanceur tué ne laisse pas de `cortexdb-mcp.exe` orphelin ; mesure du temps de démarrage avec la vraie base ; retour arrière, écriture d'un souvenir, nouvel aller : la divergence est signalée |
| C | la base Revit est la même avant et après ; le lanceur tué ne laisse pas de processus orphelin |
| D, E, F | ouvrir l'hôte et appeler son outil d'état ; le code chargé vient de `aoi\addins` ; `/regen` avec l'hôte ouvert ne casse pas l'add-in chargé ; E : SECURELOAD 1 et 2 ; F : avertissement de signature |
| G, H | un ancien dossier encore désigné par un pointeur n'est pas effacé |
