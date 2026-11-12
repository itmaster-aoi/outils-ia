# -*- coding: utf-8 -*-
"""Controle du document Rhino avant un rendu D5 Lite ou un passage vers D5 Render.

Ce module s'execute DANS Rhino (IronPython 2.7), par le serveur MCP Rhino.
Il lit seulement. Il s'appuie sur d5mat.py et d5lum.py.

    print(d5scene.j(d5scene.rapport()))
    print(d5scene.j(d5scene.preparer_d5render()))
"""
import json
import os

import Rhino
import rhinoscriptsyntax as rs
import scriptcontext as sc

import d5lum
import d5mat

CLE_LITE = "D5Lite.DocumentData"


def j(valeur):
    return json.dumps(valeur, indent=2, sort_keys=True, default=str)


def donnees_lite():
    """Reglages que D5 Lite enregistre dans le document (texte utilisateur D5Lite.DocumentData).

    D5 Render lit ces donnees quand il ouvre le modele. Elles sont a jour apres
    un enregistrement du fichier Rhino.
    """
    brut = rs.GetDocumentUserText(CLE_LITE)
    if not brut:
        return {"present": False}
    d = json.loads(brut)

    def deplier(texte):
        try:
            return json.loads(texte) if texte else None
        except Exception:
            return texte
    doc = d.get("doc") or {}
    vues = {}
    for nom, v in (d.get("views") or {}).items():
        vues[nom] = dict((k, deplier(x) if k.endswith("_save_data") else x) for k, x in v.items()) if isinstance(v, dict) else v
    return {"present": True, "version": d.get("version"), "projet": d.get("project_guid"),
            "ciel": deplier(doc.get("sky_save_data")), "post_traitement": deplier(doc.get("pp_save_data")),
            "rendu": deplier(doc.get("render_save_data")), "scene_courante": doc.get("scene_id"),
            "hdri_integres": list((d.get("embedded_hdri_textures") or {}).keys()), "vues": vues}


def _document():
    doc = sc.doc
    chemin = (rs.DocumentPath() or "") + (rs.DocumentName() or "")
    return {"fichier": chemin or None, "enregistre": bool(rs.DocumentName()), "modifie_non_enregistre": bool(doc.Modified),
            "unite": str(doc.ModelUnitSystem), "disque": os.path.splitdrive(chemin)[0] if chemin else None}


def _plugin_d5():
    for pid in Rhino.PlugIns.PlugIn.GetInstalledPlugIns().Keys:
        nom = Rhino.PlugIns.PlugIn.GetInstalledPlugIns()[pid]
        if "D5" in nom:
            info = Rhino.PlugIns.PlugIn.GetPlugInInfo(pid)
            return {"nom": nom, "charge": bool(info.IsLoaded), "commandes": list(info.CommandNames)}
    return None


def rapport():
    """Controle avant rendu, cote Rhino. Lecture seule.

    Le controle cote D5 Lite (connexion, ciel, exposition, scenes) se fait par
    la commande : d5lite.py controle.
    """
    doc = sc.doc
    alertes, infos = [], []
    document = _document()
    if not document["enregistre"]:
        alertes.append("Le document n'a jamais ete enregistre.")
    elif document["modifie_non_enregistre"]:
        infos.append("Le document a des modifications non enregistrees.")
    vues = list(rs.NamedViews() or [])
    if not vues:
        alertes.append("Aucune vue nommee : D5 Lite n'aura aucune scene a rendre.")
    mat = d5mat.audit()
    lum = d5lum.audit()
    if mat["resume"]["objets_sans_materiau"]:
        alertes.append("%d objet(s) sans materiau : ils auront le gris par defaut." % mat["resume"]["objets_sans_materiau"])
    for t in mat["textures_introuvables"]:
        alertes.append("Texture introuvable : %s (%s)" % (t["fichier"], t["materiau"]))
    echelles = d5mat.echelles()
    sans_echelle = sorted(set(e["materiau"] for e in echelles if not e["echelle_reelle"]))
    if sans_echelle:
        infos.append("Textures sans taille reelle (elles dependent du placage de chaque objet) : %s" % ", ".join(sans_echelle))
    if mat["resume"]["materiaux_rhino_utilises"]:
        infos.append("%d materiau(x) Rhino non convertis en D5 : %s" % (
            mat["resume"]["materiaux_rhino_utilises"], ", ".join(m["nom"] for m in mat["materiaux_rhino_utilises"])))
    for l in lum["non_reprises_par_lite"]:
        infos.append("Lumiere non reprise par D5 Lite : %s (%s)" % (l["nom"], l["type"]))
    for l in lum["intensite_faible"]:
        alertes.append("Lumiere allumee mais invisible dans Lite : %s (intensite %s)" % (l["nom"], l["intensite"]))
    if lum["noms_en_double"]:
        infos.append("Lumieres de meme nom : %s" % ", ".join(lum["noms_en_double"]))
    caches = len([o for o in doc.Objects if o.IsHidden])
    if caches:
        infos.append("%d objet(s) cache(s)." % caches)
    plugin = _plugin_d5()
    if plugin is None or not plugin["charge"]:
        alertes.append("Le plugin D5 n'est pas charge dans Rhino.")
    return {"pret": not alertes, "alertes": alertes, "infos": infos, "document": document, "vues_nommees": vues,
            "materiaux": mat["resume"], "calques_sans_materiau": mat["calques_sans_materiau"],
            "lumieres": {"total": lum["total"], "allumees": lum["allumees"]},
            "textures": {"total": len(echelles), "a_taille_reelle": len([e for e in echelles if e["echelle_reelle"]])},
            "conseils": mat["conseils"] + lum["conseils"]}


def preparer_d5render():
    """Controle le document avant de poursuivre le travail dans D5 Render. Lecture seule.

    Ce controle repose sur la documentation de D5 : D5 Render lit les donnees de
    D5 Lite dans le fichier du modele, et la synchronisation va de Rhino vers D5.
    Le passage lui-meme n'est PAS teste.
    """
    r = rapport()
    etapes, bloquants = [], []
    document = r["document"]
    lite = donnees_lite()
    if not document["enregistre"] or document["modifie_non_enregistre"]:
        bloquants.append("Enregistrez le document : D5 Render lit les reglages de Lite dans le fichier .3dm.")
    if not lite["present"]:
        bloquants.append("Le document ne contient aucun reglage D5 Lite. Ouvrez-le une fois dans D5 Lite.")
    if document["disque"] and document["disque"].upper() != "C:":
        etapes.append("Le fichier est sur %s. Verifiez que les textures sont accessibles depuis D5 Render." % document["disque"])
    for t in d5mat.audit()["textures_introuvables"]:
        bloquants.append("Texture introuvable : %s" % t["fichier"])
    plugin = _plugin_d5() or {}
    commandes = plugin.get("commandes") or []
    etapes.append("1. Enregistrez le fichier Rhino.")
    etapes.append("2. Ouvrez D5 Render, puis dans Rhino lancez D5LiveSyncStart." if "D5LiveSyncStart" in commandes
                  else "2. Le plugin D5 n'expose pas D5LiveSyncStart : ouvrez le modele depuis D5 Render.")
    etapes.append("3. Dans Rhino : D5LiveSyncSendModel, D5LiveSyncSendLights, D5LiveSyncSendScenes.")
    etapes.append("4. Verifiez dans D5 Render : materiaux, lumieres, ciel, vues. Rien ne revient de D5 Render vers Rhino.")
    return {"pret": r["pret"] and not bloquants, "bloquants": bloquants + r["alertes"], "infos": r["infos"],
            "donnees_lite": {"present": lite["present"], "vues": sorted((lite.get("vues") or {}).keys()),
                             "hdri_integres": lite.get("hdri_integres")},
            "commandes_d5": [c for c in commandes if c.startswith("D5LiveSync")], "etapes": etapes,
            "non_teste": "Le passage vers D5 Render n'est pas teste."}
