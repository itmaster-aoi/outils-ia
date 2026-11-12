# Matériaux entre Rhino et D5 Lite

Testé sur D5 Lite pour Rhino 1.2.0.0017, Rhino 8.

## Principe

D5 Lite n'a pas de table de matériaux propre. Il lit les matériaux de rendu du document Rhino.
Un réglage fait dans Rhino apparaît dans Lite en 2 à 4 s. Les matériaux sont enregistrés dans le fichier `.3dm`.
Les opérations `lite.material.*` de la CLI ne servent pas avec Rhino : elles demandent un éditeur que Lite pour Rhino n'a pas.

Le module `scripts/d5mat.py` fait tout le travail. Il s'exécute dans Rhino, par le serveur MCP Rhino.

## Chargement

Envoyez ce code par l'outil `execute_rhinoscript_python_code` du MCP Rhino :

```python
import sys
p = r"<dossier du skill>\scripts"
if p not in sys.path:
    sys.path.insert(0, p)
import d5mat
reload(d5mat)
print(d5mat.j(d5mat.inventaire()))
```

- Le module tourne sous IronPython 2.7 : `print` avec parenthèses et un seul argument, pas de f-string.
- `d5mat.j(...)` met le résultat en JSON.
- Une erreur d'usage lève `d5mat.ErreurMateriau`, avec un message en clair.

## Types de matériaux D5

| Type | Paramètres | Canaux de texture testés |
| --- | --- | --- |
| `generic` | `base-color`, `roughness`, `specular`, `normal` | `base-color` |
| `glass` | `base-color`, `roughness`, `specular`, `normal`, `opacity`, `ior`, `metallic` | — |
| `metal` | `base-color`, `roughness`, `normal` | — |
| `emissive` | `emissive`, `intensity` | — |
| `water` | `base-color`, `specular`, `depth`, `normal` (booléen) | — |
| `grass` | `base-color`, `density`, `height` | — |
| `sheer` | `base-color`, `opacity`, `ior`, `normal` | — |

- Couleur : `"#RRGGBB"` ou `[r, v, b]` entre 0 et 1.
- `d5mat.types()` donne les valeurs par défaut. Un paramètre inconnu est refusé, avec la liste des paramètres valables.
- Vérifiés dans Lite par capture : `generic`, `glass`, `metal`, `emissive`. Non vérifiés : `water`, `grass`, `sheer`.
- Un matériau Rhino ordinaire (PBR) s'affiche aussi dans Lite. La conversion en D5 donne accès aux réglages propres à D5.

## Modes d'affectation

Les quatre modes de Rhino s'affichent dans Lite. Ordre de priorité de Rhino : face, puis objet, puis parent ou calque.

| Mode | Fonction | Vérifié dans Lite |
| --- | --- | --- |
| Par calque | `affecter_calque(nom, calques)`, `retirer_calque(calques)` | Oui |
| Par objet | `affecter_objets(nom, objets)` | Oui |
| Retour au calque | `affecter_par_calque(objets)` | Oui |
| Par parent (contenu d'un bloc) | `affecter_par_parent(objets)` ; le matériau se pose sur l'instance avec `affecter_objets` | Oui |
| Par face | `affecter_faces(nom, objet, faces)`, `retirer_faces(objet, faces=None)` | Oui : 3 matériaux sur une boîte |

`affectation(objet)` donne le mode, le matériau effectif, le matériau du calque, les faces et le contenu d'un bloc.

**Deux pièges de Rhino, traités par le module :**

- `objet.RenderMaterial = materiau` écrase une entrée existante de la table des matériaux. D'autres objets changent alors de matériau, et Lite ne reçoit pas le changement. Le module passe par l'indice de table et `ModifyAttributes`.
- Les canaux d'un matériau par face se déclarent sur une entrée de table neuve, avant son ajout, avec l'identifiant de l'entrée de table du matériau de la face. Modifier une entrée déjà ajoutée ne fonctionne pas. Le module reconstruit l'entrée à chaque appel.

## Orientation des textures

Deux niveaux, qui se cumulent :

| Niveau | Fonction | Réglages |
| --- | --- | --- |
| Matériau | `texture(nom, canal, fichier=None, repetition=None, decalage=None, rotation=None, actif=None, retirer=False)` | Répétition `[u, v]`, décalage `[u, v]`, rotation en degrés |
| Objet | `placage(objets, mode, taille, rotation, origine)` | Mode `boite`, `plan` ou `surface` ; taille d'une répétition dans l'unité du document ; rotation autour de Z |

- `lire_placage(objet)` donne le mode de placage d'un objet.
- Vérifié dans Lite : répétition 3 × 3 avec rotation 30°, plus placage en boîte de 2000 mm tourné de 45°.
- Le réglage du matériau vaut pour tous les objets qui portent ce matériau. Le placage vaut pour un objet.

## Échelle réelle des textures

Par défaut, la taille d'une texture dépend de chaque objet : de son placage ou de ses coordonnées de surface. Deux objets de tailles différentes montrent alors la même image à deux échelles.

`echelle(nom, largeur_m, hauteur_m=None, rotation=None)` donne une taille réelle à la texture, en mètres. La texture passe en projection monde : tous les objets qui portent le matériau ont la même échelle, sans placage.

| Fonction | Rôle |
| --- | --- |
| `echelle(nom, largeur_m, hauteur_m, rotation)` | Une répétition de l'image mesure `largeur_m`. La hauteur suit les proportions de l'image |
| `echelle_objet(nom, repetition)` | Revient aux coordonnées de l'objet |
| `lire_echelle(nom)` | Projection, répétition, et taille en mètres si elle est connue |
| `echelles()` | Échelle de toutes les textures du document |

- Vérifié dans Lite : une répétition tous les 2 m sur un sol de 8 m (capture 19).
- Le calcul tient compte de l'unité du document : en millimètres, une largeur de 2 m donne une répétition de 0,0005.
- `d5scene.rapport()` signale les textures sans taille réelle.
- Pour une orientation propre à un objet (lames de parquet dans le sens d'une pièce), utilisez `placage` sur cet objet, avec `echelle_objet` sur le matériau.

## Fonctions

| Fonction | Rôle |
| --- | --- |
| `types()` | Types D5 et paramètres par défaut |
| `inventaire(detail=False)` | Matériaux du document, type, nombre d'usages |
| `lire(nom)` | Paramètres, textures et usages d'un matériau |
| `usages(nom)` | Calques, objets, contenus de blocs et faces qui portent le matériau |
| `affectation(objet)` | Matériau effectif d'un objet et mode d'affectation |
| `creer(nom, type_d5, parametres, textures)` | Crée un matériau D5 |
| `modifier(nom, parametres, textures, nouveau_nom)` | Modifie ou renomme |
| `dupliquer(nom, nouveau_nom)` | Copie un matériau D5 avec ses textures |
| `supprimer(nom, forcer=False)` | Supprime. Refuse si le matériau est utilisé |
| `remplacer(ancien, nouveau)` | Remplace partout : calques, objets, contenus de blocs |
| `convertir(nom, type_d5=None)` | Crée l'équivalent D5 d'un matériau Rhino et le met à sa place |
| `convertir_tous()` | Convertit tous les matériaux Rhino utilisés |
| `eclater(objet)` | Sépare une polysurface en un objet par matériau |
| `audit()` | Calques et objets sans matériau, textures introuvables, matériaux inutilisés |
| `exporter(chemin, noms=None)` | Écrit des matériaux D5 dans un fichier JSON |
| `importer(chemin, ecraser=False)` | Recrée ces matériaux dans un autre document |

## Ordre de travail

1. Lancez `audit()` et `inventaire()`. Montrez le résumé à l'utilisateur.
2. Créez ou modifiez les matériaux. Affectez-les selon le mode que l'utilisateur emploie déjà dans le fichier : lisez `affectation()` sur deux objets pour le savoir.
3. Capturez la vue de Lite (`lite.screenshot.capture`) 4 s après le changement, puis lisez l'image.
4. Donnez le nom du matériau, le mode d'affectation et le résultat vu.

## Approbations

Ces fonctions modifient le document Rhino. Ce sont des modifications ordinaires du modèle, annulables dans Rhino (Ctrl+Z).

- Lecture (`inventaire`, `lire`, `usages`, `affectation`, `audit`, `lire_placage`, `types`) : aucune demande.
- Création, modification, affectation demandées par l'utilisateur : exécutez, puis montrez le résultat.
- `supprimer`, `remplacer`, `convertir_tous`, `eclater`, `importer(ecraser=True)` : annoncez la portée (nombre de calques, d'objets, de blocs) avant d'exécuter.

## Limites

- `remplacer` ne traite pas les matériaux par face. Le résultat donne `faces_non_traitees`.
- `convertir` reprend la couleur, la rugosité, l'opacité et la texture de couleur. Il ne reprend pas les textures de relief.
- `affecter_faces` et `retirer_faces` laissent des entrées inutilisées dans la table des matériaux. Elles sont sans effet sur le rendu.
- Un fichier de texture doit exister sur le disque. `exporter` écrit les chemins, pas les images.
- Canaux de texture autres que `base-color` : non testés.
- Les blocs imbriqués et les blocs liés ne sont pas testés.
