---
name: d5-lite-rhino
description: Piloter D5 Lite (plugin de rendu temps réel dans Rhino 8) depuis Claude. Utiliser quand l'utilisateur demande de lire ou de régler une scène D5 Lite - ciel, soleil, HDRI, exposition, post-traitement, caméra, scènes, capture de la vue, rendu d'image - ou de régler une lumière affichée dans D5 Lite. Ne pas utiliser pour D5 Render et ses projets .drs, ni pour SketchUp ou Revit.
---

# D5 Lite pour Rhino

Ce skill pilote D5 Lite par sa CLI officielle `D5LiteWorkflowCli.exe` (Bêta) et par le serveur MCP Rhino.
Il repose sur 98 cas de test (81 opérations) exécutés sur D5 Lite pour Rhino 1.2.0.0017.
Le détail par opération est dans `references/operations.md`.

## Deux outils, deux rôles

D5 Lite affiche le modèle Rhino en direct. Le modèle appartient à Rhino. L'image appartient à Lite.

| Besoin | Outil |
| --- | --- |
| Lister les lumières, obtenir leur GUID | MCP Rhino |
| Créer, régler, allumer, éteindre une lumière ; mode jour et nuit côté lumières | MCP Rhino, avec `scripts/d5lum.py` |
| Contrôler le document avant un rendu | MCP Rhino, avec `scripts/d5scene.py` |
| Créer, déplacer, supprimer un objet | MCP Rhino |
| Créer, régler, affecter, convertir un matériau ; orienter une texture | MCP Rhino, avec `scripts/d5mat.py`. Voir `references/materiaux.md` |
| Démarrer D5 Lite | MCP Rhino : commande `D5LiteStart` |
| Lire l'état de Lite | `scripts/d5lite.py` |
| Régler le ciel, le post-traitement, la caméra, les scènes, le rendu | `scripts/d5lite.py` |
| Capturer la vue, lancer un rendu | `scripts/d5lite.py` |

## L'outil `scripts/d5lite.py`

Lancez-le avec le Python AOI : `%LOCALAPPDATA%\aoi\python\python.exe`. Il utilise la bibliothèque standard seulement.
Il trouve la CLI seul : variable `D5_LITE_WORKFLOW_CLI`, puis registre, puis `%APPDATA%\D5 Lite for Rhino\engine`.

| Commande | Rôle |
| --- | --- |
| `etat` | Contrôle la connexion à Lite. Lecture seule |
| `aide <mot>` | Cherche une opération dans l'aide de la CLI |
| `operation <type>` | Donne la cible, les paramètres et le risque d'une opération |
| `lire <type> [--cible JSON] [--params JSON]` | Exécute une lecture. Refuse tout autre risque |
| `instantane [--lumieres GUID,GUID]` | Lit l'état complet : scènes, caméra, ciel, post-traitement, rendu, lumières |
| `regler <type> --params JSON --lecture <type> --champ <chemin> [--cible JSON]` | Écrit une valeur, la relit, donne un verdict |
| `executer <workflow.json> [--risque-max] [--confirme]` | Exécute un workflow de plusieurs opérations |
| `capturer <fichier.png> [--taille]` | Capture la vue de Lite |
| `ambiance lire`, `enregistrer <nom>`, `appliquer <nom>`, `lister` | Ciel, post-traitement et réglages de rendu, dans un fichier réutilisable |
| `nuit`, `jour` | Ciel de nuit, puis retour au ciel de jour |
| `ensoleillement --latitude --longitude --date --heures --decalage-utc --dossier` | Captures à plusieurs heures d'une journée |
| `preparer-rendus <dossier>`, `lancer-rendus <dossier>` | Série de rendus, un par scène. L'utilisateur lance la seconde |
| `controle` | Contrôle avant rendu, côté D5 Lite |
| `comparer <capture> <reference>` | Mesure l'écart entre deux images et donne des pistes de réglage |

Modules à exécuter dans Rhino, par le MCP Rhino :

| Module | Rôle | Référence |
| --- | --- | --- |
| `scripts/d5mat.py` | Matériaux : création, affectation par calque, objet, bloc ou face, textures, échelle réelle, conversion | `references/materiaux.md` |
| `scripts/d5lum.py` | Lumières : création, réglage, mode jour et nuit | `references/ambiances.md` |
| `scripts/d5scene.py` | Contrôle du document avant rendu, préparation du passage vers D5 Render | `references/ambiances.md` |

Lisez la référence d'un module avant de l'utiliser.

L'outil enchaîne `workflow validate`, `workflow plan`, le contrôle du risque et `workflow execute` avec un reçu neuf.
Il garde le workflow et le reçu de chaque écriture dans `journal_d5lite\` (ou `D5LITE_JOURNAL`).

Exemple :

```
python scripts/d5lite.py regler lite.postprocess.patch.exposure --params "{\"exposure\": 0.2}" --lecture lite.postprocess.read.exposure --champ exposure --cible "{\"kind\": \"postprocess\"}"
```

Verdicts de `regler` : `OK`, `SANS EFFET` (valeur inchangée), `ECART`, `ECHEC`, `REFUSE`.

## Ordre de travail

1. Lancez `etat`. Résultat attendu : `"connecte": true` et `"contrats_testes": true`. Si `contrats_testes` vaut `false`, D5 Lite a changé depuis les tests : prévenez l'utilisateur et vérifiez chaque écriture.
2. Si Lite ne répond pas, vérifiez que Rhino est ouvert, que `mcpstart` est lancé, puis exécutez `D5LiteStart` par le MCP Rhino. Relancez `etat` : le premier contrôle peut échouer pendant le chargement.
3. Lancez `instantane` pour connaître l'état de départ. Gardez cette sortie : elle sert à remettre les valeurs.
4. Si l'opération n'est pas dans `references/operations.md`, lancez `aide <mot>` puis `operation <type>`.
5. Pour une valeur simple, utilisez `regler`. Pour une suite d'opérations, écrivez un workflow et utilisez `executer`.
6. Donnez à l'utilisateur la valeur avant, la valeur après et le verdict.
7. Pour un réglage visuel, capturez la vue avant et après avec `lite.screenshot.capture`, puis lisez les deux images.

## Règles

- **`applied: true` ne prouve pas l'effet.** Une écriture est faite quand la relecture le confirme. `regler` fait cette relecture.
- **N'inventez rien.** Le nom d'une opération, un paramètre et un identifiant viennent de l'aide de la CLI, d'une lecture ou de l'utilisateur.
- **Identifiant d'une lumière :** le GUID de l'objet Rhino, en majuscules, sans accolades. `/Instance/...` est la forme de SketchUp : elle échoue avec Rhino.
- **Lumière de Rhino :** réglez-la dans Rhino avec `d5lum.py`. Les opérations `lite.light.patch.*` sont acquittées par Lite et restent sans effet. L'intensité de Rhino passe telle quelle dans Lite : une intensité de 1 est invisible, visez 100 à 5000.
- **Chemins :** D5 Lite demande un chemin absolu pour une capture ou un rendu. Un chemin relatif est accepté sans erreur, et le fichier n'apparaît pas.
- **Passage vers D5 Render :** non testé. Dites-le à l'utilisateur. Voir `references/ambiances.md`.
- **Scènes :** une scène de Lite est une vue nommée de Rhino. `lite.scene.create`, `rename`, `update` et `delete` modifient le document Rhino. Prévenez l'utilisateur avant.
- **Sélection de scène :** `lite.scene.select` change aussi le rapport d'image du rendu. Relisez les réglages de rendu ensuite.
- **Unités :** Lite compte en mètres, avec les axes Y et Z échangés par rapport à Rhino. Un point Rhino `(x, y, z)` en mm se lit `[x/1000, z/1000, y/1000]`.
- **Un workflow s'arrête à la première opération en échec.** Isolez les lectures qui dépendent du type de l'objet : `coneAngle` (spot), `size` (surface, linéaire, disque).
- **N'utilisez pas `su.*` ni `su-lite.*`.** Ces espaces de noms visent SketchUp. Ils échouent avec `su_lite_rpc_unavailable`.
- **Matériaux :** D5 Lite lit les matériaux de rendu de Rhino. Utilisez `scripts/d5mat.py` dans Rhino, pas les opérations `lite.material.*` : elles retournent `material_editor_closed` avec Rhino. Lisez `references/materiaux.md` avant toute action sur un matériau.
- **Affectation d'un matériau :** n'écrivez jamais `objet.RenderMaterial = materiau` dans un script Rhino. Cette ligne écrase une entrée de la table des matériaux, et Lite ne reçoit pas le changement. Utilisez `d5mat.affecter_objets`, `affecter_calque` ou `affecter_faces`.
- Travaillez sur le disque `C:` seulement.

## Approbations

Lisez le risque dans le plan (`risque` dans la sortie de l'outil), pas dans le nom de l'opération.

| Risque | Opérations | Règle |
| --- | --- | --- |
| `readOnly` | Toutes les lectures | Aucune demande |
| `safeWrite` | Ciel, post-traitement, caméra, réglages de rendu, capture | Aucune demande. Montrez le résultat après |
| `safeWrite` sur les scènes | `lite.scene.create`, `rename`, `update`, `parameters.paste` | Demandez : ces opérations modifient le document Rhino |
| `confirmWrite` | Suppression de scène, annulation, matériaux, fermeture de Lite | Montrez le plan. Exécutez après l'accord, avec `--confirme` |
| Rendu | `lite.render.job.start` | Préparez le workflow. L'utilisateur lance la commande |

`--confirme` déclare l'accord de l'utilisateur à la CLI. Ne le passez jamais sans cet accord.

## Rendu

1. Faites le contrôle avant rendu : `controle`, et `d5scene.rapport()` dans Rhino.
2. Lancez `preparer-rendus <dossier>` avec la qualité (`low` ou `high`), le format (`png` ou `jpg`) et le type (`image` ou `panorama`).
3. Donnez à l'utilisateur la commande retournée, sur une ligne. Il la lance lui-même.
4. Lisez `bilan_rendus.json` dans le dossier, puis chaque image.

La qualité fixe la résolution : `low` donne 2560 px de large, `high` donne 3840 px. Un panorama mesure 4096 × 2048 px.
Durées sur la scène de test : 10 à 13 s en `low`, 30 s en `high`, 17 s pour un panorama. Un projet réel demande plus de temps.

## Erreurs courantes

| Code | Sens | Action |
| --- | --- | --- |
| `lite_rpc_unavailable` | Lite ne répond pas | Vérifiez Rhino, puis `D5LiteStart`. Attendez la fin du chargement |
| `target_not_found` | Identifiant de lumière inconnu | Reprenez le GUID dans Rhino, en majuscules |
| `invalid_target_type` | L'opération ne vaut pas pour ce type de lumière | Lisez `light_type` d'abord |
| `scene_not_found` | `sceneId` inconnu | Relisez `lite.scene.list` |
| `material_editor_closed` | Éditeur de matériaux fermé | Demandez à l'utilisateur de l'ouvrir |
| `missing_requirement`, `confirmation_required` | Accord non déclaré | Obtenez l'accord, puis `--confirme` |
| `render_job_not_active` | Aucun rendu à annuler | Aucune action |
| `executionState: unknown` | La requête a pu s'exécuter | Ne relancez pas. Relisez la scène d'abord |

## Limites

- CLI en Bêta. Après une mise à jour de D5 Lite, rejouez les essais du dossier `essais/` (voir `essais/LISEZMOI.md`) avant de vous fier à ce skill.
- La CLI ne crée ni lumière ni géométrie avec Rhino. Les modules Rhino du skill créent les lumières et les matériaux. Pas de placement d'asset.
- La lumière directionnelle de Rhino n'est pas reprise par Lite.
- Pas de vidéo. Pas de résolution de rendu réglable.
- Pas de réglage de matériau par la CLI avec Rhino. Le module `d5mat.py` le fait dans Rhino.
- `lite.status.read`, `lite.diagnostics.run`, `lite.light.read.visibility` et `lite.render.sync` ne sont pas disponibles.
