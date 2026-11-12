# Lumières, jour et nuit, ambiances, ensoleillement, rendus, contrôle, D5 Render

Testé sur D5 Lite pour Rhino 1.2.0.0017.

Deux familles d'outils :

- **Dans Rhino** (MCP Rhino, IronPython 2.7) : `d5lum.py` pour les lumières, `d5scene.py` pour le contrôle du document. Chargement comme `d5mat.py` : voir `materiaux.md`.
- **Hors de Rhino** (Python AOI) : les commandes de `d5lite.py` pour le ciel, les captures et les rendus.

## Lumières : `d5lum.py`

Faits vérifiés :

| Fait | Preuve |
| --- | --- |
| L'intensité de Rhino se relit à l'identique dans Lite (`brightness`) : 0,3 → 0,3 ; 50 → 50 | essai |
| L'intensité n'est pas bornée à 1. Une intensité de 1 est invisible. Ordre de grandeur utile : 100 à 5000 | Captures 03 et 06 |
| Les watts et les lumens de Rhino ne sont pas repris | Relecture à 1,0 après réglage |
| Une lumière éteinte dans Rhino disparaît de Lite | `target_not_found`, compteur à 0 |
| Types repris : ponctuelle, spot, rectangulaire (`area`), linéaire (`line`) | Lecture de `light_type` |
| La lumière directionnelle n'est pas reprise | `target_not_found` |
| La couleur de Rhino est reprise | Relecture à l'identique |

| Fonction | Rôle |
| --- | --- |
| `lister(calque=None)`, `lire(selection)` | Lumières, avec `id_lite` (GUID en majuscules pour la CLI) |
| `creer(type, nom, position, cible, intensite, couleur, angle_cone, longueur, largeur, calque)` | Crée une lumière reprise par Lite |
| `modifier(selection, intensite, couleur, allumee, position, angle_cone, facteur)` | Règle une ou plusieurs lumières |
| `allumer(selection, calque)`, `eteindre(selection, calque)` | Allume ou éteint |
| `dupliquer(selection, deplacement, copies)` | Copie en série |
| `supprimer(selection)` | Supprime |
| `etat()`, `restaurer(etats)` | Garde et remet l'état de toutes les lumières |
| `definir_mode(selection, jour, nuit, intensite_nuit, calque)` | Fixe l'état d'une lumière dans chaque mode |
| `mode("jour")`, `mode("nuit")` | Met toutes les lumières dans l'état du mode |
| `audit()` | Lumières non reprises, intensités invisibles, noms en double |

`selection` est un nom, un GUID, une liste, ou `None` pour toutes les lumières.

## Mode jour et nuit

Le mode a deux moitiés. Faites les deux.

| Moitié | Passage en nuit | Retour au jour |
| --- | --- | --- |
| Ciel (CLI) | `d5lite.py nuit` | `d5lite.py jour` |
| Lumières (Rhino) | `d5lum.mode("nuit")` | `d5lum.mode("jour")` |

- `nuit` enregistre d'abord le ciel de jour dans `ambiances\_avant_nuit.json`. En mode HDRI, il met l'intensité du ciel et du soleil à 0. En mode GEO, il met le soleil à −15°.
- `jour` remet ce ciel. `jour --ambiance <nom>` applique une autre ambiance.
- Sans réglage, une lumière est éteinte le jour et allumée la nuit. `definir_mode` change cette règle par lumière : par exemple un plafonnier allumé le jour, ou une intensité propre à la nuit.
- Les réglages du mode sont enregistrés dans le texte utilisateur de chaque lumière (`d5.jour`, `d5.nuit`), donc dans le fichier `.3dm`.
- Un matériau émissif éclaire aussi la scène de nuit.
- Vérifié : capture `06_mode_nuit.png` (ciel noir, ombres portées des lumières), puis `07_retour_jour.png`.

## Ambiances

Une ambiance contient le ciel, le post-traitement et les réglages de rendu, dans un fichier JSON du dossier `ambiances\` (ou `D5LITE_AMBIANCES`).

| Commande | Rôle |
| --- | --- |
| `d5lite.py ambiance lire` | Affiche l'ambiance actuelle. Lecture seule |
| `d5lite.py ambiance enregistrer <nom>` | Écrit `ambiances\<nom>.json` |
| `d5lite.py ambiance appliquer <nom> [--parties ciel,post,rendu]` | Applique, relit, et donne les écarts |
| `d5lite.py ambiance lister` | Liste les ambiances enregistrées |

- Une ambiance se reprend dans un autre projet : copiez le fichier JSON.
- `appliquer` retourne `ecarts` : les champs dont la valeur relue diffère de la valeur voulue. Une liste vide prouve l'application.
- Le fichier HDRI doit exister sur le poste. Sinon l'ambiance garde le HDRI en place.

## Ensoleillement

```
python d5lite.py ensoleillement --latitude 46.99 --longitude 6.93 --date 2026-06-21 --heures 08:00,12:00,16:00 --decalage-utc 2 --dossier <dossier>
```

- La commande calcule l'altitude et l'azimut du soleil, règle le ciel GEO, capture la vue, puis remet l'ambiance d'origine.
- `--decalage-utc` : 2 en heure d'été suisse, 1 en heure d'hiver.
- `--nord` : angle du nord géographique par rapport à l'axe +Y de Rhino, en degrés, sens horaire. Défaut : 0.
- Convention vérifiée par capture : azimut 0 = axe +Y de Rhino, 90 = axe +X.
- Précision du calcul : 0,5°. Vérifié à Neuchâtel : 66,4° au solstice d'été, 19,6° au solstice d'hiver.
- Une heure où le soleil est sous l'horizon n'est pas capturée.
- **Avant l'étude, éteignez les lumières artificielles** (`d5lum.eteindre()`) : une lumière forte masque les ombres du soleil.

## Série de rendus

1. `d5lite.py preparer-rendus <dossier> [--scenes a,b] [--qualite high] [--format png] [--type image]` écrit un workflow par scène. Aucun rendu ne part.
2. Montrez à l'utilisateur la liste des scènes et la commande retournée (`commande_a_lancer_par_l_utilisateur`).
3. L'utilisateur lance `d5lite.py lancer-rendus <dossier>`. La commande rend les scènes l'une après l'autre, attend la fin de chaque rendu et écrit `bilan_rendus.json`.
4. Lisez `bilan_rendus.json`, puis chaque image.

- Une scène de Lite est une vue nommée de Rhino.
- `lancer-rendus` saute une image déjà présente. Une relance reprend donc une série interrompue.
- Lancer la commande vaut accord de l'utilisateur pour tous les rendus du dossier.
- Le chemin de sortie doit être absolu. L'outil le convertit.

## Contrôle avant rendu

Faites les deux contrôles, puis donnez un seul bilan à l'utilisateur.

| Côté | Commande | Vérifie |
| --- | --- | --- |
| D5 Lite | `d5lite.py controle` | Connexion, version de la CLI, scènes, rendu en cours, ciel de nuit sans lumière, fichier HDRI, exposition, qualité |
| Rhino | `d5scene.rapport()` | Fichier enregistré, vues nommées, objets sans matériau, textures introuvables, textures sans taille réelle, lumières invisibles ou non reprises, plugin D5 |

Les deux retournent `pret`, `alertes` (à corriger avant le rendu) et `infos` (à signaler).

## Réglage sur une image de référence

1. Capturez la vue : `d5lite.py capturer <fichier.png>`.
2. Lisez la capture et l'image de référence. Dites ce qui diffère : cadrage, lumière, teinte.
3. `d5lite.py comparer <capture> <reference>` donne des mesures (luminance, contraste, saturation, canaux) et des pistes de réglage.
4. Réglez un seul champ avec `regler`. Recapturez. Recommencez, cinq tours au plus.

- Les pistes sont des ordres de grandeur, pas des valeurs à appliquer telles quelles.
- La comparaison ne juge ni le cadrage ni les matériaux. Votre lecture des deux images reste nécessaire.
- Gardez la même caméra et la même taille de capture pendant tout le réglage.
- L'exposition automatique fausse une comparaison de luminosité. Notez son état, et gardez-le.

## Passage vers D5 Render

**Non testé.** Ce qui suit vient de la documentation de D5 et des commandes présentes dans le plugin.

- `d5scene.preparer_d5render()` contrôle le document et donne les étapes. Lecture seule.
- `d5scene.donnees_lite()` lit ce que D5 Lite enregistre dans le document : ciel, post-traitement, réglages par vue. D5 Render lit ces données. Elles sont à jour après un enregistrement du fichier Rhino.
- Selon D5, le passage va de Lite vers Render, pour les matériaux, les lumières, les modèles et le ciel. Rien ne revient de D5 Render vers Rhino.
- Commandes du plugin dans Rhino : `D5LiveSyncStart`, `D5LiveSyncSendModel`, `D5LiveSyncSendLights`, `D5LiveSyncSendScenes`, `D5LiveSyncExport`.
- N'exécutez pas ces commandes sans D5 Render ouvert : leur comportement dans ce cas n'est pas connu.
- Dites à l'utilisateur que ce passage n'est pas vérifié, à chaque fois.

## Approbations

- Lecture, capture, ambiance, jour, nuit, ensoleillement : `safeWrite` sur le ciel et le post-traitement. Exécutez, puis montrez le résultat.
- `d5lum` : modifications ordinaires du modèle Rhino, annulables. Annoncez la portée avant `supprimer` et avant `mode` si plus de 20 lumières changent.
- Rendus : l'utilisateur lance `lancer-rendus`.
