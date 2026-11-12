# -*- coding: utf-8 -*-
"""Essai du module d5mat. A executer DANS Rhino, par le serveur MCP Rhino.

Le script cree sa propre geometrie sur des calques "essai_d5mat::*", execute
chaque fonction, affiche OK ou ERR, puis supprime ce qu'il a cree.
Passez NETTOYER = False pour garder la scene et la regarder dans D5 Lite.

    import sys
    sys.path.insert(0, r"<dossier du skill>\\essais")
    import essai_d5mat; reload(essai_d5mat); essai_d5mat.lancer()
"""
import os
import sys

import rhinoscriptsyntax as rs
import scriptcontext as sc

SKILL = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
if SKILL not in sys.path:
    sys.path.insert(0, SKILL)
import d5mat  # noqa: E402

NETTOYER = True
PREFIXE = "essai_"
RACINE = "essai_d5mat"
BILAN = []


def _essai(nom, f, refus_attendu=False):
    try:
        r = f()
        etat = "ERR" if refus_attendu else "OK"
        BILAN.append((nom, etat))
        print("%-4s %-34s %s" % (etat, nom, d5mat.j(r).replace("\n", " ")[:160]))
        return r
    except d5mat.ErreurMateriau as e:
        etat = "OK" if refus_attendu else "ERR"
        BILAN.append((nom, etat))
        print("%-4s %-34s refus : %s" % (etat, nom, str(e).replace("\n", " ")[:120]))
    except Exception as e:
        BILAN.append((nom, "ERR"))
        print("ERR  %-34s %s: %s" % (nom, type(e).__name__, e))
    return None


def _boite(x, nom, calque):
    g = rs.AddBox([(x, 0, 0), (x + 800, 0, 0), (x + 800, 800, 0), (x, 800, 0),
                   (x, 0, 800), (x + 800, 0, 800), (x + 800, 800, 800), (x, 800, 800)])
    rs.ObjectName(g, nom)
    chemin = RACINE + "::" + calque
    if not rs.IsLayer(chemin):
        rs.AddLayer(calque, parent=RACINE)
    rs.ObjectLayer(g, chemin)
    return str(g)


def lancer():
    try:
        reload(d5mat)
    except NameError:
        pass
    del BILAN[:]
    if not rs.IsLayer(RACINE):
        rs.AddLayer(RACINE)
    x0 = 20000
    a = _boite(x0, "essai_a", "calque")
    b = _boite(x0 + 1000, "essai_b", "objet")
    c = _boite(x0 + 2000, "essai_c", "faces")
    d = _boite(x0 + 3000, "essai_d", "bloc")
    e = _boite(x0 + 4000, "essai_e", "bloc")
    rs.AddBlock([d, e], (x0 + 3000, 0, 0), "essai_bloc", True)
    inst = str(rs.InsertBlock("essai_bloc", (x0 + 3000, 2000, 0)))
    rs.ObjectLayer(inst, RACINE + "::bloc")

    _essai("types", lambda: sorted(d5mat.types().keys()))
    for t in ("generic", "glass", "metal", "emissive", "water", "grass", "sheer"):
        _essai("creer " + t, lambda t=t: d5mat.creer(PREFIXE + t, t)["type_d5"])
    _essai("creer : nom deja pris", lambda: d5mat.creer(PREFIXE + "generic"), refus_attendu=True)
    _essai("creer : type inconnu", lambda: d5mat.creer(PREFIXE + "x", "bois"), refus_attendu=True)
    _essai("modifier", lambda: d5mat.modifier(PREFIXE + "generic", {"base-color": "#336699", "roughness": 0.25})["parametres"])
    _essai("modifier : parametre inconnu", lambda: d5mat.modifier(PREFIXE + "generic", {"brillance": 1}), refus_attendu=True)
    _essai("lire", lambda: d5mat.lire(PREFIXE + "generic")["parametres"]["base-color"])
    _essai("affecter_calque", lambda: d5mat.affecter_calque(PREFIXE + "generic", RACINE + "::calque"))
    _essai("affectation par calque", lambda: d5mat.affectation(a)["materiau_effectif"])
    _essai("affecter_objets", lambda: d5mat.affecter_objets(PREFIXE + "metal", b))
    _essai("affectation par objet", lambda: d5mat.affectation(b)["materiau_effectif"])
    _essai("affecter_par_calque", lambda: d5mat.affecter_par_calque(b))
    _essai("affecter_objets (retour)", lambda: d5mat.affecter_objets(PREFIXE + "metal", b))
    _essai("affecter_faces 1 materiau", lambda: d5mat.affecter_faces(PREFIXE + "glass", c, [5])["faces"])
    _essai("affecter_faces 2e materiau", lambda: d5mat.affecter_faces(PREFIXE + "emissive", c, [0, 1])["faces"])
    _essai("retirer_faces une face", lambda: d5mat.retirer_faces(c, [1])["faces"])
    _essai("affecter_faces : face absente", lambda: d5mat.affecter_faces(PREFIXE + "glass", c, [99]), refus_attendu=True)
    _essai("bloc : instance", lambda: d5mat.affecter_objets(PREFIXE + "generic", inst))
    _essai("bloc : contenu", lambda: [(k["nom"], k["source"]) for k in d5mat.affectation(inst)["bloc"]["contenu"]])
    _essai("usages", lambda: d5mat.usages(PREFIXE + "generic"))
    _essai("dupliquer", lambda: d5mat.dupliquer(PREFIXE + "generic", PREFIXE + "copie")["nom"])
    _essai("remplacer", lambda: d5mat.remplacer(PREFIXE + "generic", PREFIXE + "copie")["remplacements"])
    _essai("placage boite", lambda: d5mat.placage(a, "boite", taille=400, rotation=30))
    _essai("lire_placage", lambda: d5mat.lire_placage(a)["mode"])
    _essai("placage surface", lambda: d5mat.placage(a, "surface"))
    chemin = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bibliotheque_essai.json")
    _essai("exporter", lambda: len(d5mat.exporter(chemin, [PREFIXE + "copie", PREFIXE + "glass"])["materiaux"]))
    _essai("importer (ignore l'existant)", lambda: d5mat.importer(chemin)["ignores"])
    _essai("supprimer : utilise", lambda: d5mat.supprimer(PREFIXE + "copie"), refus_attendu=True)
    _essai("supprimer : inutilise", lambda: d5mat.supprimer(PREFIXE + "generic"))
    _essai("eclater", lambda: len(d5mat.eclater(c)["crees"]))
    _essai("audit", lambda: d5mat.audit()["resume"])
    _essai("inventaire", lambda: len(d5mat.inventaire()))

    if NETTOYER:
        for o in rs.ObjectsByLayer(RACINE, True) or []:
            rs.DeleteObject(o)
        for sous in ("calque", "objet", "faces", "bloc"):
            ch = RACINE + "::" + sous
            if rs.IsLayer(ch):
                for o in rs.ObjectsByLayer(ch) or []:
                    rs.DeleteObject(o)
                rs.PurgeLayer(ch)
        if rs.IsBlock("essai_bloc"):
            rs.DeleteBlock("essai_bloc")
        rs.PurgeLayer(RACINE)
        for m in list(sc.doc.RenderMaterials):
            if m.Name.startswith(PREFIXE):
                sc.doc.RenderMaterials.Remove(m)
        if os.path.isfile(chemin):
            os.remove(chemin)
    ok = len([1 for _, etat in BILAN if etat == "OK"])
    print("BILAN : %d OK sur %d" % (ok, len(BILAN)))
    return BILAN
