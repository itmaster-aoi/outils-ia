# Organisation des dossiers d'installation AOI

Étude du 28.10.2026, version 3. La version 2 intégrait des essais et une relecture adversariale. La version 3 remplace les 8 étiquettes de migration par une solution mixte : une étiquette qui lit les deux organisations, puis un script de migration lancé sur chaque poste. État : validée. Étiquette M réalisée (plugin 2026.10.28.3, voir « Réalisation de l'étiquette M ») ; aucun poste n'est migré.

## Objectif

Les outils de l'atelier s'installent aujourd'hui dans 14 emplacements (tableau ci-dessous). Aucune règle commune ne décide où va un fichier. Cette étude fixe une règle unique : **tout ce qui appartient à l'atelier va sous `%LOCALAPPDATA%\aoi`**. Les dossiers des logiciels hôtes reçoivent seulement un lanceur ou un manifeste.

Décisions de l'IT (28.10.2026) :
1. Le Python AOI reste dans `%LOCALAPPDATA%\aoi\python`. Les managed settings et les instructions de Claude citent ce chemin. `node` et `python-libs-<v>` restent aussi à la racine.
2. Le code des add-ins reste dans `%LOCALAPPDATA%\aoi\addins`. Les dossiers hôtes reçoivent un lanceur qui pointe vers ce dossier.
3. La migration choisit le chemin le plus sûr pour les postes déjà installés.
4. Solution mixte : le nouveau code arrive par une étiquette ; un script déplace les données sur chaque poste, Claude Code et logiciels hôtes fermés.
5. Aucun poste de l'atelier n'utilise de profil itinérant.

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

## Solution retenue : une étiquette, puis un script

### Pourquoi le code passe quand même par une étiquette

Les chemins utilisés sur un poste viennent du plugin (`.mcp.json`, `maj.py`, `archives_aoi.py`). Un script seul, sans nouveau plugin, casserait les serveurs : l'ancien `.mcp.json` pointerait vers des dossiers vides, et le `/regen` suivant réinstallerait tout aux anciens emplacements.

### Principe

1. **L'étiquette M (« bilingue ») lit les deux organisations.** Le module `chemins_aoi.py` lit le témoin de migration `journal\migration-dossiers.json`. Sans témoin, le poste utilise les anciens chemins. Avec le témoin, il utilise les nouveaux. Un poste non migré continue donc de fonctionner sans changement.
2. **Le script `migrer-dossiers` fait la migration**, une fois par compte Windows, quand Claude Code et les logiciels hôtes sont fermés. Il écrit le témoin en dernier.
3. **L'étiquette N (« nettoyage ») retire la lecture des anciens chemins**, quand tous les postes sont migrés. Le script de vérification le prouve poste par poste.

Comparaison avec la version 2 de l'étude :

| | Version 2 : étiquettes seules | Version 3 : étiquette, puis script |
|---|---|---|
| Étiquettes du plugin | 8 (A à H) | 2 (M et N), plus les étiquettes amont de keyshot-mcp et autocad-mcp |
| Migration des données | au démarrage du serveur, avec verrou, témoins et détection de divergence | par le script, Claude Code fermé : pas de session simultanée, pas d'écriture pendant la copie |
| Geste sur chaque poste | `/regen` et redémarrage, 8 fois | `/regen`, puis le script, puis le redémarrage |
| Risque principal | logique de migration complexe dans le lanceur | un poste non migré ; il fonctionne, et la ligne de démarrage le signale |

### Ce que contient l'étiquette M

- **`plugins/aoi/skills/regen/scripts/chemins_aoi.py`** : seule définition des dossiers, ancienne et nouvelle organisation, choisie par le témoin. Chaque point d'entrée (`maj.py`, `archives_aoi.py`, `lancer.py`, `migrer_dossiers.py`) ajoute `skills/regen/scripts` à `sys.path`, car le Python embarqué ne le fait pas (essai du 28.10.2026).
- **`plugins/aoi/lanceur/lancer.py`**, lancé par `controle/runtime/python.exe`, pour cortexdb et le serveur Revit. Il ne migre rien. Il choisit seulement le dossier du serveur et le chemin de la base selon `chemins_aoi`, pose les variables (`CORTEXDB_PATH`), et lance le serveur dans un Job Object (`KILL_ON_JOB_CLOSE`). Il n'écrit jamais sur la sortie standard et ignore Ctrl+C.
- **`archives_aoi.py`** installe les serveurs dans `serveurs\` sur un poste migré, et à l'ancien emplacement sinon. `conserver` cherche dans les deux.
- **`maj.py`** : `copier_addin` écrit la forme « lanceur » ou « pointeur » sur un poste migré, et la copie complète sinon. `--verifier-dossiers` affiche l'état. La ligne de démarrage affiche « dossiers à migrer : fermez Claude Code, puis lancez migrer-dossiers.cmd » sur un poste non migré.
- **`archives/construire.py`** cesse de réécrire `.mcp.json` : retirer le dictionnaire `MCP` et la réécriture (`construire.py:46`, `:97-103`).
- **Le script `migrer-dossiers.cmd`**, à la racine du plugin et du dépôt, à côté de `installer-poste.cmd`. Il lance `controle/runtime/python.exe` avec `migrer_dossiers.py` (le Python embarqué contient `sqlite3`, PowerShell non).
- **Les corrections trouvées par la relecture** :
  - `archive_addin` (`maj.py:171-173`) : passer par `effacer_si_libre` et ne jamais effacer la version désignée par un hôte ou un pointeur.
  - `archive_addin` (`maj.py:153`) : `with_suffix` coupe une version qui contient un point.
  - `finir()` (`maj.py:343-346`) : chaque étape est protégée ; un échec est affiché, la suite continue ; témoin `journal\finir-<version>.ok`.
  - `controle_si_besoin()` (`maj.py:375`) : un échec est affiché au lieu d'être ignoré.
  - `installer-poste.ps1` (lignes 423 et 449) : il appelle `--finir`.
  - `skills/regen/SKILL.md`, étape 2 : « catalogue à jour » ne suffit plus ; il faut aussi `--verifier-dossiers` sans écart.
  - Verrou `journal\regen.verrou` : un seul `/regen` à la fois.
- **Les nouvelles versions des add-ins KeyShot et AutoCAD** qui acceptent un pointeur (étiquettes amont, voir plus bas). Si elles ne sont pas prêtes, M part sans elles : KeyShot et AutoCAD restent en copie complète, et une étiquette suivante les ajoute.

### Réalisation de l'étiquette M (plugin 2026.10.28.3)

Décisions de l'IT du 28.10.2026 : M part sans KeyShot ni AutoCAD, et la base du serveur Revit reste en place.

| Point de M | État |
|---|---|
| `chemins_aoi.py`, `lancer.py`, `migrer-dossiers.cmd`, témoin, `--annuler`, détection de divergence | fait |
| Copie des serveurs, de la base cortexdb (contrôlée) et des journaux | fait |
| Add-in Revit en forme « pointeur » : manifeste `.addin` avec chemin absolu vers `aoi\addins`, copie complète gardée dans `journal\avant-migration\revit-2025`, choix `enabled` de `commandRegistry.json` repris à chaque version, remise en place par `--annuler` | fait ; le registre reste dans le dossier de la version, pas dans `donnees\revit` |
| Refus si `Revit.exe` est ouvert ; contrôle de l'espace libre | fait |
| Corrections de la relecture : `with_suffix`, `finir()` protégé et témoin, verrou de `/regen`, `controle_si_besoin()` | fait |
| Effacement d'une ancienne version d'add-in seulement après le passage de l'hôte à la nouvelle | fait |
| `revit-data.db` dans `donnees\revit` | reporté : le chemin est fixé dans le serveur compilé (`build/database/db.js:8`). Demande une nouvelle version de `lfoletti/mcp-servers-for-revit` |
| KeyShot et AutoCAD en forme « lanceur » ou « pointeur » ; copie de leurs réglages | reporté : demande des étiquettes amont de `keyshot-mcp` et `autocad-mcp` |
| `installer-poste.ps1` appelle `--finir` | non fait : `finir()` renvoie toujours 0 et l'installeur perdrait les échecs de son bilan. `--addins` couvre les add-ins |

L'étiquette `2026-10-28.2` contenait une partie de M sans ces ajouts. Elle a été supprimée avant tout déploiement.

À essayer sur le poste de test : l'avertissement de Revit sur les add-ins non signés quand `<Assembly>` change de chemin.

### Ce que fait le script `migrer-dossiers`

Le script travaille pour le compte Windows qui le lance. Il est idempotent : relancé, il reprend où il s'est arrêté.

1. **Contrôles préalables.** Il refuse de continuer et dit pourquoi si :
   - le plugin installé n'est pas au moins l'étiquette M ;
   - un de ces processus tourne pour ce compte : `claude.exe`, `cortexdb-mcp.exe`, `node.exe` du serveur Revit, `Revit.exe`, `acad.exe`, `accoreconsole.exe`, `Rhino.exe`, `keyshot.exe` (filtre `tasklist /FI "USERNAME eq ..."`) ;
   - l'espace libre est insuffisant pour les copies.
2. **Mode simulation par défaut.** Sans option, il affiche ce qu'il ferait. Avec `--appliquer`, il agit.
3. **Copies, jamais de déplacement :**
   - `~\.cortexdb\cortexdb.db` vers `donnees\cortexdb\` : copie par l'API `backup` de `sqlite3`, source ouverte en lecture seule, puis `PRAGMA integrity_check` et comparaison du nombre de lignes de chaque table ;
   - `revit-data.db` de la dernière version du serveur Revit vers `donnees\revit\`, avec le même contrôle ;
   - `pont-config.json` de `%LOCALAPPDATA%\keyshot-mcp`, `config.json` de `%LOCALAPPDATA%\autocad-mcp` ;
   - `imports.jsonl`, `demarrage.log`, `session.json` vers `journal\` ;
   - dossiers des serveurs `aoi\<nom>-<v>` vers `serveurs\<nom>-<v>`.
4. **Dossiers hôtes.** Il écrit les lanceurs et les pointeurs, et retire les copies complètes devenues inutiles. Avant de retirer un fichier, il en garde une copie dans `journal\avant-migration\`.
5. **Témoin.** Il écrit `journal\migration-dossiers.json` en dernier : date, compte, version du plugin, liste des copies, taille et date de modification de chaque source.
6. **Témoins dans les anciens dossiers.** Il écrit `MIGRE-VERS-AOI.txt` dans chaque ancien dossier de données. Il n'efface aucune donnée.
7. **Bilan.** Il affiche ce qui est fait, ce qui reste, et la consigne de redémarrer Claude Code.

Option `--annuler` : le script retire le témoin et remet les dossiers hôtes dans leur forme d'avant, depuis `journal\avant-migration\`. Le poste revient aux anciens chemins. **Attention** : les données écrites après la migration restent dans `donnees\` et ne sont pas recopiées vers les anciens dossiers. Le script le dit et donne la liste des fichiers concernés.

### Retour arrière de la console

Si la console revient à une étiquette antérieure à M, l'ancien plugin lit les anciens chemins. Les données écrites depuis la migration ne sont pas visibles.

1. Lancez `migrer-dossiers.cmd --annuler` avant de changer l'étiquette, si possible.
2. Si les anciennes données ont été modifiées après la migration, le script le détecte à la relance (date de modification comparée au témoin). Il s'arrête et demande une décision de l'IT. Il ne choisit jamais en silence.

## Détails par add-in

**KeyShot (étiquette amont keyshot-mcp)**
- Le lanceur dans `Scripts` calcule `%LOCALAPPDATA%` au moment de l'exécution et lit le pointeur dans le profil de l'utilisateur, car `%PUBLIC%` est commun à tous les comptes.
- `MSG_LANCER` exécute le script sans `__file__` (`server.py:33-36`). Le lanceur ne dépend donc pas de `__file__`. Il exécute le vrai pont avec `__file__` réglé (essai E5). `_chemin_source()` (`MCP start.py:1495-1503`) lit le pointeur, pour que `reload_bridge` recharge le vrai pont et non le lanceur.
- Le serveur lit `donnees\keyshot\pont-actif.json`, puis l'ancien chemin s'il manque. `.mcp.json` donne `KEYSHOT_MCP_FICHE` dans `env`.
- Le lanceur et le serveur vérifient la même version (`VERSION_PONT_ATTENDUE`), avec un message clair si elles diffèrent.
- `addin.json` reçoit `processus` (KeyShot).
- Les captures restent dans l'ancien dossier, signalées par `--verifier-dossiers`.

**AutoCAD (étiquette amont autocad-mcp)**
- `Extension.cs:84` lit le dossier du code dans le pointeur. Les 4 chemins `%LOCALAPPDATA%\autocad-mcp` (`Extension.cs:30`, `Job.cs:34`, `OutilsLot.cs:35`, `Config.cs:67`) passent par une seule fonction.
- Le pointeur porte une version de contrat. Si `Boot.dll` et le serveur ne correspondent pas, AutoCAD affiche un message dans sa ligne de commande.
- `processus` contrôle aussi `accoreconsole.exe`.
- À essayer avant publication : chargement depuis `%LOCALAPPDATA%` avec SECURELOAD à 1 et à 2.

**Revit (sans projet amont)**
- Le registre des commandes (`commandRegistry.json`) va dans `donnees\revit`, fusionné avec celui de la nouvelle version à chaque mise à jour. Reprendre l'ancien registre tel quel masquerait les commandes ajoutées.
- À essayer avant publication : l'avertissement de Revit sur les add-ins non signés réapparaît-il quand le chemin `<Assembly>` change à chaque version ?

**Rhino** : inchangé, copie complète.

## Essais du 28.10.2026

Tous les essais utilisent le Python embarqué `controle/runtime` (Python 3.12, sans `site`).

| Essai | Résultat | Conséquence |
|---|---|---|
| `CORTEXDB_PATH` avec un dossier personnel de test | la base est créée au chemin donné ; la vraie base est inchangée | la variable convient |
| `sqlite3` dans le Python embarqué | 3.49.1, API `backup` présente | copie possible sans librairie |
| E1 : lanceur Python qui enveloppe un serveur stdio (JSON UTF-8, message de 200 Ko) | octets identiques, 0,08 s pour 4 messages | lanceur possible |
| E2 : lanceur tué, comme quand Claude Code ferme | **le serveur reste orphelin** | Job Object obligatoire |
| E2b : même essai avec un Job Object (`KILL_ON_JOB_CLOSE`, `ctypes`) | le serveur s'arrête avec le lanceur | solution retenue |
| E3 : `backup` d'une base WAL pendant qu'un autre processus écrit | copie intègre, mais 70 lignes sur 400 | copier seulement quand aucun processus n'utilise la base ; d'où le script, Claude Code fermé |
| E4 : verrou `O_EXCL`, 20 démarrages simultanés | 1 seul gagnant | verrou de `/regen` |
| E5 : `exec` du pont KeyShot avec `__file__` réglé | le code voit le vrai chemin | lanceur KeyShot possible |
| E6 : processus `cortexdb-mcp.exe` sur ce poste | 2 en cours : une session ouverte depuis le 27.10 et la session actuelle | le script doit refuser tant qu'une session tourne |
| Import d'un module voisin avec le Python embarqué | **échec** : le dossier du script n'est pas dans `sys.path` | chaque point d'entrée ajoute son dossier |
| Profils Windows de ce poste | 4 comptes, aucun profil itinérant | le script tourne une fois par compte |
| Droits de `C:\ProgramData\aoi\guard\sitecustomize.py` | écriture : Système, Administrateurs, lauro seulement | défaut actuel, hors migration (voir plus bas) |

**Attention** : `cortexdb-mcp.exe` n'a pas d'option `--help`. Lancé sans variable, il ouvre et modifie la vraie base `~/.cortexdb` (constaté le 28.10.2026). Tout essai doit fixer `CORTEXDB_PATH` et un dossier personnel de test.

## Plusieurs comptes Windows sur un poste

- Chaque compte a son propre `%LOCALAPPDATA%\aoi` et lance le script pour lui-même. Le témoin est propre à chaque compte.
- Le contrôle des processus filtre par compte. Sinon, une session d'un autre compte bloquerait la migration.
- `%PUBLIC%\Documents\KeyShot Studio\Scripts` est commun : le lanceur KeyShot ne contient aucun chemin propre à un compte.
- Défaut actuel, pris en compte par l'IT le 28.10.2026 et traité hors de cette migration : seul le compte qui a installé le contrôle peut le mettre à jour dans `C:\ProgramData\aoi`.

## Profils itinérants

L'IT confirme le 28.10.2026 qu'aucun poste de l'atelier n'utilise de profil itinérant. Si l'atelier en introduit un jour, les décisions 2 et la place de la base cortexdb sont à revoir : les pointeurs de `%APPDATA%` voyageraient vers un poste où `%LOCALAPPDATA%\aoi\addins` diffère.

## Qui fait quoi

### Gestes humains

| Geste | Qui | Pourquoi |
|---|---|---|
| Mettre l'étiquette M, puis N, dans la console | IT | Claude n'a pas accès à la console ; c'est la décision de publier |
| Cloner keyshot-mcp et autocad-mcp sur leur étiquette et compiler l'add-in AutoCAD | IT | `importer_*.py` exige un clone fait hors de Claude Code |
| Taper `/aoi:regen` | chaque utilisateur | le crochet de démarrage ne met rien à jour lui-même |
| Fermer Claude Code et les logiciels hôtes, puis lancer `migrer-dossiers.cmd --appliquer` | chaque utilisateur, une fois par compte | le script exige que rien ne tourne ; une session Claude Code ne peut pas migrer sa propre base |
| Relancer Claude Code | chaque utilisateur | les serveurs se chargent seulement au démarrage |
| Ouvrir KeyShot, AutoCAD et Revit une fois après la migration | IT, sur le poste de test | Claude ne lance pas les logiciels hôtes ; il appelle ensuite lui-même l'outil d'état |
| Décider après une divergence de données | IT | choix entre deux versions de données |

Pour un designer : taper `/aoi:regen`, fermer Claude Code et ses logiciels, lancer `migrer-dossiers.cmd --appliquer`, relancer Claude Code. Une seule fois.

### Délégué à Claude, avec l'accord de l'IT pour chaque publication

- Écrire le code, le script, les tests et la documentation.
- Commiter, créer les étiquettes, publier les archives, pousser vers `lfoletti/*` et `itmaster-aoi/outils-ia`.
- Lancer `migrer-dossiers.cmd` en simulation et `maj.py --verifier-dossiers` sur le poste de test, puis lire le résultat.
- Après le redémarrage, appeler les outils MCP de contrôle (`memory_list_all`, `keyshot_status`, outil d'état AutoCAD).

### Délégué aux scripts

- `/regen` : installer le code de l'étiquette M, sans rien déplacer.
- `migrer-dossiers` : contrôler, copier, vérifier, écrire les lanceurs et le témoin.
- Ligne de démarrage : signaler un poste non migré, ou un `finir()` incomplet.
- `--verifier-dossiers` : donner l'état de chaque composant ; c'est la preuve avant l'étiquette N.

## Vérification

Sur le poste de test, avant de mettre M dans la console pour tous :

1. Installez M (`/aoi:regen`), sans migrer. Résultat attendu : tous les serveurs démarrent sur les anciens chemins ; la ligne de démarrage dit « dossiers à migrer ».
2. Lancez `migrer-dossiers.cmd` sans option. Résultat attendu : la liste des actions, rien n'est modifié.
3. Lancez-le avec `--appliquer`, une session Claude Code ouverte. Résultat attendu : refus, avec le nom du processus.
4. Fermez tout, puis lancez-le avec `--appliquer`. Résultat attendu : bilan sans échec ; `integrity_check` « ok » ; même nombre de lignes dans chaque table.
5. Relancez Claude Code. Résultat attendu : `/mcp` montre tous les serveurs connectés ; `memory_list_all` donne les mêmes souvenirs qu'avant ; `--verifier-dossiers` sans écart.
6. Ouvrez KeyShot, AutoCAD et Revit. Résultat attendu : leur outil d'état répond ; le code chargé vient de `aoi\addins`.
7. Fermez Claude Code et lancez `--annuler`, puis relancez Claude Code. Résultat attendu : retour aux anciens chemins, avec la liste des données écrites depuis la migration.
8. Relancez `--appliquer`. Résultat attendu : migration refaite, ou arrêt avec une demande de décision si les anciennes données ont changé.
9. Vérifiez qu'un Claude Code fermé ne laisse aucun `cortexdb-mcp.exe` orphelin.
10. Avec un second compte Windows du poste, refaites les étapes 4 et 5.

Avant l'étiquette N : `--verifier-dossiers` montre « migré » sur chaque compte de chaque poste. La ligne de démarrage note cet état dans `journal\demarrage.log`, que l'IT peut relever.
