"""Outils MCP. Peu d'outils, descriptions courtes : elles entrent dans le contexte à chaque session."""
import json
from typing import Any, Dict, List, Optional

from mcp.types import ToolAnnotations

from photoshopmcp.server import DELAI_S, ErreurPont, PORT, get_pont, mcp

LECTURE = ToolAnnotations(readOnlyHint=True, openWorldHint=False)
DESTRUCTIF = ToolAnnotations(readOnlyHint=False, destructiveHint=True, openWorldHint=False)


def compact(resultat: Any) -> str:
    return json.dumps(resultat, ensure_ascii=False, separators=(",", ":"))


@mcp.tool(annotations=LECTURE)
def status() -> str:
    """État de la connexion au plugin Photoshop (version, Photoshop, execute_script autorisé)."""
    pont = get_pont()
    return compact({"connecte": pont.connecte(), "port": PORT, "plugin": pont.info,
                    "erreur": pont.erreur_ecoute or None, "journal": list(pont.journal) or None})


@mcp.tool(annotations=LECTURE)
def snapshot(sections: Optional[List[str]] = None, ids: Optional[List[int]] = None,
             offset: int = 0, limit: int = 300) -> str:
    """Lit le document actif en une passe. sections : doc (défaut), layers, guides, docs (documents ouverts).
    doc : id, name, w, h (pixels), res, mode, bits, layers (nombre de calques), saved, path.
    Commence sans layers, puis demande layers si besoin ; ids filtre des calques.
    layers : lignes compactes dans l'ordre de "cols", du haut vers le bas, valeurs nulles de fin omises ;
    paginé (offset, limit, "next"). Colonnes : id, t (P pixels, T texte, G groupe, S objet dynamique,
    F remplissage, A réglage), b [haut,gauche,bas,droite] en pixels, n nom, g id du groupe parent,
    x début du texte, h 1 = masqué, o opacité si < 100.
    docs : [id, nom, 1 si actif]."""
    return compact(get_pont().appeler("snapshot", {"sections": sections, "ids": ids,
                                                   "offset": offset, "limit": limit}))


@mcp.tool(annotations=DESTRUCTIF)
def batch(operations: List[Dict[str, Any]], stop_on_error: bool = True, dry_run: bool = False,
          summary: bool = False, single_undo: bool = True) -> str:
    """Exécute des opérations Photoshop en un seul aller-retour et une seule étape d'historique (Ctrl+Z).
    operations : [{"c": commande, "p": {paramètres}}]. Résultat : [{"i","ok","r"|"e"}].
    summary=true : résultat court {"n","ok","ids":[ids créés, null sinon],"ko":[{"i","e"}]}, pour un lot long.
    single_undo=false : une étape d'historique par action.
    "$n.champ" dans un paramètre = champ du résultat de l'opération n (0 = première).
    Mesures en pixels. bounds = [haut, gauche, bas, droite] depuis le coin haut gauche du document.
    color = [rouge, vert, bleu] de 0 à 255. "cible" = id ou ids:[...] (ids de calques).
    Commandes sur le document actif :
    create_layer {name?, group?:bool, opacity?} -> {id}
    set_text {text, id? | position:[x,y], size?, font? (nom PostScript), color?, name?} -> {id} (texte de point)
    place_image {path, bounds?, fit?:"proportional"|"fill"|"stretch", linked?, name?} -> {id} (objet dynamique)
    fill {color, bounds?, id?, opacity?, name?} -> {id} (sans id : nouveau calque ; retire la sélection en cours)
    set_bounds {id, bounds}
    set_props {cible, name?, visible?, opacity?, blend? (normal, multiply, screen...), locked?}
    move {cible, by:[dx,dy] | to:[x,y]}
    order {cible, to:"front"|"back" | above:id | below:id | into:id de groupe}
    transform {cible, scale?:% ou [l%,h%], rotate?:degrés, flip?:"horizontal"|"vertical"|"both"}
    duplicate {id, by?:[dx,dy], count?, name?} -> {ids}
    group {cible, name?} -> {id}
    delete_layer {cible}
    resize_image {width?, height?, resolution?} -> {w,h} (un seul côté : proportion gardée)
    resize_canvas {width, height, anchor?:"MIDDLECENTER"|"TOPLEFT"...} -> {w,h}
    crop {bounds} -> {w,h}
    flatten {}
    guides {h?:[y...], v?:[x...], clear?:bool}
    play {descriptors:[descripteurs batchPlay], options?} -> {r} (action non couverte par les autres commandes)
    preview {path (.jpg), max?:1024} -> {path,w,h} (image réduite, à lire pour un contrôle visuel)
    export {path (.png|.jpg|.psd), quality?:1-12} -> {path} (copie à la taille réelle)
    snapshot {mêmes paramètres que l'outil snapshot}
    Commandes hors groupe d'historique :
    new_document {width, height, resolution?:72, name?, fill?:"white"|"black"|"transparent"} -> {doc, name}
    open_document {path} -> {doc, name}
    select_document {doc: id ou nom} -> {doc, name}
    save_document {path? (.psd)} -> {path}
    close_document {save: true|false} (obligatoire ; false perd les modifications non enregistrées)
    undo {steps?} (un lot = une étape)
    Le dossier d'un fichier de sortie doit exister."""
    if not isinstance(operations, list) or not operations:
        raise ErreurPont("parametres", "operations doit être une liste non vide")
    for i, op in enumerate(operations):
        if not isinstance(op, dict) or not isinstance(op.get("c"), str):
            raise ErreurPont("parametres", "opération %d : il faut {\"c\": commande, \"p\": {...}}" % i)
    delai = max(DELAI_S, 300.0)  # un export ou un gros fichier peut durer plusieurs minutes
    resultat = get_pont().appeler("batch", {"operations": operations, "stop_on_error": stop_on_error,
                                            "dry_run": dry_run, "single_undo": single_undo}, delai=delai)
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
    """Exécute du JavaScript UXP dans Photoshop. Le code est le corps d'une fonction asynchrone : await est
    permis, « return valeur » rend le résultat (un objet revient en JSON). Variables fournies : app, core,
    action (action.batchPlay), constants, imaging, require. Le code tourne déjà dans executeAsModal, en une
    seule étape d'historique : n'appelle pas executeAsModal. Aucun état gardé entre deux appels.
    Pas d'alert ni de boîte de dialogue : elle bloque Photoshop. Mesures en pixels.
    À utiliser pour une boucle ou une logique que batch n'exprime pas ; sinon préfère batch.
    Refusé tant que la case « Autoriser les scripts JavaScript (UXP) » du panneau n'est pas cochée."""
    resultat = get_pont().appeler("execute_script", {"code": code}, delai=max(DELAI_S, 300.0))
    # Le plugin rend déjà un texte (JSON pour un objet) : pas de second encodage, qui doublerait les guillemets.
    return resultat if isinstance(resultat, str) else compact(resultat)
