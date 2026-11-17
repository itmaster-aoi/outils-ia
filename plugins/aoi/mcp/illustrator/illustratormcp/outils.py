"""Outils MCP. Peu d'outils, descriptions courtes : elles entrent dans le contexte à chaque session."""
import json
from typing import Any, Dict, List, Optional

from mcp.types import ToolAnnotations

from illustratormcp.server import DELAI_S, ErreurPont, PontIndisponible, get_pont, mcp

LECTURE = ToolAnnotations(readOnlyHint=True, openWorldHint=False)
DESTRUCTIF = ToolAnnotations(readOnlyHint=False, destructiveHint=True, openWorldHint=False)


def compact(resultat: Any) -> str:
    return json.dumps(resultat, ensure_ascii=False, separators=(",", ":"))


@mcp.tool(annotations=LECTURE)
def status() -> str:
    """État d'Illustrator : panneau connecté ou non, version, document actif, execute_script autorisé."""
    pont = get_pont()
    etat: Dict[str, Any] = {"canal": pont.nom}
    try:
        etat.update(pont.appeler("status", delai=10))
        etat["connecte"] = True
    except PontIndisponible as e:
        etat["connecte"] = False
        etat["aide"] = str(e)
    except ErreurPont as e:
        etat["connecte"] = False
        etat["erreur"] = str(e)
    etat.update(pont.etat())  # après l'appel : l'état du canal est à jour
    return compact(etat)


@mcp.tool(annotations=LECTURE)
def snapshot(sections: Optional[List[str]] = None, artboards: str = "", layer: Optional[str] = None,
             ids: Optional[List[str]] = None, offset: int = 0, limit: int = 300) -> str:
    """Lit le document actif en une passe. sections : doc, artboards (défaut), items, links.
    Commence sans items, puis demande items pour les plans de travail utiles : artboards = "1-4" ou "1,3" ;
    layer et ids filtrent. doc.u = unité des règles : toutes les longueurs sont dans cette unité.
    doc.layers : [nom, nombre d'objets, état]. artboards : [numéro, nom, largeur, hauteur].
    items et links : lignes compactes dans l'ordre de "cols", valeurs nulles de fin omises ; items paginés
    (offset, limit, "next"). items : id (vaut pour la session), t (P tracé, C tracé composé, T texte, I image liée,
    R image incorporée, G groupe, S symbole, X autre), a plan de travail (0 = hors plan), b [haut,gauche,bas,droite]
    dans le plan, l rang du calque dans "layers", n nom, x début du texte, f fichier lié, g id du groupe parent,
    s état (H masqué, L verrouillé). links : id, n fichier, d rang du dossier dans "dirs", a plan, s état."""
    return compact(get_pont().appeler("snapshot", {"sections": sections, "artboards": artboards, "layer": layer,
                                                   "ids": ids, "offset": offset, "limit": limit}))


@mcp.tool(annotations=DESTRUCTIF)
def batch(operations: List[Dict[str, Any]], stop_on_error: bool = True, dry_run: bool = False,
          summary: bool = False) -> str:
    """Exécute des opérations Illustrator en un seul aller-retour et une seule annulation (Ctrl+Z).
    operations : [{"c": commande, "p": {paramètres}}]. Résultat : [{"i","ok","r"|"e"}].
    summary=true : résultat court {"n","ok","ids":[ids créés, null sinon],"ko":[{"i","e"}]}, pour un lot long.
    "$n.champ" dans un paramètre = champ du résultat de l'opération n (0 = première).
    bounds = [haut, gauche, bas, droite] dans le plan de travail, Y vers le bas, unité des règles du document.
    artboard = numéro (1 = premier) ou nom ; absent = plan actif. Cible = id, ou ids:[...].
    Couleur : "none", "#rrggbb", [c,m,y,k] ou nom de nuance. "apparence" ci-dessous =
    name?, layer?, fill?, stroke?, stroke_width? (points), opacity? (0-100).
    Préfère grid, duplicate et ids à une opération par objet.
    Commandes :
    new_document {width, height, units?:"mm", artboards?, color?:"cmyk"|"rgb"} ; open_document {path}
    create_shape {artboard?, kind?:"rect"|"ellipse"|"line", bounds | kind:"path", points:[[x,y]], closed?, apparence} -> {id}
    create_text {text, artboard?, bounds (bloc) | at:[x,y] (texte de point), size?, font? (nom PostScript), apparence} -> {id}
    place_image {path, artboard?, bounds | at, fit?:"proportional"|"fill"|"stretch", name?, layer?} -> {id} (fill = groupe écrêté)
    grid {area:bounds, rows, cols, artboard?, gap?, images?:[chemins], fit?, kind?:"rect"|"text", name?, layer?, fill?, stroke?} -> {ids}
    set_text {id, text} ; set_bounds {id, bounds, artboard?}
    set_props {cible, apparence, size?, font?, hidden?, locked?}
    move {cible, by:[dx,dy] | to:[x,y], artboard?} ; order {cible, to:"front"|"back"|"forward"|"backward"}
    duplicate {id, by?:[dx,dy], count?} -> {ids} ; delete_item {cible} ; group {ids, name?} -> {id}
    select {cible?} (sans cible : rien de sélectionné) ; menu {command} (executeMenuCommand, agit sur la sélection)
    add_artboard {width, height, name?} -> {artboard} ; set_artboard {artboard, name?, width?, height?, active?}
    add_layer {name}
    change_text {find, change?, regex?, ignore_case?} -> {n} (sans change : compte seulement)
    relink {id | name (nom de fichier : tous les liens de ce nom), path} -> {n, ids}
    preview {path (.png), artboard?, dpi?} -> {path} (image du plan de travail, à lire pour un contrôle visuel)
    export {dir, format:"pdf"|"png"|"jpg"|"svg", artboards?:"1-3", prefix?, dpi?, preset?} -> {dir, files} (un fichier par plan)
    save_document {path?} (.ai ou .pdf : le document ouvert devient ce fichier ; un seul PDF de plusieurs pages)
    undo {steps?} (seule dans son lot ; un lot = une étape)
    snapshot {mêmes paramètres que l'outil snapshot}"""
    if not isinstance(operations, list) or not operations:
        raise ErreurPont("parametres", "operations doit être une liste non vide")
    for i, op in enumerate(operations):
        if not isinstance(op, dict) or not isinstance(op.get("c"), str):
            raise ErreurPont("parametres", "opération %d : il faut {\"c\": commande, \"p\": {...}}" % i)
    delai = max(DELAI_S, 300.0)  # un export peut durer plusieurs minutes
    resultat = get_pont().appeler("batch", {"operations": operations, "stop_on_error": stop_on_error,
                                            "dry_run": dry_run}, delai=delai)
    if summary and isinstance(resultat, list):
        reussis = [x for x in resultat if x.get("ok")]
        ids: List[Any] = []
        for x in reussis:
            r = x.get("r") if isinstance(x.get("r"), dict) else {}
            ids.extend(r["ids"] if isinstance(r.get("ids"), list) else [r.get("id")])
        resultat = {"n": len(operations), "ok": len(reussis), "ids": ids,
                    "ko": [{"i": x.get("i"), "e": x.get("e")} for x in resultat if not x.get("ok")]}
    return compact(resultat)


@mcp.tool(annotations=DESTRUCTIF)
def execute_script(code: str) -> str:
    """Exécute de l'ExtendScript (JSX, ES3 : var, pas de let ni de =>) dans Illustrator et rend sa dernière valeur.
    Un objet ou un tableau revient en JSON ; pas d'objet JSON : $.global.__aimcp.json(v) écrit du JSON.
    Une erreur donne sa ligne. Une seule annulation par appel. $.global garde ses valeurs entre deux appels.
    Pas d'alert() : il bloque Illustrator. Ne fermez pas un document juste après l'avoir modifié :
    Illustrator peut s'arrêter ; désélectionnez, puis fermez dans un appel suivant, 3 s plus tard. Unité : points, Y vers le haut, repère du document.
    Créez par le document (doc.pathItems), pas par un calque : sinon doc.pageItems reste en retard.
    À utiliser pour une boucle ou une logique que batch n'exprime pas ; sinon préfère batch.
    Refusé sauf si l'utilisateur coche « Autoriser les scripts » dans le panneau Claude MCP."""
    get_pont().verifier_scripts()
    resultat = get_pont().appeler("execute_script", {"code": code}, delai=max(DELAI_S, 300.0))
    return resultat if isinstance(resultat, str) else compact(resultat)
