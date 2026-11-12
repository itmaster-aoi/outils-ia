# -*- coding: utf-8 -*-
"""Gestion des materiaux entre Rhino 8 et D5 Lite.

Ce module s'execute DANS Rhino (IronPython 2.7 ou CPython 3), par le serveur
MCP Rhino. D5 Lite lit les materiaux de rendu de Rhino : tout se regle donc
dans le document Rhino, et Lite suit en direct.

Chargement dans Rhino :
    import sys
    sys.path.insert(0, r"<dossier scripts du skill>")
    import d5mat
    print(d5mat.j(d5mat.inventaire()))

Chaque fonction retourne un dictionnaire ou une liste. d5mat.j() le met en JSON.
Les couleurs sont "#RRGGBB" ou [r, v, b] entre 0 et 1.
Les longueurs sont dans l'unite du document.
"""
import json
import math

import Rhino
import System
import scriptcontext as sc
from Rhino.Display import Color4f
from Rhino.DocObjects import ObjectMaterialSource as Src
from Rhino.Render import RenderContent, RenderContentType, RenderTexture, SimulatedTexture

CC = RenderContent.ChangeContexts.Program
SAUTER = RenderTexture.TextureGeneration.Skip

# Types de materiaux ajoutes par D5 Lite a Rhino (D5 Lite pour Rhino 1.2.0.0017).
TYPES_D5 = {
    "generic": "b7a1c2d3-e4f5-6789-0abc-def123456789",
    "glass": "c8d2e3f4-a5b6-7890-1cde-f23456789abc",
    "metal": "d9e3f4a5-b6c7-8901-2def-345678901bcd",
    "emissive": "eaf4b5c6-d7e8-9012-3efa-456789012cde",
    "water": "9e7eb860-dc9a-4224-b53d-8be0a6b7da9b",
    "grass": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "sheer": "ef0e8427-e297-4337-a2ce-09abbd0ca2ee",
}
TYPE_PBR_RHINO = "5a8d7b9b-cdc9-49de-8c16-2ef64fb097ab"
# Canaux qui acceptent une texture, par ordre d'essai.
CANAUX_TEXTURE = ["base-color", "normal", "roughness", "specular", "opacity", "metallic", "emissive"]


class ErreurMateriau(Exception):
    pass


def j(valeur):
    """Met un resultat en JSON lisible."""
    return json.dumps(valeur, indent=2, sort_keys=True, default=str)


# ------------------------------------------------------------------ outils
def _doc():
    return sc.doc


def _guid(texte):
    return System.Guid(str(texte).strip("{}"))


def _couleur(valeur):
    if isinstance(valeur, Color4f):
        return valeur
    if isinstance(valeur, str):
        t = valeur.lstrip("#")
        if len(t) != 6:
            raise ErreurMateriau("Couleur invalide : %s" % valeur)
        return Color4f(int(t[0:2], 16) / 255.0, int(t[2:4], 16) / 255.0, int(t[4:6], 16) / 255.0, 1.0)
    v = [float(x) for x in valeur]
    if max(v) > 1.0:
        v = [x / 255.0 for x in v]
    return Color4f(v[0], v[1], v[2], v[3] if len(v) > 3 else 1.0)


def _hex(c):
    return "#%02X%02X%02X" % (int(round(c.R * 255)), int(round(c.G * 255)), int(round(c.B * 255)))


def _nom_type(rm):
    tid = str(rm.TypeId).lower()
    for nom, g in TYPES_D5.items():
        if g == tid:
            return nom
    return None


def _trouver(nom):
    for m in _doc().RenderMaterials:
        if m.Name == nom:
            return m
    raise ErreurMateriau("Materiau introuvable : %s" % nom)


def _existe(nom):
    return any(m.Name == nom for m in _doc().RenderMaterials)


def _params(rm):
    resultat = {}
    for f in rm.Fields:
        try:
            v = f.ValueAsObject()
        except Exception:
            continue
        if isinstance(v, Color4f):
            v = _hex(v)
        resultat[f.Name] = v
    return resultat


def _ecrire_params(rm, params):
    connus = set(f.Name for f in rm.Fields)
    refuses = [k for k in params if k not in connus]
    if refuses:
        raise ErreurMateriau("Parametres inconnus pour %s : %s. Connus : %s"
                             % (rm.TypeName, ", ".join(refuses), ", ".join(sorted(connus))))
    rm.BeginChange(CC)
    try:
        for k, v in params.items():
            ancien = rm.Fields.GetField(k).ValueAsObject()
            if isinstance(ancien, Color4f):
                v = _couleur(v)
            elif isinstance(ancien, bool):
                v = bool(v)
            else:
                v = float(v)
            rm.SetParameter(k, v)
    finally:
        rm.EndChange()


def _texture_info(rm, canal):
    t = rm.FindChild(canal)
    if t is None:
        return None
    info = {"actif": bool(rm.ChildSlotOn(canal)), "type": t.TypeName}
    try:
        info["fichier"] = t.SimulatedTexture(SAUTER).Filename
    except Exception:
        info["fichier"] = None
    try:
        r, o, a = t.GetRepeat(), t.GetOffset(), t.GetRotation()
        info["repetition"] = [r.X, r.Y]
        info["decalage"] = [o.X, o.Y]
        info["rotation"] = a.Z
    except Exception:
        pass
    return info


def _textures(rm):
    resultat = {}
    for canal in CANAUX_TEXTURE:
        try:
            info = _texture_info(rm, canal)
        except Exception:
            info = None
        if info:
            resultat[canal] = info
    return resultat


def _indice_table(rm):
    """Indice de la table des materiaux lie a ce materiau de rendu. Le cree au besoin.

    Ne pas utiliser objet.RenderMaterial = rm : cette affectation ecrase une
    entree existante de la table, et D5 Lite ne recoit pas le changement.
    """
    doc = _doc()
    for i in range(doc.Materials.Count):
        m = doc.Materials[i]
        if not m.IsDeleted and not m.IsReference and m.RenderMaterialInstanceId == rm.Id and m.Name == rm.Name:
            return i
    m = rm.SimulatedMaterial(SAUTER)
    m.Name = rm.Name
    m.RenderMaterialInstanceId = rm.Id
    return doc.Materials.Add(m)


def _materiau_de_table(indice):
    doc = _doc()
    if indice is None or indice < 0 or indice >= doc.Materials.Count:
        return None
    m = doc.Materials[indice]
    rid = m.RenderMaterialInstanceId
    if rid == System.Guid.Empty:
        return None
    for rm in doc.RenderMaterials:
        if rm.Id == rid:
            return rm
    return None


def _materiau_de_canal(objet, indice_face):
    """Materiau de rendu pose sur une face. None si la face suit le materiau de base.

    Un canal de materiau designe une entree de la table des materiaux par son Id.
    """
    if objet.Geometry.Faces[indice_face].MaterialChannelIndex <= 0:
        return None
    # Rhino resout lui-meme le canal : c'est la seule lecture fiable.
    ci = Rhino.Geometry.ComponentIndex(Rhino.Geometry.ComponentIndexType.BrepFace, indice_face)
    rm = objet.GetRenderMaterial(ci)
    base = _base_objet(objet)
    if rm is None or (base is not None and rm.Id == base.Id):
        return None
    return rm


def _base_objet(objet):
    """Materiau de rendu de base d'un objet : celui de l'objet, sinon celui du calque."""
    a = objet.Attributes
    if a.MaterialSource == Src.MaterialFromObject:
        return _materiau_de_table(a.MaterialIndex)
    return _doc().Layers[a.LayerIndex].RenderMaterial


def _objets_document():
    reglages = Rhino.DocObjects.ObjectEnumeratorSettings()
    reglages.IncludeLights = False
    reglages.IncludeGrips = False
    reglages.HiddenObjects = True
    reglages.LockedObjects = True
    reglages.NormalObjects = True
    return list(_doc().Objects.GetObjectList(reglages))


def _objets_blocs():
    resultat = []
    for idef in _doc().InstanceDefinitions:
        if idef is None or idef.IsDeleted:
            continue
        for o in idef.GetObjects():
            resultat.append((idef.Name, o))
    return resultat


def _objet(identifiant):
    o = _doc().Objects.FindId(_guid(identifiant))
    if o is None:
        raise ErreurMateriau("Objet introuvable : %s" % identifiant)
    return o


def _liste(valeur):
    if isinstance(valeur, (list, tuple)):
        return list(valeur)
    return [valeur]


def _rafraichir():
    _doc().Views.Redraw()


# ------------------------------------------------------------- lecture
def types():
    """Types de materiaux D5 et leurs parametres par defaut."""
    resultat = {}
    for nom, g in TYPES_D5.items():
        c = RenderContentType.NewContentFromTypeId(_guid(g))
        if c is None:
            resultat[nom] = {"disponible": False}
            continue
        resultat[nom] = {"disponible": True, "nom_rhino": c.TypeName, "parametres": _params(c)}
    return resultat


def usages(nom):
    """Ou un materiau est utilise : calques, objets, contenus de blocs, faces."""
    rm = _trouver(nom)
    doc = _doc()
    u = {"calques": [], "objets": [], "blocs": [], "faces": []}
    for l in doc.Layers:
        if not l.IsDeleted and l.RenderMaterial is not None and l.RenderMaterial.Id == rm.Id:
            u["calques"].append(l.FullPath)
    for o in _objets_document():
        a = o.Attributes
        if a.MaterialSource == Src.MaterialFromObject:
            m = _materiau_de_table(a.MaterialIndex)
            if m is not None and m.Id == rm.Id:
                u["objets"].append(str(o.Id))
        if o.HasSubobjectMaterials:
            for ci in o.SubobjectMaterialComponents:
                try:
                    m = _materiau_de_canal(o, ci.Index)
                    if m is not None and m.Id == rm.Id:
                        u["faces"].append({"objet": str(o.Id), "face": ci.Index})
                except Exception:
                    pass
    for nom_bloc, o in _objets_blocs():
        a = o.Attributes
        if a.MaterialSource == Src.MaterialFromObject:
            m = _materiau_de_table(a.MaterialIndex)
            if m is not None and m.Id == rm.Id:
                u["blocs"].append({"bloc": nom_bloc, "objet": str(o.Id)})
    return u


def lire(nom):
    """Type, parametres, textures et usages d'un materiau."""
    rm = _trouver(nom)
    t = _nom_type(rm)
    return {"nom": rm.Name, "id": str(rm.Id), "type_rhino": rm.TypeName, "type_d5": t, "d5": t is not None,
            "parametres": _params(rm), "textures": _textures(rm), "usages": usages(nom)}


def inventaire(detail=False):
    """Liste des materiaux du document. detail=True ajoute parametres et textures."""
    resultat = []
    for rm in _doc().RenderMaterials:
        u = usages(rm.Name)
        ligne = {"nom": rm.Name, "type_rhino": rm.TypeName, "type_d5": _nom_type(rm),
                 "calques": len(u["calques"]), "objets": len(u["objets"]),
                 "blocs": len(u["blocs"]), "faces": len(u["faces"])}
        ligne["utilise"] = any(ligne[k] for k in ("calques", "objets", "blocs", "faces"))
        if detail:
            ligne["parametres"] = _params(rm)
            ligne["textures"] = _textures(rm)
        resultat.append(ligne)
    return resultat


def affectation(identifiant):
    """Materiau effectif d'un objet et mode d'affectation."""
    o = _objet(identifiant)
    a = o.Attributes
    doc = _doc()
    calque = doc.Layers[a.LayerIndex]
    r = {"objet": str(o.Id), "nom": a.Name, "calque": calque.FullPath, "source": str(a.MaterialSource),
         "materiau_calque": calque.RenderMaterial.Name if calque.RenderMaterial else None,
         "materiau_objet": None, "faces": [], "bloc": None}
    if a.MaterialSource == Src.MaterialFromObject:
        m = _materiau_de_table(a.MaterialIndex)
        r["materiau_objet"] = m.Name if m else None
    if a.MaterialSource == Src.MaterialFromObject:
        r["materiau_effectif"] = r["materiau_objet"]
    elif a.MaterialSource == Src.MaterialFromLayer:
        r["materiau_effectif"] = r["materiau_calque"]
    else:
        r["materiau_effectif"] = "herite du bloc parent"
    if o.HasSubobjectMaterials:
        for ci in o.SubobjectMaterialComponents:
            try:
                m = _materiau_de_canal(o, ci.Index)
                r["faces"].append({"face": ci.Index, "materiau": m.Name if m else None})
            except Exception:
                pass
    if isinstance(o, Rhino.DocObjects.InstanceObject):
        idef = o.InstanceDefinition
        r["bloc"] = {"definition": idef.Name, "contenu": []}
        for sous in idef.GetObjects():
            sa = sous.Attributes
            m = _materiau_de_table(sa.MaterialIndex) if sa.MaterialSource == Src.MaterialFromObject else None
            lc = doc.Layers[sa.LayerIndex]
            r["bloc"]["contenu"].append({
                "objet": str(sous.Id), "nom": sa.Name, "source": str(sa.MaterialSource),
                "materiau": m.Name if m else (lc.RenderMaterial.Name if (sa.MaterialSource == Src.MaterialFromLayer and lc.RenderMaterial) else None),
                "calque": lc.FullPath})
    return r


# ------------------------------------------------------------ creation
def creer(nom, type_d5="generic", parametres=None, textures=None):
    """Cree un materiau D5. textures : {"base-color": "C:/.../image.jpg"}."""
    if _existe(nom):
        raise ErreurMateriau("Un materiau porte deja ce nom : %s" % nom)
    if type_d5 not in TYPES_D5:
        raise ErreurMateriau("Type inconnu : %s. Types : %s" % (type_d5, ", ".join(sorted(TYPES_D5))))
    rm = RenderContentType.NewContentFromTypeId(_guid(TYPES_D5[type_d5]))
    if rm is None:
        raise ErreurMateriau("Le type D5 %s n'est pas disponible. Le plugin D5 Lite est-il charge ?" % type_d5)
    rm.Name = nom
    if parametres:
        _ecrire_params(rm, parametres)
    _doc().RenderMaterials.Add(rm)
    for canal, fichier in (textures or {}).items():
        texture(nom, canal, fichier=fichier)
    return lire(nom)


def modifier(nom, parametres=None, textures=None, nouveau_nom=None):
    """Modifie les parametres, les textures ou le nom d'un materiau."""
    rm = _trouver(nom)
    if parametres:
        _ecrire_params(rm, parametres)
    for canal, fichier in (textures or {}).items():
        texture(nom, canal, fichier=fichier)
    if nouveau_nom and nouveau_nom != nom:
        if _existe(nouveau_nom):
            raise ErreurMateriau("Un materiau porte deja ce nom : %s" % nouveau_nom)
        doc = _doc()
        rm.BeginChange(CC)
        rm.Name = nouveau_nom
        rm.EndChange()
        for i in range(doc.Materials.Count):
            m = doc.Materials[i]
            if not m.IsDeleted and m.RenderMaterialInstanceId == rm.Id:
                m.Name = nouveau_nom
                m.CommitChanges()
        nom = nouveau_nom
    _rafraichir()
    return lire(nom)


def dupliquer(nom, nouveau_nom):
    """Copie un materiau D5 sous un autre nom, avec ses parametres et ses textures."""
    source = lire(nom)
    if not source["d5"]:
        raise ErreurMateriau("%s n'est pas un materiau D5. Utilisez convertir()." % nom)
    creer(nouveau_nom, source["type_d5"], source["parametres"])
    for canal, t in source["textures"].items():
        if t.get("fichier"):
            texture(nouveau_nom, canal, fichier=t["fichier"], repetition=t.get("repetition"),
                    decalage=t.get("decalage"), rotation=t.get("rotation"), actif=t.get("actif"))
    return lire(nouveau_nom)


def supprimer(nom, forcer=False):
    """Supprime un materiau. Refuse si le materiau est utilise, sauf forcer=True."""
    rm = _trouver(nom)
    u = usages(nom)
    if any(u.values()) and not forcer:
        raise ErreurMateriau("%s est utilise : %s" % (nom, j(u)))
    return {"supprime": bool(_doc().RenderMaterials.Remove(rm)), "nom": nom}


# ------------------------------------------------------------ textures
def texture(nom, canal, fichier=None, repetition=None, decalage=None, rotation=None, actif=None, retirer=False):
    """Pose ou regle une texture sur un canal du materiau.

    repetition : [u, v] nombre de repetitions. decalage : [u, v]. rotation : degres.
    Ces trois reglages orientent la texture au niveau du materiau.
    """
    import os
    rm = _trouver(nom)
    if retirer:
        rm.BeginChange(CC)
        rm.DeleteChild(canal, CC)
        rm.EndChange()
        _rafraichir()
        return lire(nom)
    if fichier:
        if not os.path.isfile(fichier):
            raise ErreurMateriau("Fichier de texture introuvable : %s" % fichier)
        st = SimulatedTexture(_doc())
        st.Filename = fichier
        tex = RenderTexture.NewBitmapTexture(st, _doc())
        rm.BeginChange(CC)
        ok = rm.SetChild(tex, canal)
        rm.SetChildSlotOn(canal, True, CC)
        rm.EndChange()
        if not ok or rm.FindChild(canal) is None:
            raise ErreurMateriau("Le canal %s n'accepte pas de texture pour %s" % (canal, rm.TypeName))
    tex = rm.FindChild(canal)
    if tex is None:
        raise ErreurMateriau("Aucune texture sur le canal %s de %s" % (canal, nom))
    if repetition is not None or decalage is not None or rotation is not None:
        tex.BeginChange(CC)
        if repetition is not None:
            tex.SetRepeat(Rhino.Geometry.Vector3d(float(repetition[0]), float(repetition[1]), 1.0), CC)
        if decalage is not None:
            tex.SetOffset(Rhino.Geometry.Vector3d(float(decalage[0]), float(decalage[1]), 0.0), CC)
        if rotation is not None:
            tex.SetRotation(Rhino.Geometry.Vector3d(0.0, 0.0, float(rotation)), CC)
        tex.EndChange()
    if actif is not None:
        rm.BeginChange(CC)
        rm.SetChildSlotOn(canal, bool(actif), CC)
        rm.EndChange()
    _rafraichir()
    return {"nom": nom, "canal": canal, "texture": _texture_info(rm, canal)}


# ------------------------------------------------- echelle reelle
def _metres_par_unite():
    return Rhino.RhinoMath.UnitScale(_doc().ModelUnitSystem, Rhino.UnitSystem.Meters)


def _taille_image(fichier):
    try:
        import System.Drawing
        img = System.Drawing.Image.FromFile(fichier)
        t = (img.Width, img.Height)
        img.Dispose()
        return t
    except Exception:
        return None


def echelle(nom, largeur_m, hauteur_m=None, rotation=None, canaux=None):
    """Donne une taille reelle aux textures d'un materiau, en metres.

    largeur_m : largeur reelle d'une repetition de l'image. hauteur_m : par
    defaut, calculee d'apres les proportions de l'image.
    La texture passe en projection monde (boite) : sa taille ne depend plus
    de l'objet ni de ses coordonnees de surface. Tous les objets qui portent
    le materiau ont alors la meme echelle. D5 Lite affiche cette projection
    (verifie le 12.11.2026 : une repetition tous les 2 m).
    Pour revenir aux coordonnees de l'objet : echelle_objet(nom).
    """
    rm = _trouver(nom)
    u = _metres_par_unite()
    faits = {}
    for canal in (canaux or CANAUX_TEXTURE):
        tex = rm.FindChild(canal)
        if tex is None:
            continue
        h = hauteur_m
        if h is None:
            info = _texture_info(rm, canal)
            t = _taille_image(info.get("fichier")) if info else None
            h = float(largeur_m) * t[1] / float(t[0]) if t else float(largeur_m)
        mode = type(tex.GetProjectionMode())
        tex.BeginChange(CC)
        tex.SetProjectionMode(mode.WcsBox, CC)
        tex.SetRepeat(Rhino.Geometry.Vector3d(u / float(largeur_m), u / float(h), u / float(largeur_m)), CC)
        if rotation is not None:
            tex.SetRotation(Rhino.Geometry.Vector3d(0.0, 0.0, float(rotation)), CC)
        tex.EndChange()
        faits[canal] = {"largeur_m": float(largeur_m), "hauteur_m": round(h, 4)}
    if not faits:
        raise ErreurMateriau("%s n'a aucune texture." % nom)
    _rafraichir()
    return {"nom": nom, "projection": "monde (boite)", "canaux": faits}


def echelle_objet(nom, repetition=None, canaux=None):
    """Remet les textures d'un materiau sur les coordonnees de l'objet (placage ou UV)."""
    rm = _trouver(nom)
    faits = []
    for canal in (canaux or CANAUX_TEXTURE):
        tex = rm.FindChild(canal)
        if tex is None:
            continue
        mode = type(tex.GetProjectionMode())
        r = repetition or [1.0, 1.0]
        tex.BeginChange(CC)
        tex.SetProjectionMode(mode.MappingChannel, CC)
        tex.SetRepeat(Rhino.Geometry.Vector3d(float(r[0]), float(r[1]), 1.0), CC)
        tex.EndChange()
        faits.append(canal)
    _rafraichir()
    return {"nom": nom, "projection": "objet", "canaux": faits}


def lire_echelle(nom):
    """Taille reelle des textures d'un materiau, si elle est connue."""
    rm = _trouver(nom)
    u = _metres_par_unite()
    resultat = {"nom": nom, "canaux": {}}
    for canal in CANAUX_TEXTURE:
        tex = rm.FindChild(canal)
        if tex is None:
            continue
        mode = str(tex.GetProjectionMode())
        r = tex.GetRepeat()
        ligne = {"projection": mode, "repetition": [r.X, r.Y], "rotation": tex.GetRotation().Z}
        if mode in ("WcsBox", "Wcs") and r.X > 0 and r.Y > 0:
            ligne["largeur_m"] = round(u / r.X, 4)
            ligne["hauteur_m"] = round(u / r.Y, 4)
            ligne["echelle_reelle"] = True
        else:
            ligne["echelle_reelle"] = False
            ligne["remarque"] = "la taille depend du placage ou des coordonnees de chaque objet"
        resultat["canaux"][canal] = ligne
    return resultat


def echelles():
    """Echelle de toutes les textures du document. Sert au controle avant rendu."""
    resultat = []
    for rm in _doc().RenderMaterials:
        e = lire_echelle(rm.Name)
        for canal, ligne in e["canaux"].items():
            ligne = dict(ligne)
            ligne.update({"materiau": rm.Name, "canal": canal})
            resultat.append(ligne)
    return resultat


# ---------------------------------------------------------- affectation
def affecter_calque(nom, calques):
    """Pose le materiau sur un ou plusieurs calques (chemin complet ou nom)."""
    rm = _trouver(nom)
    doc = _doc()
    faits = []
    for c in _liste(calques):
        i = doc.Layers.FindByFullPath(c, -1)
        if i < 0:
            l = doc.Layers.FindName(c)
            if l is None:
                raise ErreurMateriau("Calque introuvable : %s" % c)
            i = l.Index
        l = doc.Layers[i]
        l.RenderMaterial = rm
        faits.append(l.FullPath)
    _rafraichir()
    return {"materiau": nom, "calques": faits}


def retirer_calque(calques):
    """Retire le materiau d'un ou plusieurs calques."""
    doc = _doc()
    faits = []
    for c in _liste(calques):
        l = doc.Layers.FindName(c)
        if l is None:
            raise ErreurMateriau("Calque introuvable : %s" % c)
        l.RenderMaterial = None
        faits.append(l.FullPath)
    _rafraichir()
    return {"calques": faits}


def _modifier_source(o, source, indice=None):
    a = o.Attributes.Duplicate()
    a.MaterialSource = source
    if indice is not None:
        a.MaterialIndex = indice
    return bool(_doc().Objects.ModifyAttributes(o, a, True))


def affecter_objets(nom, objets):
    """Pose le materiau sur des objets (source : objet). Vaut aussi pour une instance de bloc."""
    rm = _trouver(nom)
    i = _indice_table(rm)
    faits = [str(_objet(g).Id) for g in _liste(objets) if _modifier_source(_objet(g), Src.MaterialFromObject, i)]
    _rafraichir()
    return {"materiau": nom, "objets": faits, "mode": "objet"}


def affecter_par_calque(objets):
    """Remet des objets sur le materiau de leur calque."""
    faits = [str(_objet(g).Id) for g in _liste(objets) if _modifier_source(_objet(g), Src.MaterialFromLayer)]
    _rafraichir()
    return {"objets": faits, "mode": "calque"}


def affecter_par_parent(objets):
    """Fait heriter des objets du materiau de leur bloc parent."""
    faits = [str(_objet(g).Id) for g in _liste(objets) if _modifier_source(_objet(g), Src.MaterialFromParent)]
    _rafraichir()
    return {"objets": faits, "mode": "parent"}


def affecter_faces(nom, objet, faces):
    """Pose le materiau sur des faces d'une polysurface (materiau par face de Rhino 8).

    Les autres faces gardent le materiau de base de l'objet. D5 Lite affiche
    les materiaux par face (verifie le 12.11.2026).

    Mecanisme : la fonction reconstruit a chaque appel une entree de table
    neuve pour l'objet (source : objet). Les canaux y sont declares AVANT
    l'ajout a la table, par l'Id de l'entree de table de chaque materiau.
    Modifier les canaux d'une entree deja dans la table ne fonctionne pas.
    Les anciennes entrees restent dans la table : elles sont sans effet.
    """
    rm = _trouver(nom)
    return _poser_faces(objet, dict((int(f), rm) for f in _liste(faces)))


def _poser_faces(objet, changements):
    """changements : {indice de face: materiau de rendu, ou None pour le materiau de base}."""
    doc = _doc()
    o = _objet(objet)
    if not isinstance(o.Geometry, Rhino.Geometry.Brep):
        raise ErreurMateriau("Le materiau par face demande une polysurface.")
    nb = o.Geometry.Faces.Count
    if changements and max(changements) >= nb:
        raise ErreurMateriau("L'objet a %d faces." % nb)
    base_rm = _base_objet(o)
    voulu = {}
    for i in range(nb):
        actuel = _materiau_de_canal(o, i)
        if actuel is not None:
            voulu[i] = actuel
    for i, m in changements.items():
        if m is None:
            voulu.pop(i, None)
        else:
            voulu[i] = m
    # Entree de table neuve, canaux declares avant l'ajout.
    if base_rm is not None:
        m = base_rm.SimulatedMaterial(SAUTER)
        m.Name = base_rm.Name
        m.RenderMaterialInstanceId = base_rm.Id
    else:
        m = Rhino.DocObjects.Material()
        m.Name = "base_%s" % (o.Attributes.Name or str(o.Id)[:8])
    canaux = {}
    for face_rm in voulu.values():
        cle = str(face_rm.Id)
        if cle not in canaux:
            canaux[cle] = m.MaterialChannelIndexFromId(doc.Materials[_indice_table(face_rm)].Id, True)
            if canaux[cle] <= 0:
                raise ErreurMateriau("Canal de materiau non cree pour %s" % face_rm.Name)
    ib = doc.Materials.Add(m)
    _modifier_source(o, Src.MaterialFromObject, ib)
    o = _objet(objet)
    brep = o.Geometry.Duplicate()
    for i in range(nb):
        if i in voulu:
            brep.Faces[i].MaterialChannelIndex = canaux[str(voulu[i].Id)]
        else:
            brep.Faces[i].ClearMaterialChannelIndex()
    ok = doc.Objects.Replace(o.Id, brep)
    _rafraichir()
    o = _objet(objet)
    relu = {}
    for i in range(nb):
        r = _materiau_de_canal(o, i)
        if r is not None:
            relu[i] = r.Name
    verifie = all(relu.get(i) == voulu[i].Name for i in voulu) and len(relu) == len(voulu)
    return {"objet": str(o.Id), "fait": bool(ok) and verifie, "faces": relu,
            "materiau_de_base": base_rm.Name if base_rm else None}


def retirer_faces(objet, faces=None):
    """Remet des faces (toutes par defaut) sur le materiau de base de l'objet."""
    o = _objet(objet)
    indices = [int(f) for f in _liste(faces)] if faces is not None else list(range(o.Geometry.Faces.Count))
    return _poser_faces(objet, dict((i, None) for i in indices))


def eclater(objet):
    """Remplace une polysurface a materiaux par face par un objet par materiau.

    Utile pour un export ou un outil qui ne lit pas les materiaux par face.
    D5 Lite les lit : cette fonction n'est pas necessaire pour Lite.
    Chaque groupe de faces devient une polysurface avec son materiau pose sur
    l'objet. L'objet d'origine est supprime.
    """
    o = _objet(objet)
    doc = _doc()
    if not o.HasSubobjectMaterials:
        return {"objet": str(o.Id), "fait": False, "raison": "aucun materiau par face"}
    brep = o.Geometry
    groupes = {}
    for f in brep.Faces:
        rm = _materiau_de_canal(o, f.FaceIndex)
        groupes.setdefault(str(rm.Id) if rm else "", []).append(f.FaceIndex)
    crees = []
    for cle, indices in groupes.items():
        morceaux = [brep.Faces[i].DuplicateFace(False) for i in indices]
        joints = Rhino.Geometry.Brep.JoinBreps(morceaux, doc.ModelAbsoluteTolerance) or morceaux
        rm = None
        for m in doc.RenderMaterials:
            if str(m.Id) == cle:
                rm = m
        for b in joints:
            a = o.Attributes.Duplicate()
            if rm is not None:
                a.MaterialSource = Src.MaterialFromObject
                a.MaterialIndex = _indice_table(rm)
            nid = doc.Objects.AddBrep(b, a)
            crees.append({"objet": str(nid), "materiau": rm.Name if rm else "materiau de base", "faces": len(indices)})
    doc.Objects.Delete(o, True)
    _rafraichir()
    return {"origine": str(objet), "fait": True, "crees": crees}


def remplacer(ancien, nouveau):
    """Remplace un materiau par un autre partout : calques, objets, contenus de blocs."""
    a_rm, n_rm = _trouver(ancien), _trouver(nouveau)
    doc = _doc()
    u = usages(ancien)
    i = _indice_table(n_rm)
    bilan = {"calques": 0, "objets": 0, "blocs": 0, "faces_non_traitees": len(u["faces"])}
    for l in doc.Layers:
        if not l.IsDeleted and l.RenderMaterial is not None and l.RenderMaterial.Id == a_rm.Id:
            l.RenderMaterial = n_rm
            bilan["calques"] += 1
    for g in u["objets"]:
        if _modifier_source(_objet(g), Src.MaterialFromObject, i):
            bilan["objets"] += 1
    for b in u["blocs"]:
        o = doc.Objects.FindId(_guid(b["objet"]))
        if o is not None and _modifier_source(o, Src.MaterialFromObject, i):
            bilan["blocs"] += 1
    _rafraichir()
    return {"ancien": ancien, "nouveau": nouveau, "remplacements": bilan}


# ------------------------------------------- orientation des textures
def placage(objets, mode="boite", taille=1000.0, rotation=0.0, origine=None, canal=1):
    """Pose un placage de texture sur des objets : oriente et dimensionne la texture.

    mode : "boite", "plan" ou "surface" (retire le placage, retour aux UV de la surface).
    taille : cote d'une repetition de la texture, dans l'unite du document.
    rotation : degres autour de l'axe Z du monde. origine : [x, y, z], defaut = centre de l'objet.
    """
    doc = _doc()
    faits = []
    for g in _liste(objets):
        o = _objet(g)
        if mode == "surface":
            ok = doc.Objects.ModifyTextureMapping(o, canal, None)
            faits.append({"objet": str(o.Id), "mode": "surface", "fait": bool(ok)})
            continue
        bb = o.Geometry.GetBoundingBox(True)
        centre = Rhino.Geometry.Point3d(*origine) if origine else bb.Center
        plan = Rhino.Geometry.Plane(centre, Rhino.Geometry.Vector3d.ZAxis)
        plan.Rotate(math.radians(float(rotation)), Rhino.Geometry.Vector3d.ZAxis)
        d = float(taille) / 2.0
        ix = Rhino.Geometry.Interval(-d, d)
        if mode == "plan":
            tm = Rhino.Render.TextureMapping.CreatePlaneMapping(plan, ix, ix, ix)
        elif mode == "boite":
            tm = Rhino.Render.TextureMapping.CreateBoxMapping(plan, ix, ix, ix, True)
        else:
            raise ErreurMateriau("Mode de placage inconnu : %s" % mode)
        ok = doc.Objects.ModifyTextureMapping(o, canal, tm)
        faits.append({"objet": str(o.Id), "mode": mode, "taille": float(taille), "rotation": float(rotation), "fait": bool(ok)})
    _rafraichir()
    return faits


def lire_placage(objet, canal=1):
    """Lit le placage de texture d'un objet."""
    o = _objet(objet)
    tm = o.GetTextureMapping(canal)
    if tm is None:
        return {"objet": str(o.Id), "mode": "surface", "canaux": list(o.GetTextureChannels() or [])}
    return {"objet": str(o.Id), "mode": str(tm.MappingType), "canaux": list(o.GetTextureChannels() or [])}


# ---------------------------------------------------------- conversion
def _proposer_type(sim):
    """Choisit un type D5 pour un materiau Rhino simule."""
    if sim.IsPhysicallyBased:
        p = sim.PhysicallyBased
        e = p.Emission
        if max(e.R, e.G, e.B) > 0.05:
            return "emissive"
        if p.Opacity < 0.95:
            return "glass"
        if p.Metallic > 0.5:
            return "metal"
        return "generic"
    e = sim.EmissionColor
    if max(e.R, e.G, e.B) > 12:
        return "emissive"
    if sim.Transparency > 0.05:
        return "glass"
    return "generic"


def convertir(nom, type_d5=None, remplacer_usages=True, suffixe="_D5"):
    """Cree l'equivalent D5 d'un materiau Rhino et, par defaut, le met a sa place.

    La conversion reprend la couleur, la rugosite, l'opacite et la texture de
    couleur. Le materiau Rhino d'origine est garde.
    """
    rm = _trouver(nom)
    if _nom_type(rm):
        return {"nom": nom, "fait": False, "raison": "deja un materiau D5"}
    sim = rm.SimulatedMaterial(SAUTER)
    t = type_d5 or _proposer_type(sim)
    if sim.IsPhysicallyBased:
        p = sim.PhysicallyBased
        couleur, rugosite, opacite = p.BaseColor, p.Roughness, p.Opacity
        emission, ior = p.Emission, p.OpacityIOR
    else:
        d = sim.DiffuseColor
        couleur = Color4f(d.R / 255.0, d.G / 255.0, d.B / 255.0, 1.0)
        rugosite = 1.0 - min(1.0, sim.Shine / float(Rhino.DocObjects.Material.MaxShine))
        opacite = 1.0 - sim.Transparency
        e = sim.EmissionColor
        emission, ior = Color4f(e.R / 255.0, e.G / 255.0, e.B / 255.0, 1.0), sim.IndexOfRefraction
    params = {}
    if t == "emissive":
        params = {"emissive": emission}
    elif t == "glass":
        params = {"base-color": couleur, "roughness": rugosite, "opacity": opacite, "ior": max(1.0, min(2.5, ior))}
    elif t == "metal":
        params = {"base-color": couleur, "roughness": rugosite}
    else:
        params = {"base-color": couleur}
        if t == "generic":
            params["roughness"] = rugosite
    nouveau = nom + suffixe
    n = 2
    while _existe(nouveau):
        nouveau = "%s%s%d" % (nom, suffixe, n)
        n += 1
    creer(nouveau, t, params)
    textures = []
    try:
        tx = sim.GetBitmapTexture()
        if tx is not None and tx.FileName:
            texture(nouveau, "base-color", fichier=tx.FileName)
            textures.append(tx.FileName)
    except Exception as err:
        textures.append("texture non reprise : %s" % err)
    resultat = {"origine": nom, "nouveau": nouveau, "type_d5": t, "fait": True, "textures": textures}
    if remplacer_usages:
        resultat["remplacements"] = remplacer(nom, nouveau)["remplacements"]
    return resultat


def convertir_tous(seulement_utilises=True):
    """Convertit en D5 tous les materiaux Rhino du document."""
    resultat = []
    for ligne in inventaire():
        if ligne["type_d5"] or (seulement_utilises and not ligne["utilise"]):
            continue
        try:
            resultat.append(convertir(ligne["nom"]))
        except Exception as err:
            resultat.append({"origine": ligne["nom"], "fait": False, "raison": str(err)})
    return resultat


# --------------------------------------------------------------- audit
def audit():
    """Releve ce qui empeche un rendu fidele dans D5 Lite."""
    import os
    doc = _doc()
    r = {"calques_sans_materiau": [], "objets_sans_materiau": 0, "objets_materiau_par_face": [],
         "materiaux_rhino_utilises": [], "materiaux_inutilises": [], "textures_introuvables": [],
         "table_doublons": [], "resume": {}}
    peuples = set()
    for o in _objets_document():
        a = o.Attributes
        peuples.add(a.LayerIndex)
        if a.MaterialSource == Src.MaterialFromLayer and doc.Layers[a.LayerIndex].RenderMaterial is None:
            r["objets_sans_materiau"] += 1
        if a.MaterialSource == Src.MaterialFromObject and _materiau_de_table(a.MaterialIndex) is None:
            r["objets_sans_materiau"] += 1
        if o.HasSubobjectMaterials:
            r["objets_materiau_par_face"].append(str(o.Id))
    for l in doc.Layers:
        if not l.IsDeleted and l.Index in peuples and l.RenderMaterial is None:
            r["calques_sans_materiau"].append(l.FullPath)
    for ligne in inventaire(detail=True):
        if not ligne["utilise"]:
            r["materiaux_inutilises"].append(ligne["nom"])
        elif not ligne["type_d5"]:
            r["materiaux_rhino_utilises"].append({"nom": ligne["nom"], "type": ligne["type_rhino"]})
        for canal, t in ligne["textures"].items():
            if t.get("fichier") and not os.path.isfile(t["fichier"]):
                r["textures_introuvables"].append({"materiau": ligne["nom"], "canal": canal, "fichier": t["fichier"]})
    vus = {}
    for i in range(doc.Materials.Count):
        m = doc.Materials[i]
        if m.IsDeleted or m.RenderMaterialInstanceId == System.Guid.Empty:
            continue
        vus.setdefault(str(m.RenderMaterialInstanceId), []).append(i)
    for rid, indices in vus.items():
        if len(indices) > 1:
            nom = [m.Name for m in doc.RenderMaterials if str(m.Id) == rid]
            r["table_doublons"].append({"materiau": nom[0] if nom else rid, "indices": indices})
    r["resume"] = {
        "materiaux": doc.RenderMaterials.Count,
        "calques_sans_materiau": len(r["calques_sans_materiau"]),
        "objets_sans_materiau": r["objets_sans_materiau"],
        "objets_materiau_par_face": len(r["objets_materiau_par_face"]),
        "materiaux_rhino_utilises": len(r["materiaux_rhino_utilises"]),
        "textures_introuvables": len(r["textures_introuvables"]),
    }
    r["conseils"] = []
    if r["table_doublons"]:
        r["conseils"].append("Entrees de table en double : sans effet sur le rendu. Elles viennent d'affectations par face ou d'un script.")
    if r["calques_sans_materiau"]:
        r["conseils"].append("Posez un materiau sur ces calques : affecter_calque(nom, calques).")
    if r["materiaux_rhino_utilises"]:
        r["conseils"].append("Les materiaux Rhino s'affichent dans Lite. convertir(nom) donne acces aux reglages D5.")
    return r


# ------------------------------------------------------ bibliotheque
def exporter(chemin, noms=None):
    """Ecrit des materiaux D5 dans un fichier JSON, pour les reprendre dans un autre document."""
    donnees = []
    for rm in _doc().RenderMaterials:
        t = _nom_type(rm)
        if not t or (noms and rm.Name not in noms):
            continue
        donnees.append({"nom": rm.Name, "type_d5": t, "parametres": _params(rm), "textures": _textures(rm)})
    with open(chemin, "w") as f:
        f.write(json.dumps({"format": "d5mat-1", "materiaux": donnees}, indent=2, sort_keys=True))
    return {"fichier": chemin, "materiaux": [d["nom"] for d in donnees]}


def importer(chemin, ecraser=False):
    """Cree dans le document les materiaux D5 d'un fichier JSON ecrit par exporter()."""
    with open(chemin) as f:
        donnees = json.loads(f.read())
    bilan = {"crees": [], "modifies": [], "ignores": [], "textures_absentes": []}
    import os
    for d in donnees.get("materiaux", []):
        nom = d["nom"]
        if _existe(nom):
            if not ecraser:
                bilan["ignores"].append(nom)
                continue
            modifier(nom, d["parametres"])
            bilan["modifies"].append(nom)
        else:
            creer(nom, d["type_d5"], d["parametres"])
            bilan["crees"].append(nom)
        for canal, t in (d.get("textures") or {}).items():
            fichier = t.get("fichier")
            if fichier and os.path.isfile(fichier):
                texture(nom, canal, fichier=fichier, repetition=t.get("repetition"),
                        decalage=t.get("decalage"), rotation=t.get("rotation"), actif=t.get("actif"))
            elif fichier:
                bilan["textures_absentes"].append({"materiau": nom, "canal": canal, "fichier": fichier})
    _rafraichir()
    return bilan
