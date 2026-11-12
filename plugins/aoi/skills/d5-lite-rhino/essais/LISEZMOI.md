# Essais du skill d5-lite-rhino

Rejouez ces essais après chaque mise à jour de D5 Lite, avant de vous fier au skill.
La commande `d5lite.py etat` signale une mise à jour : `contrats_testes` vaut alors `false`.

## Préparation

1. Ouvrez un document vide, en millimètres, dans Rhino 8.
2. Tapez `mcpstart` dans Rhino.
3. Par le MCP Rhino, construisez la scène d'essai :

```python
import sys
sys.path.insert(0, r"<dossier du skill>\essais")
import scene_essai
reload(scene_essai)
print(scene_essai.construire())
```

4. Lancez `D5LiteStart` dans Rhino. Attendez la fin du chargement.

## Campagne de la CLI

```
python campagne.py robustesse post ciel rendu camera lumiere scene asset divers
```

- Utilisez le Python AOI.
- Durée : 85 s. Aucun rendu ne part.
- Résultats : `%TEMP%\d5lite_essai\resultats\<domaine>.json`.
- Les cas `confirmWrite` (suppression de scène, annulation) demandent `--confirme`, après l'accord de l'utilisateur.
- Sans `--confirme`, le domaine `scene` laisse une vue nommée `audit_scene` dans Rhino. Supprimez-la.

Résultat de référence, D5 Lite pour Rhino 1.2.0.0017, le 12.11.2026 :

| Verdict | Nombre | Sens |
| --- | --- | --- |
| `OK` | 62 | Valeur écrite, relue, puis remise |
| `SANS EFFET` | 8 | Défauts connus de la CLI : 6 écritures de lumière, `metalFxQuality`, projection `twoPointPerspective` vers `orthographic` |
| `ARRET VALIDATION`, `ARRET RISQUE`, `ARRET EXECUTION` | 9 | Refus attendus |
| `ECHEC` | 2 | Refus normaux : angle de cône sur une lumière ponctuelle, `patch.multi` sur deux types de lumière |
| `INDISPONIBLE` | 3 | Opérations annoncées par D5, non livrées |
| `FICHIER ABSENT` | 1 | La capture arrive après la fin de la commande. Le fichier apparaît 3 à 5 s plus tard |
| `REMISE KO` | 0 | Une valeur n'est pas revenue à l'origine. Ne doit jamais apparaître |

Un écart avec ce tableau montre un changement de D5 Lite. Un `SANS EFFET` devenu `OK` est une correction de D5 : mettez à jour le skill.
Un `OK` devenu autre chose est une régression : corrigez le skill avant de le diffuser.

## Essai des matériaux

Dans Rhino, par le MCP Rhino :

```python
import essai_d5mat
reload(essai_d5mat)
essai_d5mat.lancer()
```

Résultat de référence : `BILAN : 38 OK sur 38`. L'essai crée sa propre géométrie, puis la supprime.

## Après les essais

1. Dans Rhino : `print(scene_essai.nettoyer())`.
2. Si tous les résultats sont conformes, mettez à jour `CONTRATS_TESTES` dans `scripts\d5lite.py` avec la valeur `contrats` de `d5lite.py etat`.
3. Mettez à jour la version de D5 Lite dans `SKILL.md`, dans les références et dans `VERSION-AOI.txt`.
