# Opérations de D5 Lite testées avec Rhino

Testé le 12.11.2026 : D5 Lite pour Rhino 1.2.0.0017, CLI API 1, contrats `sha256:f2cc11f0…d344`.
Verdict `OK` : la relecture retourne la valeur écrite, et la valeur d'origine est remise.
Pour une opération absente de cette page, lancez `d5lite.py operation <type>`.

## Cibles

| Domaine | Cible (`target`) |
| --- | --- |
| Post-traitement | `{"kind": "postprocess"}` |
| Ciel | `{"kind": "sky"}` |
| Caméra | `{"kind": "camera"}` |
| Scènes | `{"kind": "scene"}` avec `params.sceneId` |
| Réglages et tâche de rendu | `{"kind": "renderJob"}` |
| Capture | `{"kind": "viewport"}` |
| Une lumière | `{"kind": "light", "light_id": "<GUID RHINO EN MAJUSCULES>"}` |
| Plusieurs lumières | `{"kind": "lightCollection", "lightIds": ["<GUID>", …]}` ou `{"kind": "lightCollection", "scope": "all"}` |
| Historique | `{"kind": "history"}` |
| Assets | `{"kind": "asset"}` |
| Matériau courant | `{"kind": "material", "selection": "current"}` |

## Post-traitement — 9 sur 9 `OK`

| Écriture | Paramètre | Plage | Lecture |
| --- | --- | --- | --- |
| `lite.postprocess.patch.exposure` | `exposure` | −1 à 1 | `lite.postprocess.read.exposure` |
| `lite.postprocess.patch.autoExposure` | `autoExposure` | booléen | `…read.autoExposure` |
| `lite.postprocess.patch.contrast` | `contrast` | −1 à 1 | `…read.contrast` |
| `lite.postprocess.patch.highlight` | `highlight` | 0 à 1 | `…read.highlight` |
| `lite.postprocess.patch.shadow` | `shadow` | 0 à 1 | `…read.shadow` |
| `lite.postprocess.patch.saturation` | `saturation` | −1 à 1 | `…read.saturation` |
| `lite.postprocess.patch.temperature` | `temperature` | 3000 à 12000 K | `…read.temperature` |
| `lite.postprocess.patch.tint` | `tint` | −1 à 1 | `…read.tint` |
| `lite.postprocess.patch.tonalContrast` | `tonalContrast` | 0 à 1 | `…read.tonalContrast` |

`lite.postprocess.read` retourne les neuf valeurs en une lecture.

## Ciel — 11 opérations `OK`

| Écriture | Paramètre | Plage | Lecture et champ |
| --- | --- | --- | --- |
| `lite.sky.patch.mode` | `mode` | `GEO`, `HDRI` | `lite.sky.read.mode` → `mode` |
| `lite.sky.patch.geoAltitude` | `altitude` | −90 à 90° | `lite.sky.read.sunEleAzi` → `geoSunEleAzi.altitude` |
| `lite.sky.patch.geoAzimuth` | `azimuth` | degrés, ramenés à 0–360 | `lite.sky.read.sunEleAzi` → `geoSunEleAzi.azimuth` |
| `lite.sky.patch.hdriRotation` | `rotation` | degrés, ramenés à 0–360 | `lite.sky.read.skyRotation` → `skyRotation` |
| `lite.sky.patch.hdriIntensity` | `intensity` | 0 à 1 | `lite.sky.read.intensity` → `intensity` |
| `lite.sky.patch.hdriSunlightIntensity` | `sunlightIntensity` | 0 à 20 | `lite.sky.read.hdriSunlightIntensity` |
| `lite.sky.patch.hdriSunDirection` | `sunDirection` : `{"mode": "custom", "altitude": 0–90, "azimuth": n}` ou `{"mode": "followHdri"}` | — | `lite.sky.read.hdriSunDirectionMode` → `mode` |
| `lite.sky.patch.hdriFile` | `filePath` | fichier `.exr` ou `.hdr` local | `lite.sky.read.hdriFile` → `filePath` |
| `lite.sky.resetHdri` | aucun | — | `lite.sky.read.isDefaultHdri` → `true` |
| `lite.sky.patch.hdriPreset` | `name` | nom d'un préréglage en ligne | Non vérifié : aucune opération ne liste les noms. Un nom inconnu retourne `sky_hdri_preset_not_found` |

- Les réglages GEO s'appliquent en mode `GEO`. Les réglages HDRI s'appliquent en mode `HDRI`.
- `resetHdri` remplace le HDRI de Rhino par celui de Lite. Notez `filePath` avant, pour le remettre.

## Caméra — 20 opérations `OK`, 1 défaut

| Opération | Paramètres | Effet vérifié |
| --- | --- | --- |
| `lite.camera.patch.fov` | `valueDegrees` 1–179 | focale |
| `lite.camera.patch.moveSpeed` | `value` 1–200 | vitesse |
| `lite.camera.patch.projectionMode` | `mode` : `perspective`, `twoPointPerspective`, `orthographic` | projection (voir le défaut) |
| `lite.camera.move` | `direction` (`forward`, `backward`, `left`, `right`, `up`, `down`), `distance` en m | position |
| `lite.camera.pan` | `horizontalDistance`, `verticalDistance` en m | position |
| `lite.camera.orbit` | `center` `[x, y, z]`, `pitchDegrees`, `yawDegrees` | position et direction |
| `lite.camera.lookAround` | `pitchDegrees`, `yawDegrees` | direction |
| `lite.camera.alignToDcc` | aucun | caméra remise sur la vue de Rhino |
| `lite.camera.input.*` (11 opérations) | souris, molette, touches | simulent l'interface. Préférez les opérations ci-dessus |

- Chaque opération de caméra retourne l'état complet de la caméra. Une relecture séparée est inutile.
- **Défaut :** de `twoPointPerspective` vers `orthographic`, la projection ne change pas, et la réponse contient `verified: true`. Passez par `perspective` : `twoPointPerspective` → `perspective` → `orthographic`.
- Un changement de projection déplace la caméra. Relisez la position ensuite, ou terminez par `alignToDcc`.
- Pour revenir à la vue de Rhino : `projectionMode: perspective`, puis `alignToDcc`.

## Scènes — 6 opérations `OK`, 1 non testée

| Opération | Paramètres | Remarque |
| --- | --- | --- |
| `lite.scene.list` | aucun | Retourne `items[]` avec `sceneId`, `name`, `isCurrent` |
| `lite.scene.select` | `sceneId` | Asynchrone : relisez `lite.scene.list` après 1 s. Change `aspectRatio` du rendu en `followDcc` |
| `lite.scene.create` | aucun | Crée la scène `view_000` **et une vue nommée dans Rhino** |
| `lite.scene.rename` | `sceneId`, `name` | Renomme aussi la vue nommée de Rhino |
| `lite.scene.update` | `sceneId` | Enregistre l'état courant dans la scène |
| `lite.scene.parameters.copy` puis `paste` | `sceneId` | Copie les paramètres d'une scène vers une autre |
| `lite.scene.delete` | `sceneId`, `confirmed: true` | `confirmWrite`. `OK`. Supprime aussi la vue nommée de Rhino |
| `lite.scene.snapshot.read.*` | `sceneId` | Caméra en centimètres, dans les axes de Rhino |

Supprimer une vue nommée dans Rhino supprime la scène dans Lite (vérifié).

## Rendu et capture

| Opération | Paramètres | Verdict |
| --- | --- | --- |
| `lite.render.settings.patch.quality` | `quality` : `low`, `high` | `OK` |
| `lite.render.settings.patch.format` | `format` : `png`, `jpg` | `OK` |
| `lite.render.settings.patch.outputType` | `outputType` : `image`, `panorama` | `OK` |
| `lite.render.settings.patch.aspect` | `aspectRatio` : `followDcc`, `fill`, `4:3`, `16:9`, `3:2`, `3:4`, `9:16`, `2:3`, `1:1` | `OK` |
| `lite.render.patch.metalFxQuality` | `mode` | **Sans effet** |
| `lite.render.job.start` | `outputPath` absolu, `confirmed: true`, réglages facultatifs | `OK`. `low` : 2560 px de large, 10 à 13 s. `high` : 3840 px, 30 s. Panorama : 4096 × 2048, 17 s. PNG et JPG vérifiés. Durées sur la scène de test |
| `lite.render.job.status` | aucun | `OK` : `stage`, `progress`, `active` |
| `lite.render.job.cancel` | aucun | Sans rendu en cours : `render_job_not_active` |
| `lite.screenshot.capture` | `maxSize` 1–8192, `path` facultatif | `OK`. Le fichier arrive après la fin de la commande : attendez 3 à 5 s |
| `lite.screenshot.setPath` | `path` | `OK` |

Sans `path`, la capture va dans `%LOCALAPPDATA%\Temp\d5_lite_temp\dsl_screenshots\liteops_capture_<id>.png`.

## Lumières

Lectures `OK` : `light_type`, `brightness`, `color`, `colorTemperature`, `isTemperature`, `location`, `rotation`, `attenuationRadius`, `reflectionVisibility`, `coneAngle` (spot), `size` (surface, linéaire, disque : non testé).

| Écriture | Verdict sur une lumière de Rhino |
| --- | --- |
| `lite.light.patch.intensity`, `color`, `temperature`, `useTemperature`, `reflectionVisibility`, `coneAngle` | **Sans effet.** Acquittées, inscrites dans l'historique de Lite, valeur inchangée |
| `lite.light.patch.multi` | Exige des lumières du même type. Sinon : `invalid_target_type` |
| `lite.light.patch.visibility` (`visible`, cible `scope: all`) | Acquittée. Pas de relecture possible |

Réglez une lumière dans Rhino. La couleur changée dans Rhino se relit à l'identique dans Lite (vérifié).
`brightness` reste à 1,0 pour une lumière de Rhino. Le lien entre l'intensité de Rhino et ce champ n'est pas établi.

## Assets, historique, divers

| Opération | Verdict |
| --- | --- |
| `lite.asset.search` (`query`, `maxResults`, `matchMode: text`) | `OK` : 352 résultats pour « tree » |
| `lite.asset.list` | `OK` : 6321 modèles. Sortie volumineuse |
| `lite.asset.read.type`, `download.readStatus`, `update.readStatus` (`assetId`) | `OK` |
| `lite.asset.download` | Non testée. Aucune opération ne place l'asset dans la scène |
| `lite.history.read` | `OK` |
| `lite.history.undo`, `redo` | `confirmWrite`. `OK` : l'annulation et le rétablissement d'un réglage d'exposition sont vérifiés par relecture |
| `lite.performance.read`, `lite.viewport.read.metrics`, `lite.dcc.read` | `OK` |
| `lite.material.read` et `lite.material.patch.*` | Bloquées : `material_editor_closed` |
| `lite.application.quit` | `confirmWrite`. Non testée |

## Refus de la CLI (vérifiés)

La validation refuse, avant toute exécution : valeur hors plage (`invalid_param_range`), opération inconnue (`unknown_operation`), paramètre manquant (`missing_params`), paramètre en trop (`unknown_field`), mauvais type (`invalid_param_type`), référence inconnue (`missing_reference_source`), accord absent (`confirmation_required`).
