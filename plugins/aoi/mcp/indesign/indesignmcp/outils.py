"""Outils MCP. Peu d'outils, descriptions courtes : elles entrent dans le contexte à chaque session."""
import json
from typing import Any, Dict, List, Optional

from mcp.types import ToolAnnotations

from indesignmcp.server import DELAI_S, ErreurPont, PORT, get_pont, mcp

LECTURE = ToolAnnotations(readOnlyHint=True, openWorldHint=False)
DESTRUCTIF = ToolAnnotations(readOnlyHint=False, destructiveHint=True, openWorldHint=False)


def compact(resultat: Any) -> str:
    return json.dumps(resultat, ensure_ascii=False, separators=(",", ":"))


@mcp.tool(annotations=LECTURE)
def status() -> str:
    """État de la connexion au plugin InDesign (version, InDesign, execute_script autorisé)."""
    pont = get_pont()
    return compact({"connecte": pont.connecte(), "port": PORT, "plugin": pont.info,
                    "erreur": pont.erreur_ecoute or None, "journal": list(pont.journal) or None})


@mcp.tool(annotations=LECTURE)
def snapshot(sections: Optional[List[str]] = None, pages: str = "", ids: Optional[List[int]] = None,
             offset: int = 0, limit: int = 300) -> str:
    """Lit le document actif en une passe. sections : doc, pages (défaut), items, links.
    Commence sans items, puis demande items pour les pages utiles : pages = "1-4" ou "1,3" ; ids filtre des objets.
    items et links : lignes compactes dans l'ordre de "cols", valeurs nulles de fin omises ; paginés
    (offset, limit, "next"). items : id, t (R rectangle, T texte, O ovale, P polygone, L ligne, G groupe),
    p page, b [haut,gauche,bas,droite] dans la page, n nom, x début du texte visible, f fichier lié.
    links : id, n nom, d rang du dossier dans "dirs", p page, s état (absent = normal)."""
    return compact(get_pont().appeler("snapshot", {"sections": sections, "pages": pages, "ids": ids,
                                                   "offset": offset, "limit": limit}))


@mcp.tool(annotations=DESTRUCTIF)
def batch(operations: List[Dict[str, Any]], stop_on_error: bool = True, dry_run: bool = False,
          summary: bool = False, single_undo: bool = True) -> str:
    """Exécute des opérations InDesign en un seul aller-retour et une seule annulation (Ctrl+Z).
    operations : [{"c": commande, "p": {paramètres}}]. Résultat : [{"i","ok","r"|"e"}].
    summary=true : résultat court {"n","ok","ids":[ids créés, null sinon],"ko":[{"i","e"}]}, pour un lot long.
    single_undo=false : plus rapide sur une page peu chargée, mais une annulation par action.
    "$n.champ" dans un paramètre = champ du résultat de l'opération n (0 = première).
    bounds = [haut, gauche, bas, droite] dans la page, unité du document ; page = nom de page ("1").
    "cible" = id ou ids:[...]. Préfère grid, duplicate et ids à une opération par objet.
    Commandes :
    create_frame {page, bounds, kind:"rect"|"text", name?} -> {id}
    grid {page, area:bounds, rows, cols, gap?, images?:[chemins], fit?, kind?, name?} -> {ids} (une cellule par image)
    place_image {path, id? | page+bounds, fit?:"proportional"|"fill"|"frame"|"content"|"center"} -> {id}
    set_text {text, id? | page+bounds} -> {id}
    set_bounds {id, bounds}
    set_props {cible, props?:{propriété DOM: valeur}, object_style?, paragraph_style?, fill?, stroke?} (noms)
    move {cible, by:[dx,dy] | to:[x,y]}
    duplicate {id, by?:[dx,dy], count?} -> {ids} (copie le contenu ; 30 fois plus rapide que place_image)
    duplicate_page {page, count?} -> {pages}
    delete_item {cible}
    add_pages {count?, after?} -> {pages}
    change_grep {find, change?} -> {n} (sans change : compte seulement)
    relink {link (id, ou nom : tous les liens de ce nom), path} -> {n, ids}
    preview {page, path (.png), dpi?} -> {path} (image de la page, à lire pour un contrôle visuel)
    export_pdf {path, preset?, pages?} -> {path}
    save_document {path?}
    undo {steps?} (un lot synchrone = une étape)
    snapshot {mêmes paramètres que l'outil snapshot}
    Le dossier d'un fichier de sortie doit exister."""
    if not isinstance(operations, list) or not operations:
        raise ErreurPont("parametres", "operations doit être une liste non vide")
    for i, op in enumerate(operations):
        if not isinstance(op, dict) or not isinstance(op.get("c"), str):
            raise ErreurPont("parametres", "opération %d : il faut {\"c\": commande, \"p\": {...}}" % i)
    delai = max(DELAI_S, 300.0)  # un export PDF peut durer plusieurs minutes
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
    """Exécute de l'ExtendScript (JSX, ES3 : var, pas de let ni de =>) dans InDesign et rend sa dernière valeur.
    Un objet ou un tableau revient en JSON ; JSON.stringify existe. Une erreur donne sa ligne. Une seule
    annulation par appel. Aucun état gardé entre deux appels. Pas d'alert() : il bloque InDesign.
    $.evalFile(new File(chemin)) lance un script .jsx existant. Coordonnées de la règle, pas de la page.
    À utiliser pour une boucle ou une logique que batch n'exprime pas ; sinon préfère batch.
    Refusé tant que la case « Autoriser les scripts ExtendScript (JSX) » du panneau n'est pas cochée."""
    resultat = get_pont().appeler("execute_script", {"code": code}, delai=max(DELAI_S, 300.0))
    # Le plugin rend déjà un texte (JSON pour un objet) : pas de second encodage, qui doublerait les guillemets.
    return resultat if isinstance(resultat, str) else compact(resultat)
