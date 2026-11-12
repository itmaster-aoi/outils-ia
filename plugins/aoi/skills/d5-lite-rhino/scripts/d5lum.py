# -*- coding: utf-8 -*-
"""Lumieres de Rhino pour D5 Lite, et mode jour / nuit.

Ce module s'execute DANS Rhino (IronPython 2.7), par le serveur MCP Rhino.
La CLI de D5 Lite ne modifie pas une lumiere de Rhino : tout se regle ici.

Faits verifies le 12.11.2026 (D5 Lite pour Rhino 1.2.0.0017) :
- L'intensite de Rhino (Intensity) se relit a l'identique dans Lite (brightness).
  Elle n'est pas bornee a 1. Ordre de grandeur utile : 100 a 5000.
- Les watts et les lumens de Rhino ne sont pas repris par Lite.
- Une lumiere eteinte dans Rhino disparait de Lite.
- Types repris : ponctuelle, spot, rectangulaire (area), lineaire (line).
- La lumiere directionnelle n'est pas reprise par Lite.
- Dans la CLI, l'identifiant d'une lumiere est son GUID Rhino en majuscules.

Chargement : voir d5mat.py. Exemple : print(d5lum.j(d5lum.lister()))
"""
import json

import Rhino
import System
import scriptcontext as sc

CLE_JOUR = "d5.jour"
CLE_NUIT = "d5.nuit"
CLE_INTENSITE_NUIT = "d5.nuit.intensite"
TYPES = {"WorldPoint": "ponctuelle", "WorldSpot": "spot", "WorldRectangular": "rectangulaire",
         "WorldLinear": "lineaire", "WorldDirectional": "directionnelle"}
REPRIS_PAR_LITE = ("ponctuelle", "spot", "rectangulaire", "lineaire")


class ErreurLumiere(Exception):
    pass


def j(valeur):
    return json.dumps(valeur, indent=2, sort_keys=True, default=str)


def _doc():
    return sc.doc


def _couleur(valeur):
    if isinstance(valeur, str):
        t = valeur.lstrip("#")
        return System.Drawing.Color.FromArgb(int(t[0:2], 16), int(t[2:4], 16), int(t[4:6], 16))
    v = [float(x) for x in valeur]
    if max(v) <= 1.0:
        v = [x * 255.0 for x in v]
    return System.Drawing.Color.FromArgb(int(v[0]), int(v[1]), int(v[2]))


def _hex(c):
    return "#%02X%02X%02X" % (c.R, c.G, c.B)


def _toutes():
    return [o for o in _doc().Lights if not o.IsDeleted]


def _choisir(selection=None, calque=None):
    """selection : None (toutes), un nom, un GUID, ou une liste de noms et de GUID."""
    lumieres = _toutes()
    if calque:
        doc = _doc()
        lumieres = [o for o in lumieres if doc.Layers[o.Attributes.LayerIndex].FullPath == calque
                    or doc.Layers[o.Attributes.LayerIndex].Name == calque]
    if selection is None:
        return lumieres
    cles = selection if isinstance(selection, (list, tuple)) else [selection]
    cles = [str(c).strip("{}").lower() for c in cles]
    choix = [o for o in lumieres if str(o.Id).lower() in cles or (o.Name or "").lower() in cles]
    if not choix:
        raise ErreurLumiere("Aucune lumiere ne correspond a : %s" % selection)
    return choix


def _texte(o, cle):
    return o.Attributes.GetUserString(cle)


def _ecrire_texte(o, cle, valeur):
    a = o.Attributes.Duplicate()
    a.SetUserString(cle, valeur)
    return bool(_doc().Objects.ModifyAttributes(o, a, True))


def _decrire(o):
    g = o.LightGeometry
    t = TYPES.get(str(g.LightStyle), str(g.LightStyle))
    d = {"nom": o.Name, "id": str(o.Id), "id_lite": str(o.Id).upper(), "type": t,
         "allumee": bool(g.IsEnabled), "intensite": g.Intensity, "couleur": _hex(g.Diffuse),
         "position": [g.Location.X, g.Location.Y, g.Location.Z],
         "calque": _doc().Layers[o.Attributes.LayerIndex].FullPath,
         "reprise_par_lite": t in REPRIS_PAR_LITE,
         "jour": _texte(o, CLE_JOUR), "nuit": _texte(o, CLE_NUIT)}
    if t == "spot":
        import math
        d["angle_cone"] = round(math.degrees(g.SpotAngleRadians) * 2.0, 3)
        d["cible"] = [g.Location.X + g.Direction.X, g.Location.Y + g.Direction.Y, g.Location.Z + g.Direction.Z]
    if t in ("rectangulaire", "lineaire"):
        d["longueur"] = g.Length.Length
    if t == "rectangulaire":
        d["largeur"] = g.Width.Length
    return d


def _modifier(o, f):
    g = o.LightGeometry.Duplicate()
    f(g)
    return bool(_doc().Lights.Modify(o.Id, g))


# ---------------------------------------------------------------- lecture
def lister(calque=None):
    """Toutes les lumieres du document, avec l'identifiant a donner a la CLI de Lite."""
    return [_decrire(o) for o in _choisir(None, calque)]


def lire(selection):
    return [_decrire(o) for o in _choisir(selection)]


# --------------------------------------------------------------- creation
def creer(type_lumiere, nom, position, cible=None, intensite=500.0, couleur="#FFFFFF",
          angle_cone=60.0, longueur=1000.0, largeur=1000.0, calque=None):
    """Cree une lumiere. Les longueurs sont dans l'unite du document.

    type_lumiere : ponctuelle, spot, rectangulaire, lineaire.
    spot : cible obligatoire, angle_cone en degres (angle complet).
    rectangulaire : position = centre, la lumiere eclaire vers le bas (-Z) ou vers la cible.
    lineaire : position = debut, cible = fin (sinon longueur le long de +X).
    """
    import math
    import rhinoscriptsyntax as rs
    P = Rhino.Geometry.Point3d(*position)
    if type_lumiere == "ponctuelle":
        gid = rs.AddPointLight(P)
    elif type_lumiere == "spot":
        if cible is None:
            raise ErreurLumiere("Un spot demande une cible.")
        C = Rhino.Geometry.Point3d(*cible)
        rayon = (C - P).Length * math.tan(math.radians(float(angle_cone) / 2.0))
        gid = rs.AddSpotLight(C, rayon, P)
    elif type_lumiere == "rectangulaire":
        axe_x, axe_y = Rhino.Geometry.Vector3d(1, 0, 0), Rhino.Geometry.Vector3d(0, -1, 0)
        if cible is not None:
            n = Rhino.Geometry.Point3d(*cible) - P
            n.Unitize()
            plan = Rhino.Geometry.Plane(P, n)
            axe_x, axe_y = plan.XAxis, plan.YAxis
        o = P - axe_x * (float(longueur) / 2.0) - axe_y * (float(largeur) / 2.0)
        gid = rs.AddRectangularLight(o, o + axe_x * float(longueur), o + axe_y * float(largeur))
    elif type_lumiere == "lineaire":
        fin = Rhino.Geometry.Point3d(*cible) if cible is not None else P + Rhino.Geometry.Vector3d(float(longueur), 0, 0)
        gid = rs.AddLinearLight(P, fin)
    else:
        raise ErreurLumiere("Type non repris par D5 Lite : %s. Types : %s" % (type_lumiere, ", ".join(REPRIS_PAR_LITE)))
    if gid is None:
        raise ErreurLumiere("Rhino n'a pas cree la lumiere.")
    rs.ObjectName(gid, nom)
    if calque:
        if not rs.IsLayer(calque):
            rs.AddLayer(calque)
        rs.ObjectLayer(gid, calque)
    o = _doc().Objects.FindId(gid)
    _modifier(o, lambda g: (setattr(g, "Intensity", float(intensite)), setattr(g, "Diffuse", _couleur(couleur))))
    _doc().Views.Redraw()
    return _decrire(_doc().Objects.FindId(gid))


def modifier(selection, intensite=None, couleur=None, allumee=None, position=None, angle_cone=None, facteur=None):
    """Regle une ou plusieurs lumieres. facteur multiplie l'intensite actuelle."""
    import math
    faits = []
    for o in _choisir(selection):
        def f(g):
            if intensite is not None:
                g.Intensity = float(intensite)
            if facteur is not None:
                g.Intensity = g.Intensity * float(facteur)
            if couleur is not None:
                g.Diffuse = _couleur(couleur)
            if allumee is not None:
                g.IsEnabled = bool(allumee)
            if position is not None:
                g.Location = Rhino.Geometry.Point3d(*position)
            if angle_cone is not None:
                g.SpotAngleRadians = math.radians(float(angle_cone) / 2.0)
        _modifier(o, f)
        faits.append(_decrire(_doc().Objects.FindId(o.Id)))
    _doc().Views.Redraw()
    return faits


def allumer(selection=None, calque=None):
    return [d["nom"] for d in modifier([str(o.Id) for o in _choisir(selection, calque)], allumee=True)]


def eteindre(selection=None, calque=None):
    return [d["nom"] for d in modifier([str(o.Id) for o in _choisir(selection, calque)], allumee=False)]


def dupliquer(selection, deplacement, copies=1, suffixe="_"):
    """Copie une lumiere en serie. deplacement : [dx, dy, dz] entre deux copies."""
    import rhinoscriptsyntax as rs
    crees = []
    for o in _choisir(selection):
        for n in range(1, int(copies) + 1):
            v = [deplacement[0] * n, deplacement[1] * n, deplacement[2] * n]
            gid = rs.CopyObject(o.Id, v)
            rs.ObjectName(gid, "%s%s%d" % (o.Name or "lumiere", suffixe, n))
            crees.append(_decrire(_doc().Objects.FindId(gid)))
    _doc().Views.Redraw()
    return crees


def supprimer(selection):
    import rhinoscriptsyntax as rs
    noms = []
    for o in _choisir(selection):
        noms.append(o.Name)
        rs.DeleteObject(o.Id)
    return {"supprimees": noms}


# ------------------------------------------------------------ jour / nuit
def definir_mode(selection=None, jour=None, nuit=None, intensite_nuit=None, calque=None):
    """Fixe l'etat d'une lumiere dans chaque mode. jour, nuit : True (allumee) ou False.

    Sans reglage, une lumiere est eteinte le jour et allumee la nuit.
    intensite_nuit : intensite appliquee en mode nuit (sinon l'intensite actuelle).
    Les reglages sont enregistres dans le texte utilisateur de la lumiere, donc dans le .3dm.
    """
    faits = []
    for o in _choisir(selection, calque):
        if jour is not None:
            _ecrire_texte(_doc().Objects.FindId(o.Id), CLE_JOUR, "allumee" if jour else "eteinte")
        if nuit is not None:
            _ecrire_texte(_doc().Objects.FindId(o.Id), CLE_NUIT, "allumee" if nuit else "eteinte")
        if intensite_nuit is not None:
            _ecrire_texte(_doc().Objects.FindId(o.Id), CLE_INTENSITE_NUIT, str(float(intensite_nuit)))
        faits.append(_decrire(_doc().Objects.FindId(o.Id)))
    return faits


def mode(nom):
    """Met les lumieres dans l'etat du mode "jour" ou "nuit".

    Ce module regle les lumieres de Rhino. Le ciel se regle par la CLI :
    d5lite.py nuit  /  d5lite.py jour.
    """
    if nom not in ("jour", "nuit"):
        raise ErreurLumiere("Mode inconnu : %s" % nom)
    bilan = {"mode": nom, "allumees": [], "eteintes": [], "non_reprises_par_lite": []}
    for o in _toutes():
        d = _decrire(o)
        reglage = d["jour"] if nom == "jour" else d["nuit"]
        if reglage is None:
            reglage = "eteinte" if nom == "jour" else "allumee"
        allumee = reglage == "allumee"
        intensite = None
        if nom == "nuit" and allumee:
            t = _texte(o, CLE_INTENSITE_NUIT)
            intensite = float(t) if t else None
        modifier(str(o.Id), allumee=allumee, intensite=intensite)
        bilan["allumees" if allumee else "eteintes"].append(d["nom"])
        if allumee and not d["reprise_par_lite"]:
            bilan["non_reprises_par_lite"].append(d["nom"])
    _doc().Views.Redraw()
    return bilan


def etat():
    """Etat allume ou eteint et intensite de chaque lumiere. A garder pour restaurer()."""
    return [{"id": str(o.Id), "nom": o.Name, "allumee": bool(o.LightGeometry.IsEnabled),
             "intensite": o.LightGeometry.Intensity, "couleur": _hex(o.LightGeometry.Diffuse)} for o in _toutes()]


def restaurer(etats):
    """Remet les lumieres dans un etat lu par etat()."""
    faits = []
    for e in etats:
        try:
            modifier(e["id"], allumee=e["allumee"], intensite=e["intensite"], couleur=e["couleur"])
            faits.append(e["nom"])
        except ErreurLumiere:
            pass
    return {"restaurees": faits}


# ------------------------------------------------------------------ audit
def audit():
    """Releve ce qui empeche un eclairage fidele dans D5 Lite."""
    r = {"total": 0, "allumees": 0, "non_reprises_par_lite": [], "intensite_faible": [],
         "sans_nom": 0, "noms_en_double": [], "conseils": []}
    noms = {}
    for o in _toutes():
        d = _decrire(o)
        r["total"] += 1
        r["allumees"] += 1 if d["allumee"] else 0
        if not d["nom"]:
            r["sans_nom"] += 1
        else:
            noms[d["nom"]] = noms.get(d["nom"], 0) + 1
        if not d["reprise_par_lite"]:
            r["non_reprises_par_lite"].append({"nom": d["nom"], "type": d["type"]})
        elif d["allumee"] and d["intensite"] <= 1.0:
            r["intensite_faible"].append({"nom": d["nom"], "intensite": d["intensite"]})
    r["noms_en_double"] = sorted(n for n, c in noms.items() if c > 1)
    if r["non_reprises_par_lite"]:
        r["conseils"].append("D5 Lite ne reprend pas les lumieres directionnelles. Le soleil se regle par le ciel de Lite.")
    if r["intensite_faible"]:
        r["conseils"].append("Une intensite de 1 est invisible dans Lite. Ordre de grandeur utile : 100 a 5000.")
    if r["noms_en_double"] or r["sans_nom"]:
        r["conseils"].append("Nommez chaque lumiere d'un nom unique : la selection par nom en depend.")
    return r
