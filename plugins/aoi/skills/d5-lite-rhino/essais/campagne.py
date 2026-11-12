"""Campagne de tests des operations de D5 Lite sur la scene d'essai.

A rejouer apres chaque mise a jour de D5 Lite. Chaque cas lit la valeur, ecrit
une valeur d'essai, relit, puis remet la valeur d'origine. Le verdict compare
la relecture a la valeur attendue.

Avant de lancer :
1. Ouvrez un document vide dans Rhino 8, lancez mcpstart.
2. Dans Rhino, par le MCP Rhino : scene_essai.construire() (voir scene_essai.py).
3. Lancez D5LiteStart et attendez la fin du chargement.

Usage : python campagne.py <domaine> [<domaine> ...] [--confirme]
Domaines : post ciel rendu camera lumiere scene asset materiau divers robustesse
Les cas confirmWrite demandent l'option --confirme (accord de l'utilisateur).
Aucun rendu n'est lance par ce script.
Resultats : %TEMP%\\d5lite_essai\\resultats\\<domaine>.json
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from d5lite import D5Lite  # noqa: E402

RACINE = Path(os.environ.get("D5LITE_ESSAI") or Path(tempfile.gettempdir()) / "d5lite_essai")
SORTIE = RACINE / "resultats"
SORTIE.mkdir(parents=True, exist_ok=True)

_scene = RACINE / "scene.json"
if not _scene.is_file():
    sys.exit(f"Scene d'essai absente : {_scene}. Lancez d'abord scene_essai.construire() dans Rhino.")
_donnees = json.loads(_scene.read_text(encoding="utf-8"))
POINT = _donnees["point"].upper()
SPOT = _donnees["spot"].upper()
NOM_VUE = _donnees["vue"]

d5 = D5Lite(journal=RACINE / "journal")
_scenes = (d5.lire("lite.scene.list", {"kind": "scene"}).get("valeur") or {}).get("items") or []
SCENE = next((s["sceneId"] for s in _scenes if s["name"] == NOM_VUE), None)
if SCENE is None:
    sys.exit(f"D5 Lite ne voit pas la scene {NOM_VUE}. Lite est-il demarre sur le document d'essai ?")
CAMERA_ORIGINE = d5.lire("lite.camera.read.state", {"kind": "camera"}).get("valeur") or {}
RESULTATS: list[dict] = []
CONFIRME = "--confirme" in sys.argv


def champ(valeur, chemin: str):
    for cle in chemin.split("."):
        if not isinstance(valeur, dict) or cle not in valeur:
            return None
        valeur = valeur[cle]
    return valeur


def egal(a, b, tol=1e-3) -> bool:
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b) <= tol * max(1.0, abs(b))
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(egal(x, y, tol) for x, y in zip(a, b))
    return a == b


def noter(domaine, cas, operation, verdict, **details):
    ligne = {"domaine": domaine, "cas": cas, "operation": operation, "verdict": verdict, **details}
    RESULTATS.append(ligne)
    resume = {k: v for k, v in details.items() if k in ("avant", "ecrit", "apres", "remis", "erreur", "note")}
    print(f"[{verdict:<12}] {operation:<42} {json.dumps(resume, ensure_ascii=False)[:230]}", flush=True)


def cas_valeur(domaine, operation, cible_e, param, essai, lecture, cible_l, chemin,
               attendu=None, params_l=None, remise=True, risque="safeWrite", params_fixes=None,
               construire=None):
    """Lit, ecrit, relit, remet. construire(valeur) donne les params d'ecriture."""
    construire = construire or (lambda v: {**(params_fixes or {}), param: v})
    attendu = essai if attendu is None else attendu
    op_l = {"id": "avant", "type": lecture, "target": cible_l, "params": params_l or {}}
    op_e = {"id": "ecrire", "type": operation, "target": cible_e, "params": construire(essai)}
    r = d5.executer([op_l, op_e, {**op_l, "id": "apres"}], nom=operation.replace(".", "_"),
                    risque_max=risque, confirme=(risque == "confirmWrite"))
    if r["etape"] != "execution":
        noter(domaine, param, operation, "REFUSE", erreur=r["etape"],
              note=json.dumps(r.get("diagnostics") or r.get("risque"), ensure_ascii=False)[:300])
        return
    seg = r["segments"]
    avant = champ((seg.get("avant") or {}).get("valeur"), chemin)
    ecr = seg.get("ecrire") or {}
    apres = champ((seg.get("apres") or {}).get("valeur"), chemin)
    if ecr.get("statut") != "completed":
        noter(domaine, param, operation, "ECHEC", avant=avant, ecrit=essai,
              erreur=ecr.get("erreur") or (seg.get("avant") or {}).get("erreur"),
              note=(ecr.get("message") or (seg.get("avant") or {}).get("message") or "")[:200])
        return
    if egal(apres, attendu):
        verdict = "OK"
    elif egal(apres, avant):
        verdict = "SANS EFFET"
    else:
        verdict = "ECART"
    remis = None
    if remise and avant is not None and verdict != "SANS EFFET":
        r2 = d5.executer([{"id": "remettre", "type": operation, "target": cible_e, "params": construire(avant)},
                          {**op_l, "id": "relire"}], nom="remise_" + operation.replace(".", "_"),
                         risque_max=risque, confirme=(risque == "confirmWrite"))
        remis = champ(((r2.get("segments") or {}).get("relire") or {}).get("valeur"), chemin)
        if not egal(remis, avant):
            verdict += " / REMISE KO"
    noter(domaine, param, operation, verdict, avant=avant, ecrit=essai, apres=apres, remis=remis,
          acquittement=ecr.get("valeur"))


# ---------------------------------------------------------------- domaines
def domaine_post():
    c = {"kind": "postprocess"}
    for param, essai in [("autoExposure", False), ("contrast", 0.2), ("exposure", 0.25), ("highlight", 0.6),
                         ("saturation", 0.3), ("shadow", 0.2), ("temperature", 5000), ("tint", 0.2),
                         ("tonalContrast", 0.4)]:
        cas_valeur("post", f"lite.postprocess.patch.{param}", c, param, essai,
                   f"lite.postprocess.read.{param}", c, param)


def domaine_ciel():
    c = {"kind": "sky"}
    cas_valeur("ciel", "lite.sky.patch.hdriRotation", c, "rotation", 45, "lite.sky.read.skyRotation", c, "skyRotation")
    cas_valeur("ciel", "lite.sky.patch.hdriRotation", c, "rotation", 400, "lite.sky.read.skyRotation", c, "skyRotation", attendu=40)
    cas_valeur("ciel", "lite.sky.patch.hdriIntensity", c, "intensity", 0.6, "lite.sky.read.intensity", c, "intensity")
    cas_valeur("ciel", "lite.sky.patch.hdriSunlightIntensity", c, "sunlightIntensity", 5,
               "lite.sky.read.hdriSunlightIntensity", c, "hdriSunlightIntensity")
    cas_valeur("ciel", "lite.sky.patch.hdriSunDirection", c, "sunDirection",
               {"mode": "custom", "altitude": 30, "azimuth": 100},
               "lite.sky.read.hdriSunDirectionMode", c, "mode", attendu="custom",
               construire=lambda v: {"sunDirection": v if isinstance(v, dict) else {"mode": v}})
    r = d5.lire("lite.sky.read.sunEleAzi", c)
    noter("ciel", "lecture apres direction", "lite.sky.read.sunEleAzi", "INFO", apres=r.get("valeur"))
    cas_valeur("ciel", "lite.sky.patch.mode", c, "mode", "GEO", "lite.sky.read.mode", c, "mode", remise=False)
    cas_valeur("ciel", "lite.sky.patch.geoAltitude", c, "altitude", 35, "lite.sky.read.sunEleAzi", c, "geoSunEleAzi.altitude")
    cas_valeur("ciel", "lite.sky.patch.geoAzimuth", c, "azimuth", 200, "lite.sky.read.sunEleAzi", c, "geoSunEleAzi.azimuth")
    cas_valeur("ciel", "lite.sky.patch.mode", c, "mode", "HDRI", "lite.sky.read.mode", c, "mode", remise=False)
    # fichier HDRI local
    origine = (d5.lire("lite.sky.read.hdriFile", c).get("valeur") or {}).get("filePath")
    autre = None
    if origine:
        dossier = Path(origine).parent
        for motif in ("*.exr", "*.hdr"):
            for f in sorted(dossier.glob(motif)):
                if f.as_posix().lower() != Path(origine).as_posix().lower():
                    autre = f.as_posix()
                    break
            if autre:
                break
    if autre:
        cas_valeur("ciel", "lite.sky.patch.hdriFile", c, "filePath", autre, "lite.sky.read.hdriFile", c, "filePath")
    else:
        noter("ciel", "filePath", "lite.sky.patch.hdriFile", "NON TESTE", note="aucun second fichier HDRI local trouve")
    r = d5.executer([{"id": "reset", "type": "lite.sky.resetHdri", "target": c},
                     {"id": "defaut", "type": "lite.sky.read.isDefaultHdri", "target": c},
                     {"id": "fichier", "type": "lite.sky.read.hdriFile", "target": c}], nom="resetHdri")
    seg = r.get("segments") or {}
    ok = champ((seg.get("defaut") or {}).get("valeur"), "isDefaultHdri") is True
    noter("ciel", "reset", "lite.sky.resetHdri", "OK" if ok else "ECART",
          apres=(seg.get("fichier") or {}).get("valeur"), erreur=(seg.get("reset") or {}).get("erreur"))
    if origine:
        r = d5.executer([{"id": "remettre", "type": "lite.sky.patch.hdriFile", "target": c, "params": {"filePath": origine}},
                         {"id": "fichier", "type": "lite.sky.read.hdriFile", "target": c}], nom="remise_hdri")
        remis = champ(((r.get("segments") or {}).get("fichier") or {}).get("valeur"), "filePath")
        noter("ciel", "remise du HDRI d'origine", "lite.sky.patch.hdriFile",
              "OK" if remis and remis.lower() == origine.lower() else "REMISE KO", avant=origine, remis=remis)
    # prereglage : aucun moyen de lister les noms
    r = d5.executer([{"id": "p", "type": "lite.sky.patch.hdriPreset", "target": c, "params": {"name": "nom-inexistant-audit"}}],
                    nom="hdriPreset_inconnu")
    s = (r.get("segments") or {}).get("p") or {}
    noter("ciel", "prereglage inconnu", "lite.sky.patch.hdriPreset", "ERREUR ATTENDUE" if s.get("statut") == "failed" else "A VERIFIER",
          erreur=s.get("erreur"), note=(s.get("message") or "")[:200])


def domaine_rendu():
    c = {"kind": "renderJob"}
    for op, param, essai in [("quality", "quality", "high"), ("format", "format", "jpg"),
                             ("outputType", "outputType", "panorama"), ("aspect", "aspectRatio", "16:9")]:
        cas_valeur("rendu", f"lite.render.settings.patch.{op}", c, param, essai, "lite.render.settings.read", c, param)
    cas_valeur("rendu", "lite.render.patch.metalFxQuality", {"kind": "render"}, "mode", "Quality",
               "lite.render.read.metalFxQuality", {"kind": "render"}, "metalFxQuality")
    r = d5.executer([{"id": "annuler", "type": "lite.render.job.cancel", "target": c},
                     {"id": "etat", "type": "lite.render.job.status", "target": c}], nom="cancel_sans_rendu")
    seg = r.get("segments") or {}
    noter("rendu", "annulation sans rendu en cours", "lite.render.job.cancel",
          "OK" if (seg.get("annuler") or {}).get("statut") == "completed" else "ERREUR",
          apres=(seg.get("annuler") or {}).get("valeur"), erreur=(seg.get("annuler") or {}).get("erreur"),
          note=(seg.get("annuler") or {}).get("message"))
    noter("rendu", "lancement", "lite.render.job.start", "TESTE A PART",
          note="lance par l'utilisateur le 12.11.2026 : PNG 2560x1302 en 10 s")


def domaine_camera():
    c = {"kind": "camera"}
    cas_valeur("camera", "lite.camera.patch.fov", c, "valueDegrees", 50, "lite.camera.read.fov", c, "fovDegrees")
    cas_valeur("camera", "lite.camera.patch.moveSpeed", c, "value", 20, "lite.camera.read.moveSpeed", c, "moveSpeed")
    for mode in ("twoPointPerspective", "orthographic", "perspective"):
        cas_valeur("camera", "lite.camera.patch.projectionMode", c, "mode", mode,
                   "lite.camera.read.projectionMode", c, "projectionMode", remise=False)
    actions = [
        ("lite.camera.move", {"direction": "backward", "distance": 1.0, "speedProfile": "normal"}),
        ("lite.camera.pan", {"horizontalDistance": 1.0, "verticalDistance": -0.5}),
        ("lite.camera.orbit", {"center": [0, 1, 0], "pitchDegrees": -5, "yawDegrees": 15}),
        ("lite.camera.lookAround", {"pitchDegrees": 5, "yawDegrees": 20}),
        ("lite.camera.input.drag", {"button": "right", "deltaPixels": [-100, 0], "durationMs": 250, "startUv": [0.5, 0.5]}),
        ("lite.camera.input.verticalDrag", {"deltaYPixels": 50, "durationMs": 250, "startUv": [0.5, 0.5]}),
        ("lite.camera.input.holdMovementKey", {"durationMs": 300, "key": "W"}),
        ("lite.camera.input.holdMovementKey.fast", {"durationMs": 300, "key": "S"}),
        ("lite.camera.input.holdMovementKey.slow", {"durationMs": 300, "key": "A"}),
        ("lite.camera.input.wheel", {"positionUv": [0.5, 0.5], "wheelDelta": 1}),
        ("lite.camera.input.wheel.fast", {"positionUv": [0.5, 0.5], "wheelDelta": -1}),
        ("lite.camera.input.wheel.fov", {"wheelDelta": 1}),
        ("lite.camera.input.wheel.moveSpeed", {"wheelDelta": 1}),
        ("lite.camera.input.projectionShortcut", {"key": "P"}),
        ("lite.camera.input.projectionShortcut", {"key": "P"}),
        ("lite.camera.input.alignShortcut", {"key": "0"}),
    ]
    cles = ("position", "forward", "fovDegrees", "moveSpeed", "projectionMode", "orthoWidth")
    for op, params in actions:
        r = d5.executer([{"id": "avant", "type": "lite.camera.read.state", "target": c},
                         {"id": "agir", "type": op, "target": c, "params": params},
                         {"id": "apres", "type": "lite.camera.read.state", "target": c}], nom=op.replace(".", "_"))
        seg = r.get("segments") or {}
        a = (seg.get("avant") or {}).get("valeur") or {}
        b = (seg.get("apres") or {}).get("valeur") or {}
        agir = seg.get("agir") or {}
        if agir.get("statut") != "completed":
            noter("camera", json.dumps(params), op, "ECHEC" if r["etape"] == "execution" else "REFUSE",
                  erreur=agir.get("erreur") or r["etape"], note=(agir.get("message") or json.dumps(r.get("diagnostics"))[:200]))
            continue
        change = [k for k in cles if not egal(a.get(k), b.get(k), 1e-4)]
        noter("camera", json.dumps(params), op, "OK" if change else "SANS EFFET",
              ecrit=params, note="champs changes : " + ", ".join(change),
              acquittement={"verified": (agir.get("valeur") or {}).get("verified")})
    origine = {"fov": CAMERA_ORIGINE.get("fovDegrees", 35.0), "vitesse": CAMERA_ORIGINE.get("moveSpeed", 8.0)}
    r = d5.executer([{"id": "persp", "type": "lite.camera.patch.projectionMode", "target": c, "params": {"mode": "perspective"}},
                     {"id": "fov", "type": "lite.camera.patch.fov", "target": c, "params": {"valueDegrees": origine["fov"]}},
                     {"id": "vit", "type": "lite.camera.patch.moveSpeed", "target": c, "params": {"value": origine["vitesse"]}},
                     {"id": "aligner", "type": "lite.camera.alignToDcc", "target": c},
                     {"id": "etat", "type": "lite.camera.read.state", "target": c}], nom="remise_camera")
    e = ((r.get("segments") or {}).get("etat") or {}).get("valeur") or {}
    # alignToDcc remet la camera sur la vue de Rhino : la position depend de cette vue, pas de l'etat de depart.
    ok = e.get("projectionMode") == "perspective" and egal(e.get("fovDegrees"), origine["fov"], 1e-2)
    noter("camera", "remise", "lite.camera.alignToDcc", "OK" if ok else "REMISE KO",
          remis={k: e.get(k) for k in ("position", "fovDegrees", "projectionMode", "moveSpeed")})


def domaine_lumiere():
    p = {"kind": "light", "light_id": POINT}
    s = {"kind": "light", "light_id": SPOT}
    cas_valeur("lumiere", "lite.light.patch.intensity", p, "intensity", 10, "lite.light.read.brightness", p, "brightness")
    cas_valeur("lumiere", "lite.light.patch.color", p, "color", "#FF0000", "lite.light.read.color", p, "color", attendu=[1.0, 0.0, 0.0])
    cas_valeur("lumiere", "lite.light.patch.temperature", p, "temperature", 3000, "lite.light.read.colorTemperature", p, "colorTemperature")
    cas_valeur("lumiere", "lite.light.patch.useTemperature", p, "useTemperature", True, "lite.light.read.isTemperature", p, "isTemperature")
    cas_valeur("lumiere", "lite.light.patch.reflectionVisibility", p, "reflectionVisibility", 0.5,
               "lite.light.read.reflectionVisibility", p, "reflectionVisibility")
    cas_valeur("lumiere", "lite.light.patch.coneAngle", s, "coneAngle", 60, "lite.light.read.coneAngle", s, "coneAngle")
    cas_valeur("lumiere", "lite.light.patch.coneAngle", p, "coneAngle", 60, "lite.light.read.light_type", p, "light_type", attendu="point")
    col = {"kind": "lightCollection", "lightIds": [POINT, SPOT]}
    cas_valeur("lumiere", "lite.light.patch.multi", col, "patch", {"intensity": 7}, "lite.light.read.brightness", s, "brightness",
               attendu=7, remise=False)
    tous = {"kind": "lightCollection", "scope": "all"}
    for visible in (False, True):
        r = d5.executer([{"id": "v", "type": "lite.light.patch.visibility", "target": tous, "params": {"visible": visible}},
                         {"id": "cap", "type": "lite.screenshot.capture", "target": {"kind": "viewport"}, "params": {"maxSize": 640}}],
                        nom=f"visibilite_{visible}")
        seg = r.get("segments") or {}
        v = seg.get("v") or {}
        noter("lumiere", f"visible={visible}", "lite.light.patch.visibility",
              "ACQUITTE" if v.get("statut") == "completed" else "ECHEC", ecrit=visible,
              acquittement=v.get("valeur"), erreur=v.get("erreur"),
              note="pas de relecture : lite.light.read.visibility est planned. Capture : "
                   + str(champ((seg.get("cap") or {}).get("valeur"), "artifactPath")))
    r = d5.lire("lite.light.read.brightness", {"kind": "light", "light_id": "00000000-0000-0000-0000-000000000000"})
    noter("lumiere", "GUID inconnu", "lite.light.read.brightness", "ERREUR ATTENDUE" if not r["ok"] else "A VERIFIER",
          erreur=r.get("erreur"), note=r.get("message"))


def domaine_scene():
    c = {"kind": "scene"}

    def liste():
        return (d5.lire("lite.scene.list", c).get("valeur") or {})

    avant = liste()
    ids_avant = {i["sceneId"] for i in avant.get("items", [])}
    r = d5.executer([{"id": "creer", "type": "lite.scene.create", "target": c}], nom="scene_create")
    time.sleep(2)
    apres = liste()
    nouveaux = [i for i in apres.get("items", []) if i["sceneId"] not in ids_avant]
    noter("scene", "creation", "lite.scene.create", "OK" if nouveaux else "SANS EFFET",
          avant=avant.get("count"), apres=apres.get("count"),
          acquittement=((r.get("segments") or {}).get("creer") or {}).get("valeur"), note=json.dumps(nouveaux))
    if not nouveaux:
        return
    nid = nouveaux[0]["sceneId"]
    r = d5.executer([{"id": "renommer", "type": "lite.scene.rename", "target": c, "params": {"sceneId": nid, "name": "audit_scene"}}],
                    nom="scene_rename")
    time.sleep(1)
    nom = (d5.lire("lite.scene.item.read.name", c, {"sceneId": nid}).get("valeur") or {}).get("name")
    noter("scene", "renommage", "lite.scene.rename", "OK" if nom == "audit_scene" else "ECART", ecrit="audit_scene", apres=nom,
          acquittement=((r.get("segments") or {}).get("renommer") or {}).get("valeur"))
    r = d5.executer([{"id": "choisir", "type": "lite.scene.select", "target": c, "params": {"sceneId": nid}}], nom="scene_select")
    time.sleep(1)
    cour = liste().get("currentSceneId")
    noter("scene", "selection", "lite.scene.select", "OK" if cour == nid else "ECART", ecrit=nid, apres=cour)
    # mise a jour : changer l'exposition, mettre a jour la scene, lire l'instantane
    r = d5.executer([{"id": "expo", "type": "lite.postprocess.patch.exposure", "target": {"kind": "postprocess"}, "params": {"exposure": 0.4}},
                     {"id": "maj", "type": "lite.scene.update", "target": c, "params": {"sceneId": nid}}], nom="scene_update")
    time.sleep(1)
    snap = d5.lire("lite.scene.snapshot.read.postprocess", c, {"sceneId": nid}).get("valeur")
    noter("scene", "mise a jour", "lite.scene.update",
          "OK" if ((r.get("segments") or {}).get("maj") or {}).get("statut") == "completed" else "ECHEC",
          acquittement=((r.get("segments") or {}).get("maj") or {}).get("valeur"),
          apres=snap, erreur=((r.get("segments") or {}).get("maj") or {}).get("erreur"))
    # copier les parametres de la nouvelle scene vers vue_test ? non : sens inverse, pour ne pas alterer vue_test
    r = d5.executer([{"id": "copier", "type": "lite.scene.parameters.copy", "target": c, "params": {"sceneId": SCENE}},
                     {"id": "coller", "type": "lite.scene.parameters.paste", "target": c, "params": {"sceneId": nid}}], nom="scene_copy_paste")
    seg = r.get("segments") or {}
    noter("scene", "copie des parametres", "lite.scene.parameters.copy",
          "OK" if (seg.get("copier") or {}).get("statut") == "completed" else "ECHEC",
          acquittement=(seg.get("copier") or {}).get("valeur"), erreur=(seg.get("copier") or {}).get("erreur"),
          note=(seg.get("copier") or {}).get("message"))
    noter("scene", "collage des parametres", "lite.scene.parameters.paste",
          "OK" if (seg.get("coller") or {}).get("statut") == "completed" else "ECHEC",
          acquittement=(seg.get("coller") or {}).get("valeur"), erreur=(seg.get("coller") or {}).get("erreur"),
          note=(seg.get("coller") or {}).get("message"))
    # retour a vue_test et a l'exposition d'origine
    d5.executer([{"id": "choisir", "type": "lite.scene.select", "target": c, "params": {"sceneId": SCENE}},
                 {"id": "expo", "type": "lite.postprocess.patch.exposure", "target": {"kind": "postprocess"}, "params": {"exposure": 0}}],
                nom="scene_retour")
    if CONFIRME:
        r = d5.executer([{"id": "supprimer", "type": "lite.scene.delete", "target": c, "params": {"sceneId": nid, "confirmed": True}}],
                        nom="scene_delete", risque_max="confirmWrite", confirme=True)
        time.sleep(2)
        reste = [i["sceneId"] for i in liste().get("items", [])]
        noter("scene", "suppression", "lite.scene.delete", "OK" if nid not in reste else "SANS EFFET",
              acquittement=((r.get("segments") or {}).get("supprimer") or {}).get("valeur"),
              erreur=((r.get("segments") or {}).get("supprimer") or {}).get("erreur") or (r["etape"] if r["etape"] != "execution" else None),
              apres=len(reste))
    else:
        noter("scene", "suppression", "lite.scene.delete", "NON TESTE", note=f"confirmWrite. Scene d'audit restante : {nid}")
    fin = liste()
    noter("scene", "etat final", "lite.scene.list", "INFO", apres=fin)


def domaine_asset():
    c = {"kind": "asset"}
    r = d5.lire("lite.asset.search", c, {"matchMode": "text", "maxResults": 5, "query": "tree"})
    items = (r.get("valeur") or {}).get("items") or []
    noter("asset", "recherche tree", "lite.asset.search", "OK" if items else "VIDE",
          apres={"count": (r.get("valeur") or {}).get("count"), "totalMatches": (r.get("valeur") or {}).get("totalMatches")})
    if not items:
        return
    aid = items[0].get("assetId")
    for op in ("lite.asset.read.type", "lite.asset.download.readStatus", "lite.asset.update.readStatus"):
        r = d5.lire(op, c, {"assetId": aid})
        noter("asset", f"assetId {aid}", op, "OK" if r["ok"] else "ECHEC", apres=r.get("valeur"), erreur=None if r["ok"] else r.get("erreur"))
    r = d5.lire("lite.asset.list", c)
    cat = (r.get("valeur") or {}).get("catalog") or {}
    noter("asset", "catalogue", "lite.asset.list", "OK" if r["ok"] else "ECHEC",
          apres={k: (len(v) if isinstance(v, list) else v) for k, v in cat.items()} if isinstance(cat, dict) else None)
    noter("asset", "telechargement", "lite.asset.download", "NON TESTE",
          note="telecharge des fichiers depuis les serveurs D5 ; aucune operation ne place l'asset dans la scene")


def domaine_materiau():
    c = {"kind": "material", "selection": "current"}
    r = d5.lire("lite.material.read", c)
    if not r["ok"]:
        noter("materiau", "lecture", "lite.material.read", "BLOQUE", erreur=r.get("erreur"), note=(r.get("message") or "")[:220])
        return
    v = r["valeur"]
    noter("materiau", "lecture", "lite.material.read", "OK", apres=v)
    if not CONFIRME:
        noter("materiau", "ecritures", "lite.material.patch.*", "NON TESTE", note="confirmWrite")
        return
    val = v.get("value") or v
    gabarit = val.get("template")
    for param, essai in [("roughness", 0.2), ("specular", 0.8), ("normal", 0.5), ("baseColor", "#3366CC")]:
        cas_valeur("materiau", f"lite.material.patch.{param}", c, param, essai, "lite.material.read", c,
                   f"value.{param}", risque="confirmWrite",
                   attendu=None if param != "baseColor" else None)
    noter("materiau", "gabarit courant", "lite.material.read", "INFO", apres=gabarit)


def domaine_divers():
    v = {"kind": "viewport"}
    chemin = (SORTIE / "capture_chemin.png").as_posix()
    r = d5.executer([{"id": "cap", "type": "lite.screenshot.capture", "target": v, "params": {"maxSize": 800, "path": chemin}}],
                    nom="capture_chemin")
    s = (r.get("segments") or {}).get("cap") or {}
    time.sleep(3)
    art = champ(s.get("valeur"), "artifactPath")
    noter("divers", "capture avec chemin", "lite.screenshot.capture",
          "OK" if art and Path(art).is_file() else ("ECHEC" if s.get("statut") != "completed" else "FICHIER ABSENT"),
          ecrit=chemin, apres=art, erreur=s.get("erreur") or (r["etape"] if r["etape"] != "execution" else None),
          note=(s.get("message") or json.dumps(r.get("diagnostics"))[:200]))
    r = d5.executer([{"id": "chemin", "type": "lite.screenshot.setPath", "params": {"path": chemin}}], nom="setPath")
    s = (r.get("segments") or {}).get("chemin") or {}
    noter("divers", "chemin par defaut", "lite.screenshot.setPath",
          "OK" if s.get("statut") == "completed" else "REFUSE" if r["etape"] != "execution" else "ECHEC",
          erreur=s.get("erreur") or r["etape"], note=(s.get("message") or json.dumps(r.get("diagnostics"))[:250]))
    for op, cible in [("lite.history.read", {"kind": "history"}), ("lite.performance.read", {"kind": "performance"}),
                      ("lite.viewport.read.metrics", {"kind": "viewport"}), ("lite.dcc.read", {"kind": "dcc"})]:
        r = d5.lire(op, cible)
        val = r.get("valeur") or {}
        noter("divers", "lecture", op, "OK" if r["ok"] else "ECHEC",
              apres={k: val[k] for k in list(val)[:4]} if isinstance(val, dict) else None, erreur=None if r["ok"] else r.get("erreur"))
    for op in ("lite.status.read", "lite.diagnostics.run", "lite.light.read.visibility"):
        cible = {"kind": "light", "light_id": POINT} if "light" in op else None
        r = d5.lire(op, cible)
        noter("divers", "operation planned", op, "INDISPONIBLE" if not r["ok"] else "DISPONIBLE",
              erreur=r.get("erreur"), note=json.dumps(r.get("diagnostics") or r.get("message"), ensure_ascii=False)[:220])
    if CONFIRME:
        pp = {"kind": "postprocess"}
        h = {"kind": "history"}
        d5.executer([{"id": "e", "type": "lite.postprocess.patch.exposure", "target": pp, "params": {"exposure": 0.35}}], nom="avant_undo")
        r = d5.executer([{"id": "annuler", "type": "lite.history.undo", "target": h},
                         {"id": "expo", "type": "lite.postprocess.read.exposure", "target": pp}],
                        nom="undo", risque_max="confirmWrite", confirme=True)
        seg = r.get("segments") or {}
        e1 = champ((seg.get("expo") or {}).get("valeur"), "exposure")
        noter("divers", "annulation", "lite.history.undo", "OK" if egal(e1, 0.0) else "ECART", avant=0.35, apres=e1,
              erreur=(seg.get("annuler") or {}).get("erreur") or (r["etape"] if r["etape"] != "execution" else None))
        r = d5.executer([{"id": "retablir", "type": "lite.history.redo", "target": h},
                         {"id": "expo", "type": "lite.postprocess.read.exposure", "target": pp}],
                        nom="redo", risque_max="confirmWrite", confirme=True)
        seg = r.get("segments") or {}
        e2 = champ((seg.get("expo") or {}).get("valeur"), "exposure")
        noter("divers", "retablissement", "lite.history.redo", "OK" if egal(e2, 0.35) else "ECART", apres=e2,
              erreur=(seg.get("retablir") or {}).get("erreur"))
        d5.executer([{"id": "e", "type": "lite.postprocess.patch.exposure", "target": pp, "params": {"exposure": 0}}], nom="apres_redo")
    else:
        noter("divers", "annulation", "lite.history.undo / redo", "NON TESTE", note="confirmWrite")
    noter("divers", "fermeture de Lite", "lite.application.quit", "NON TESTE", note="ferme D5 Lite : a tester en dernier, avec accord")


def domaine_robustesse():
    pp = {"kind": "postprocess"}
    essais = [
        ("valeur hors plage", [{"id": "x", "type": "lite.postprocess.patch.exposure", "target": pp, "params": {"exposure": 5}}]),
        ("operation inconnue", [{"id": "x", "type": "lite.postprocess.patch.inexistant", "target": pp, "params": {}}]),
        ("parametre manquant", [{"id": "x", "type": "lite.postprocess.patch.exposure", "target": pp, "params": {}}]),
        ("parametre en trop", [{"id": "x", "type": "lite.postprocess.patch.exposure", "target": pp, "params": {"exposure": 0, "bidon": 1}}]),
        ("mauvais type", [{"id": "x", "type": "lite.postprocess.patch.exposure", "target": pp, "params": {"exposure": "fort"}}]),
        ("reference inconnue", [{"id": "x", "type": "lite.scene.select", "target": {"kind": "scene"}, "params": {"sceneId": "${absent.sceneId}"}}]),
        ("espace de noms SketchUp", [{"id": "x", "type": "su-lite.light.get_select", "params": {}}]),
    ]
    for nom, ops in essais:
        r = d5.executer(ops, nom="robustesse")
        seg = (r.get("segments") or {}).get("x") or {}
        diag = r.get("diagnostics") or []
        codes = [d.get("code") for d in diag if isinstance(d, dict)]
        noter("robustesse", nom, ops[0]["type"], f"ARRET {r['etape'].upper()}", erreur=seg.get("erreur") or ", ".join(map(str, codes)),
              note=(seg.get("message") or (diag[0].get("message") if diag and isinstance(diag[0], dict) else ""))[:200])
    r = d5.executer([{"id": "x", "type": "lite.scene.delete", "target": {"kind": "scene"}, "params": {"sceneId": "absent", "confirmed": True}}],
                    nom="garde_risque", risque_max="safeWrite", confirme=True)
    noter("robustesse", "garde-fou de risque de l'outil", "lite.scene.delete", "ARRET " + r["etape"].upper(),
          note=f"risque du plan : {r.get('risque')}, maximum accepte : {r.get('risque_max')}")
    r = d5.executer([{"id": "x", "type": "lite.scene.delete", "target": {"kind": "scene"}, "params": {"sceneId": "absent"}}],
                    nom="confirmation_absente", risque_max="confirmWrite", confirme=False)
    diag = r.get("diagnostics") or []
    noter("robustesse", "confirmWrite sans declaration", "lite.scene.delete", "ARRET " + r["etape"].upper(),
          erreur=", ".join(str(d.get("code")) for d in diag if isinstance(d, dict)),
          note=json.dumps([d.get("message") for d in diag if isinstance(d, dict)], ensure_ascii=False)[:250])


DOMAINES = {"post": domaine_post, "ciel": domaine_ciel, "rendu": domaine_rendu, "camera": domaine_camera,
            "lumiere": domaine_lumiere, "scene": domaine_scene, "asset": domaine_asset,
            "materiau": domaine_materiau, "divers": domaine_divers, "robustesse": domaine_robustesse}


def main():
    choix = [a for a in sys.argv[1:] if not a.startswith("--")]
    etat = d5.etat()
    if not etat["connecte"]:
        print("D5 Lite ne repond pas :", etat)
        return 2
    for nom in choix:
        debut = time.time()
        print(f"=== {nom} ===", flush=True)
        avant = len(RESULTATS)
        try:
            DOMAINES[nom]()
        except Exception as err:  # un domaine en erreur n'arrete pas la campagne
            noter(nom, "exception", "-", "ERREUR SCRIPT", erreur=repr(err))
        (SORTIE / f"{nom}.json").write_text(json.dumps(RESULTATS[avant:], ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"--- {nom} : {len(RESULTATS) - avant} cas en {time.time() - debut:.0f} s", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

