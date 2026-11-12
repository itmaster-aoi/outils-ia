# -*- coding: utf-8 -*-
"""Scene d'essai pour la campagne de tests de D5 Lite.

A executer DANS Rhino 8, par le serveur MCP Rhino, dans un document VIDE :

    import sys
    sys.path.insert(0, r"<dossier du skill>\\essais")
    import scene_essai; reload(scene_essai)
    print(scene_essai.construire())

construire() cree trois volumes, deux lumieres et une vue nommee, puis ecrit
les identifiants dans %TEMP%\\d5lite_essai\\scene.json. campagne.py lit ce fichier.
nettoyer() supprime ce que construire() a cree.
"""
import json
import os
import tempfile

import rhinoscriptsyntax as rs

CALQUE = "essai_d5lite"
VUE = "essai_d5lite_vue"
DOSSIER = os.environ.get("D5LITE_ESSAI") or os.path.join(tempfile.gettempdir(), "d5lite_essai")


def _boite(x0, y0, z0, x1, y1, z1, nom):
    g = rs.AddBox([(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
                   (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)])
    rs.ObjectName(g, nom)
    rs.ObjectLayer(g, CALQUE)
    return str(g)


def construire():
    """Cree la scene d'essai. Les longueurs sont en millimetres : utilisez un document en mm."""
    if rs.IsLayer(CALQUE):
        return {"fait": False, "raison": "le calque %s existe deja. Lancez nettoyer() d'abord." % CALQUE}
    rs.AddLayer(CALQUE)
    objets = [_boite(-4000, -4000, -200, 4000, 4000, 0, "essai_sol"),
              _boite(-1000, -1000, 0, 1000, 1000, 2000, "essai_cube"),
              _boite(-4000, 3800, 0, 4000, 4000, 3000, "essai_mur")]
    point = rs.AddPointLight((2500, -2000, 2500))
    rs.ObjectName(point, "essai_lumiere_point")
    rs.ObjectLayer(point, CALQUE)
    spot = rs.AddSpotLight((-2500, -2500, 3500), 1500, (0, 0, 1000))
    rs.ObjectName(spot, "essai_lumiere_spot")
    rs.ObjectLayer(spot, CALQUE)
    # La vue en perspective ne s'appelle pas toujours "Perspective".
    vues = [v for v in (rs.ViewNames() or []) if rs.IsViewPerspective(v)]
    if not vues:
        raise Exception("Aucune vue en perspective dans ce document.")
    vue = rs.CurrentView() if rs.CurrentView() in vues else vues[0]
    rs.CurrentView(vue)
    rs.ViewCameraTarget(vue, (7000, -9000, 4500), (0, 0, 1000))
    if VUE in (rs.NamedViews() or []):
        rs.DeleteNamedView(VUE)
    rs.AddNamedView(VUE, vue)
    rs.Redraw()
    if not os.path.isdir(DOSSIER):
        os.makedirs(DOSSIER)
    donnees = {"point": str(point), "spot": str(spot), "vue": VUE, "objets": objets,
               "document": (rs.DocumentPath() or "") + (rs.DocumentName() or "")}
    chemin = os.path.join(DOSSIER, "scene.json")
    with open(chemin, "w") as f:
        f.write(json.dumps(donnees, indent=2))
    return {"fait": True, "fichier": chemin, "suite": "Lancez D5LiteStart, puis campagne.py."}


def nettoyer():
    """Supprime la scene d'essai du document."""
    supprimes = 0
    if rs.IsLayer(CALQUE):
        for o in rs.ObjectsByLayer(CALQUE) or []:
            rs.DeleteObject(o)
            supprimes += 1
        rs.PurgeLayer(CALQUE)
    if VUE in (rs.NamedViews() or []):
        rs.DeleteNamedView(VUE)
    chemin = os.path.join(DOSSIER, "scene.json")
    if os.path.isfile(chemin):
        os.remove(chemin)
    return {"objets_supprimes": supprimes}
