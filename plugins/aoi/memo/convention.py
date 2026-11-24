"""Convention de nommage des cerveaux CortexDB de l'atelier oï.

Un seul fichier, sans import local : le script se suffit à lui-même. Bibliothèque standard seulement.

Sous-commandes :
  garde                      crochet PreToolUse de Claude Code : lit l'appel sur stdin,
                             refuse une écriture CortexDB hors convention.
  memoires [tout | CHEMIN]   liste, en lecture seule, les fichiers de la mémoire Claude Code à
                             importer (tous les projets, ou un projet par son chemin), avec
                             l'identifiant proposé et l'état dans le cerveau.
  miroir                     crochet PostToolUse : après l'écriture d'un fichier de la mémoire
                             Claude Code, demande à Claude de l'écrire aussi dans le cerveau.
                             MEMO_MIROIR=0 le désactive.
  verifier ID [--meta JSON] [--outil knowledge_save]
                             contrôle un identifiant et ses métadonnées, sans rien écrire.
  analyser BASE [--nom NOM]  lit un cerveau (fichier cortexdb.db sur C:) en lecture seule
                             et écrit un rapport dans le dossier des rapports (<nom>-<date>).
  lire BASE ID [ID ...]      affiche le texte et les métadonnées d'éléments, en lecture seule.
  migrer TABLE [--base B] [--serveur EXE] [--simuler]
                             applique une table de renommage par le serveur CortexDB.
  tests                      lance les tests du script.

Les règles suivent thalamus (gateway/convention/convention.go) :
  - identifiant <nature>:<theme>:<sujet>, mots minuscules joints par des tirets ;
  - nature dans la liste fermée ; theme connu, ou thème d'attente + theme_proposed ;
  - status current ou replaced ; date AAAA-MM-JJ pour une nature datée ;
  - un document theme:<sujet> déclare un thème ;
  - un élément qui existe déjà garde son identifiant, mais ses métadonnées sont contrôlées.
"""

import csv
import datetime
import json
import os
import re
import sqlite3
import sys
import unicodedata

DOSSIER = os.path.dirname(os.path.abspath(__file__))
RACINE = os.path.dirname(DOSSIER)  # racine du plugin aoi (ou du dépôt de développement)
CONVENTION = os.path.join(DOSSIER, "convention.yaml")
INDICES = os.path.join(DOSSIER, "indices.json")
BASE_DEFAUT = os.path.join(os.path.expanduser("~"), ".cortexdb", "cortexdb.db")


def dossier_rapports():
    """Les rapports sont des données de l'utilisateur : jamais dans le plugin installé.
    MEMO_RAPPORTS l'emporte ; dans le dépôt de développement, son dossier rapports\\ ;
    sinon Documents\\memo\\rapports de l'utilisateur."""
    if os.environ.get("MEMO_RAPPORTS"):
        return os.environ["MEMO_RAPPORTS"]
    if os.path.isdir(os.path.join(RACINE, ".git")) and os.path.isdir(os.path.join(RACINE, "rapports")):
        return os.path.join(RACINE, "rapports")
    return os.path.join(os.path.expanduser("~"), "Documents", "memo", "rapports")
PREFIXE_THEME = "theme:"

MOT = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
FORME_ID = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*:[a-z0-9]+(-[a-z0-9]+)*:[a-z0-9]+(-[a-z0-9]+)*$")

# Outils CortexDB contrôlés : nom court -> (clé de l'identifiant, l'identifiant est-il nouveau possible)
OUTILS = {
    "knowledge_save": "knowledge_id",
    "ingest_document": "document_id",
    "memory_save": "memory_id",
    "knowledge_update": "knowledge_id",
}


# ---------------------------------------------------------------- convention

def lire_convention(chemin=CONVENTION):
    """Lit convention.yaml (sous-ensemble du YAML : listes de mots et valeurs simples)."""
    conv = {"natures": [], "dated": [], "themes": [], "producteurs": [], "unsorted": "unsorted",
            "near": 0.8, "emerge": 5, "version": 0}
    liste = None
    with open(chemin, encoding="utf-8") as f:
        for brute in f:
            ligne = brute.split("#", 1)[0].rstrip()
            if not ligne.strip():
                continue
            retrait = len(ligne) - len(ligne.lstrip())
            texte = ligne.strip()
            if texte.startswith("- "):
                if liste is None:
                    raise ValueError("élément de liste hors liste : " + brute.strip())
                conv[liste].append(texte[2:].strip())
                continue
            cle, _, valeur = texte.partition(":")
            cle, valeur = cle.strip(), valeur.strip()
            liste = None
            if cle in ("natures", "dated", "themes", "producteurs") and not valeur:
                liste = cle
            elif cle in ("unsorted",):
                conv[cle] = valeur
            elif cle in ("near",):
                conv[cle] = float(valeur)
            elif cle in ("emerge", "version"):
                conv[cle] = int(valeur)
            elif cle == "convention" and retrait == 0:
                continue
    verifier_convention(conv)
    return conv


def nom_valide(s):
    """Mot minuscule ou mots joints par des tirets, et pas un nombre (règle rights.Name)."""
    if not MOT.match(s or ""):
        return False
    try:
        float(s)
        return False
    except ValueError:
        return True


def verifier_convention(conv):
    if not conv["natures"]:
        raise ValueError("la convention n'a pas de natures")
    if not conv["themes"]:
        raise ValueError("la convention n'a pas de thèmes")
    if not conv["producteurs"]:
        raise ValueError("la convention n'a pas de producteurs (produit_par)")
    for genre in ("natures", "themes", "dated", "producteurs"):
        vus = set()
        for v in conv[genre]:
            if not nom_valide(v):
                raise ValueError("%s %r : mots minuscules joints par des tirets, pas un nombre" % (genre, v))
            if v in vus:
                raise ValueError("%s %r deux fois" % (genre, v))
            vus.add(v)
    for d in conv["dated"]:
        if d not in conv["natures"]:
            raise ValueError("nature datée %r hors de la liste des natures" % d)
    if conv["unsorted"] in conv["themes"] or not nom_valide(conv["unsorted"]):
        raise ValueError("thème d'attente %r invalide" % conv["unsorted"])
    for i, a in enumerate(conv["themes"]):
        for b in conv["themes"][i + 1:]:
            if noms_proches(a, b):
                raise ValueError("thèmes trop proches : %r et %r" % (a, b))


def distance(a, b):
    prec = list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        cour = [i] + [0] * len(b)
        for j in range(1, len(b) + 1):
            cour[j] = min(prec[j] + 1, cour[j - 1] + 1, prec[j - 1] + (a[i - 1] != b[j - 1]))
        prec = cour
    return prec[-1]


def noms_proches(a, b):
    """Règle CloseNames de thalamus."""
    racine = lambda s: s.replace("-", "").rstrip("s")
    if racine(a) == racine(b):
        return True
    return len(a) >= 4 and len(b) >= 4 and distance(a, b) <= 1


# ---------------------------------------------------------------- base locale

def ouvrir_lecture(base):
    chemin = os.path.abspath(base)
    lecteur = os.path.splitdrive(chemin)[0].upper()
    if lecteur != "C:":
        raise ValueError("base refusée : seul le lecteur C: est permis (%s)" % chemin)
    uri = "file:" + chemin.replace("\\", "/") + "?mode=ro"
    return sqlite3.connect(uri, uri=True, timeout=2)


def themes_declares(base):
    """Thèmes déclarés par un document theme:<sujet> du cerveau."""
    if not base or not os.path.exists(base):
        return []
    try:
        con = ouvrir_lecture(base)
        try:
            lignes = con.execute("select id from documents where id like 'theme:%'").fetchall()
        finally:
            con.close()
    except (sqlite3.Error, ValueError):
        return []
    return [r[0][len(PREFIXE_THEME):] for r in lignes if nom_valide(r[0][len(PREFIXE_THEME):])]


def existe(base, ident, memoire):
    if not base or not os.path.exists(base):
        return False
    try:
        con = ouvrir_lecture(base)
        try:
            table = "messages" if memoire else "documents"
            return con.execute("select 1 from %s where id = ?" % table, (ident,)).fetchone() is not None
        finally:
            con.close()
    except (sqlite3.Error, ValueError):
        return False


# ---------------------------------------------------------------- contrôle

class Refus(Exception):
    pass


def date_valide(s):
    try:
        datetime.date.fromisoformat(s)
        return len(s) == 10
    except (TypeError, ValueError):
        return False


def normaliser_login(valeur):
    """Login Windows -> nom de la convention : minuscules, sans accent, « . », « _ » et espace -> « - »."""
    s = unicodedata.normalize("NFKD", valeur or "")
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = re.sub(r"[._\s]+", "-", s)
    s = re.sub(r"[^a-z0-9-]", "", s)
    return re.sub(r"-+", "-", s).strip("-")


def login_windows():
    """Login Windows de la session (%USERNAME%), normalisé ; chaîne vide s'il est inconnu."""
    return normaliser_login(os.environ.get("USERNAME", ""))


def auteur_par_defaut(donne):
    """Auteur par défaut d'une analyse : la valeur donnée, sinon le login Windows."""
    return donne or login_windows()


def controler_auteur(conv, auteur, meta, champ="author", exiger_login=False):
    """Auteur = login Windows de la personne ; produit_par = agent qui a écrit le texte.
    exiger_login : le crochet exige le login Windows de la session (une écriture faite sur ce poste)."""
    erreurs = []
    login = login_windows()
    if not nom_valide(auteur or ""):
        erreurs.append("%s obligatoire : le login Windows de la personne, normalisé%s"
                       % (champ, " (ici : %s)" % login if login else ""))
    elif exiger_login and login and auteur != login:
        erreurs.append("%s = %r : sur ce poste, l'auteur est le login Windows normalisé, %s" % (champ, auteur, login))
    if meta.get("produit_par", "") not in conv["producteurs"]:
        erreurs.append("métadonnée produit_par obligatoire, une de : " + ", ".join(conv["producteurs"]))
    if erreurs:
        raise Refus(" ; ".join(erreurs))


def controler(conv, ident, meta, existe_deja=False, declares=(), seulement_meta=False):
    """Rend None si l'écriture suit la convention, sinon lève Refus avec la correction à faire.

    seulement_meta : knowledge_update, où l'identifiant ne change pas.
    L'auteur est contrôlé à part (controler_auteur), par le crochet.
    """
    meta = dict(meta or {})
    connus = list(conv["themes"]) + [d for d in declares if d not in conv["themes"]]
    attente = conv["unsorted"]
    erreurs = []  # toutes les erreurs, pour une seule correction

    statut = meta.get("status", "")
    if statut not in ("current", "replaced"):
        erreurs.append("métadonnée status obligatoire : current ou replaced")

    if ident.startswith(PREFIXE_THEME):
        sujet = ident[len(PREFIXE_THEME):]
        if not existe_deja:
            if not nom_valide(sujet):
                erreurs.append("identifiant theme:<sujet> : mots minuscules joints par des tirets")
            for k in connus + [attente]:
                if k == sujet:
                    erreurs.append("le thème %r existe déjà" % sujet)
                elif noms_proches(k, sujet) and meta.get("distinct_from") != k:
                    erreurs.append("le thème %r est proche de %r : utiliser %r, ou le nommer dans distinct_from" % (sujet, k, k))
        if erreurs:
            raise Refus(" ; ".join(erreurs))
        return None

    nature = meta.get("nature", "")
    nature_ok = nature in conv["natures"]
    if not nature_ok:
        erreurs.append("métadonnée nature obligatoire, une de : " + ", ".join(conv["natures"]))
    if "date" in meta or nature in conv["dated"]:
        if not date_valide(meta.get("date", "")):
            erreurs.append("métadonnée date obligatoire au format AAAA-MM-JJ pour la nature %r" % nature)

    theme = meta.get("theme", "")
    theme_id = theme
    theme_ok = True
    if theme != attente and theme not in connus:
        theme_ok = False
        if nom_valide(theme):
            erreurs.append("thème %r inconnu : mettre theme=%s, theme_proposed=%s, et l'identifiant %s:%s:<sujet> ; "
                           "thèmes connus : %s" % (theme, attente, theme, nature or "<nature>", theme, ", ".join(connus)))
        else:
            erreurs.append("métadonnée theme obligatoire, une de : %s, ou %s avec theme_proposed" % (", ".join(connus), attente))
    if theme == attente:
        propose = meta.get("theme_proposed", "")
        if propose in connus:
            erreurs.append("theme_proposed %r est un thème connu : mettre theme=%s" % (propose, propose))
        elif propose:
            if not nom_valide(propose):
                erreurs.append("theme_proposed : mots minuscules joints par des tirets, pas un nombre")
            theme_id = propose

    if not (seulement_meta or existe_deja):
        if not FORME_ID.match(ident):
            erreurs.append("identifiant de la forme <nature>:<theme>:<sujet>, mots minuscules joints par des tirets")
        elif nature_ok and theme_ok:
            prefixe = "%s:%s:" % (nature, theme_id)
            if not ident.startswith(prefixe):
                erreurs.append("l'identifiant commence par %r" % prefixe)
    if erreurs:
        raise Refus(" ; ".join(erreurs))
    return None


# ---------------------------------------------------------------- garde (crochet)

def nom_outil(tool_name):
    for court in OUTILS:
        if tool_name == court or tool_name.endswith("__" + court):
            return court
    return None


def garde(entree, conv=None, base=None):
    """Rend (refus: bool, message) pour un appel d'outil de Claude Code."""
    court = nom_outil(entree.get("tool_name", ""))
    if court is None:
        return False, ""
    args = entree.get("tool_input") or {}
    ident = str(args.get(OUTILS[court], ""))
    meta = args.get("metadata") or {}
    if court == "knowledge_update" and not args.get("metadata"):
        return False, ""
    conv = conv or lire_convention()
    base = base if base is not None else os.environ.get("CORTEXDB_PATH", BASE_DEFAUT)
    memoire = court == "memory_save"
    meta_txt = {k: str(v) for k, v in meta.items()}
    erreurs = []
    try:
        controler(conv, ident, meta_txt,
                  existe_deja=existe(base, ident, memoire),
                  declares=themes_declares(base),
                  seulement_meta=(court == "knowledge_update"))
    except Refus as r:
        erreurs.append(str(r))
    try:
        if court == "knowledge_update":
            if "author" in args:
                controler_auteur(conv, args.get("author"), meta_txt, exiger_login=True)
            elif meta_txt.get("produit_par", "") not in conv["producteurs"]:
                raise Refus("métadonnée produit_par obligatoire, une de : " + ", ".join(conv["producteurs"]))
        else:
            champ = "user_id" if memoire else "author"
            controler_auteur(conv, args.get(champ), meta_txt, champ, exiger_login=True)
    except Refus as r:
        erreurs.append(str(r))
    if erreurs:
        parties = [p for e in erreurs for p in e.split(" ; ")]
        return True, ("Convention CortexDB de l'atelier, memo (%s) : %d erreur(s) à corriger ensemble : %s. Voir %s."
                      % (court, len(parties), " ; ".join(parties), CONVENTION))
    return False, ""


# ---------------------------------------------------------------- miroir de la mémoire Claude Code (crochet PostToolUse)
# Phase de transition : chaque fichier de la mémoire Claude Code (…\.claude\projects\<projet>\memory\*.md)
# est aussi écrit dans le cerveau CortexDB local. Le crochet ne fait pas l'écriture : il la demande à Claude,
# qui passe par le serveur CortexDB de la session (une seule écriture à la base, contrôlée par le crochet garde).

MEMOIRE_CLAUDE = re.compile(r"[\\/]\.claude[\\/]projects[\\/][^\\/]+[\\/]memory[\\/][^\\/]+\.md$", re.IGNORECASE)
NATURE_PAR_TYPE = {
    "user": ("preference", "preference"),
    "feedback": ("preference", "preference, ou decision si le texte décrit un choix et sa raison"),
    "project": ("<nature>", "decision, fait ou etat, selon le texte"),
    "reference": ("reference", "reference"),
}


def lire_memoire_claude(chemin):
    """En-tête (name, description, type) et corps d'un fichier de la mémoire Claude Code."""
    with open(chemin, encoding="utf-8", errors="replace") as f:
        texte = f.read()
    entete, corps = {}, texte
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", texte, re.DOTALL)
    if m:
        corps = m.group(2)
        for ligne in m.group(1).splitlines():
            cle, sep, valeur = ligne.strip().partition(":")
            if sep and valeur.strip() and cle.strip() in ("name", "description", "type"):
                entete[cle.strip()] = valeur.strip().strip("\"'")
    return entete, corps.strip()


def elements_par_source(base):
    """{chemin source normalisé: (identifiant, texte)} des éléments du cerveau qui ont une métadonnée source."""
    if not base or not os.path.isfile(base):
        return {}
    try:
        con = ouvrir_lecture(base)
        try:
            lignes = con.execute("select id, metadata, content from messages where role = 'memory' "
                                 "union all select id, metadata, content from documents").fetchall()
        finally:
            con.close()
    except (sqlite3.Error, ValueError):
        return {}
    res = {}
    for ident, meta, texte in lignes:
        source = lire_meta(meta.decode("utf-8", "replace") if isinstance(meta, bytes) else meta).get("source", "")
        if source:
            res[os.path.normcase(os.path.abspath(source))] = (ident, texte or "")
    return res


def textes_du_cerveau(base):
    """[(identifiant, texte)] de tous les éléments du cerveau, pour chercher les copies presque identiques."""
    if not base or not os.path.isfile(base):
        return []
    try:
        con = ouvrir_lecture(base)
        try:
            return [(i, t or "") for i, t in con.execute(
                "select id, content from messages where role = 'memory' union all select id, content from documents")]
        finally:
            con.close()
    except (sqlite3.Error, ValueError):
        return []


def mots(texte):
    return re.findall(r"[^\W_]+", (texte or "").lower())


def ressemblance(a, b):
    """Indice de Jaccard des trigrammes de mots (règle Likeness de thalamus) ; par mots sous 3 mots."""
    ma, mb = mots(a), mots(b)
    n = 3 if len(ma) >= 3 and len(mb) >= 3 else 1
    ga = {" ".join(ma[i:i + n]) for i in range(len(ma) - n + 1)}
    gb = {" ".join(mb[i:i + n]) for i in range(len(mb) - n + 1)}
    if not ga or not gb:
        return 0.0
    commun = len(ga & gb)
    return commun / float(len(ga) + len(gb) - commun)


def inclusion(a, b):
    """Part des trigrammes de mots de a qu'on retrouve dans b : a est-il déjà contenu dans b ?"""
    ma, mb = mots(a), mots(b)
    n = 3 if len(ma) >= 3 else 1
    ga = {" ".join(ma[i:i + n]) for i in range(len(ma) - n + 1)}
    gb = {" ".join(mb[i:i + n]) for i in range(len(mb) - n + 1)}
    return len(ga & gb) / float(len(ga)) if ga else 0.0


def identifiant_existant(base, chemin):
    """Identifiant d'un élément du cerveau dont la métadonnée source est ce fichier, sinon None."""
    e = elements_par_source(base).get(os.path.normcase(os.path.abspath(chemin)))
    return e[0] if e else None


# ---------------------------------------------------------------- import des mémoires Claude Code existantes

def racine_projets():
    """Dossier des projets de Claude Code : %CLAUDE_CONFIG_DIR%\\projects, sinon %USERPROFILE%\\.claude\\projects."""
    config = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude")
    return os.path.join(config, "projects")


def encoder_projet(chemin):
    """Nom du dossier que Claude Code donne à un projet : chaque caractère hors lettre ASCII et chiffre devient « - »."""
    return re.sub(r"[^A-Za-z0-9]", "-", chemin.rstrip("\\/"))


def dossiers_memoire(cible, racine):
    """Dossiers memory visés : tous (« tout »), celui d'un projet (son chemin), ou un dossier memory donné."""
    if cible == "tout":
        return sorted(p for p in (os.path.join(racine, n, "memory") for n in os.listdir(racine)) if os.path.isdir(p)) \
            if os.path.isdir(racine) else []
    if os.path.basename(cible.rstrip("\\/")).lower() == "memory" and os.path.isdir(cible):
        return [cible]
    nom = encoder_projet(cible)
    if os.path.isdir(racine):
        for n in os.listdir(racine):
            if n.lower() == nom.lower() and os.path.isdir(os.path.join(racine, n, "memory")):
                return [os.path.join(racine, n, "memory")]
    raise ValueError("aucune mémoire Claude Code pour le projet %s (dossier attendu : %s)"
                     % (cible, os.path.join(racine, nom, "memory")))


def lister_memoires(cible, racine=None, base=None):
    """Fichiers de mémoire à importer, en lecture seule, avec l'identifiant proposé et l'état dans le cerveau."""
    racine = racine or racine_projets()
    base = base if base is not None else os.environ.get("CORTEXDB_PATH") or BASE_DEFAUT
    connus = elements_par_source(base)
    tous = textes_du_cerveau(base)
    seuil = lire_convention()["near"]
    res = []
    for dossier in dossiers_memoire(cible, racine):
        for nom in sorted(os.listdir(dossier)):
            chemin = os.path.join(dossier, nom)
            if not nom.lower().endswith(".md") or nom.upper() == "MEMORY.MD" or not os.path.isfile(chemin):
                continue
            entete, corps = lire_memoire_claude(chemin)
            if not corps:
                continue
            nature, consigne = NATURE_PAR_TYPE.get(entete.get("type", ""), ("<nature>", "la nature qui convient"))
            sujet = normaliser_login(entete.get("name") or nom[:-3]) or "a-nommer"
            existant = connus.get(os.path.normcase(os.path.abspath(chemin)))
            if existant:
                etat = "deja-importe" if existant[1].strip() == corps.strip() else "a-mettre-a-jour"
                ident = existant[0]
            else:
                etat, ident = "nouveau", "%s:<theme>:%s" % (nature, sujet)
                proche, valeur = None, 0.0
                for autre_id, texte in tous:
                    v = max(ressemblance(corps, texte), inclusion(corps, texte))
                    if v > valeur:
                        proche, valeur = autre_id, v
                if proche and valeur >= seuil:
                    etat, ident = "doublon-probable", proche
            res.append({"fichier": chemin, "type": entete.get("type", ""), "nature": consigne,
                        "identifiant": ident, "etat": etat, "corps": corps})
    return res


def miroir(entree, base=None):
    """Crochet PostToolUse : après l'écriture d'un fichier de la mémoire Claude Code, demande à Claude
    de l'écrire aussi dans le cerveau. Rend la sortie du crochet, ou None."""
    if os.environ.get("MEMO_MIROIR", "1") == "0":
        return None
    if entree.get("tool_name") not in ("Write", "Edit", "MultiEdit"):
        return None
    chemin = str((entree.get("tool_input") or {}).get("file_path") or "")
    if not MEMOIRE_CLAUDE.search(chemin) or os.path.basename(chemin).upper() == "MEMORY.MD":
        return None
    if not os.path.isfile(chemin):
        return None
    entete, corps = lire_memoire_claude(chemin)
    if not corps:
        return None
    base = base if base is not None else os.environ.get("CORTEXDB_PATH") or BASE_DEFAUT
    nature, consigne = NATURE_PAR_TYPE.get(entete.get("type", ""), ("<nature>", "la nature qui convient"))
    sujet = normaliser_login(entete.get("name") or os.path.splitext(os.path.basename(chemin))[0]) or "a-nommer"
    existant = identifiant_existant(base, chemin)
    login = login_windows() or "<login Windows normalisé>"
    if existant:
        cible = "réécris l'élément existant %s (même identifiant, contenu et métadonnées à jour)" % existant
    else:
        cible = ("memory_id %s:<theme>:%s, avec la nature : %s, et le thème choisi selon la skill /aoi:memo"
                 % (nature, sujet, consigne))
    texte = (
        "Miroir memo (phase de transition : double écriture). Le fichier de mémoire Claude Code %s vient d'être "
        "écrit. Enregistre maintenant le même fait dans le cerveau CortexDB local, sans demander de confirmation : "
        "appelle mcp__plugin_aoi_cortexdb__memory_save ; %s ; user_id %s ; scope user ; namespace assistant ; "
        "metadata : nature, theme, status current, date du jour (AAAA-MM-JJ) si la nature est datée, "
        "produit_par claude-code, source %s. content = le fait ci-dessous, tel quel. Si le crochet de convention "
        "refuse, corrige selon son message et relance. Confirme en une ligne. Fait :\n%s"
        % (chemin, cible, login, chemin, corps))
    return {"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": texte}}


def commande_miroir():
    try:
        r = miroir(json.loads(sys.stdin.buffer.read().decode("utf-8-sig")))
    except Exception:  # le miroir ne doit jamais gêner une écriture de fichier
        return 0
    if r:
        print(json.dumps(r, ensure_ascii=False))
    return 0


def lire(base, ident):
    """Texte et métadonnées d'un élément, lus en lecture seule (document ou mémoire)."""
    con = ouvrir_lecture(base)
    try:
        d = con.execute("select 'document', coalesce(title,''), coalesce(author,''), coalesce(metadata,''), coalesce(content,'') "
                        "from documents where id = ?", (ident,)).fetchone()
        if d is None:
            d = con.execute("select 'memoire', '', coalesce(s.user_id,''), coalesce(m.metadata,''), m.content from messages m "
                            "left join sessions s on s.id = m.session_id where m.id = ? and m.role = 'memory'", (ident,)).fetchone()
    finally:
        con.close()
    if d is None:
        return None
    genre, titre, auteur, meta, texte = d
    if isinstance(meta, bytes):
        meta = meta.decode("utf-8", "replace")
    return {"genre": genre, "id": ident, "titre": titre, "auteur": auteur, "metadata": meta, "texte": texte}


def commande_garde():
    brut = sys.stdin.buffer.read()
    try:
        entree = json.loads(brut.decode("utf-8-sig"))  # tolère la marque BOM (tube PowerShell)
    except ValueError:
        if b"cortexdb" in brut.lower():  # appel CortexDB illisible : refus, jamais de passage
            entree = None
        else:
            return 0
    if entree is None:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse", "permissionDecision": "deny",
            "permissionDecisionReason": "Convention CortexDB, memo : entrée du crochet illisible, écriture bloquée."}},
            ensure_ascii=False))
        return 0
    try:
        refus, message = garde(entree)
    except Exception as e:  # convention illisible : on refuse, plutôt que d'écrire hors convention
        refus, message = True, "Convention CortexDB illisible (%s) : écriture bloquée. Corriger convention.yaml." % e
    if refus:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": message}}, ensure_ascii=False))
    return 0


# ---------------------------------------------------------------- analyse d'un cerveau

def sans_accent(s):
    s = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def lire_indices(chemin=INDICES):
    with open(chemin, encoding="utf-8") as f:
        return json.load(f)


def proposer(conv, ind, ident, titre, texte, meta):
    """Propose (nature, theme, sujet, confiance, raison) pour un élément hors convention."""
    brut = sans_accent(ident)
    projet = brut.split("/", 1)[0] if "/" in brut else ""
    base_id = brut.rsplit("/", 1)[-1]
    base_id = re.sub(r"\.(md|txt|json|pdf)$", "", base_id)
    mots = re.split(r"[-_:. ]+", base_id)
    nature, raison = None, ""
    for n in (2, 1):
        tete = "-".join(mots[:n])
        if tete in ind["prefixes_nature"]:
            nature, raison = ind["prefixes_nature"][tete], "préfixe " + tete
            mots = mots[n:]
            break
    tout = " ".join([brut, sans_accent(titre), sans_accent(meta.get("categorie", ""))])
    if nature is None:
        for n, indices in ind["mots_nature"].items():
            if n in conv["natures"] and any(i in tout for i in indices):
                nature, raison = n, "mot du titre ou du chemin"
                break
    # L'identifiant et le titre pèsent trois fois plus que le début du texte.
    tete_theme = tout + " " + sans_accent(meta.get("namespace", ""))
    corps = sans_accent(texte[:400])
    scores = {}
    for t, indices in ind["mots_theme"].items():
        if t in conv["themes"]:
            scores[t] = sum(3 * tete_theme.count(i) + corps.count(i) for i in indices)
    theme = max(scores, key=scores.get) if scores and max(scores.values()) > 0 else conv["unsorted"]
    sujet = re.sub(r"[^a-z0-9]+", "-", "-".join(w for w in mots if w)).strip("-")
    # Ni date ni numéro de série dans le sujet : une série devient un seul document.
    sujet = re.sub(r"-(\d{4}-\d{2}-\d{2}|\d{8})$", "", sujet)
    sujet = re.sub(r"-\d{1,3}$", "", sujet)
    if sujet in ("", "lisezmoi", "readme", "plan", "index"):
        sujet = "-".join(x for x in (projet, brut.split("/")[-2] if brut.count("/") >= 2 else "", sujet) if x) or "a-nommer"
    elif projet and not sujet.startswith(projet):
        sujet = projet + "-" + sujet
    sujet = re.sub(r"-+", "-", sujet).strip("-")
    confiance = "haute" if nature and raison.startswith("préfixe") and theme != conv["unsorted"] else (
        "moyenne" if nature and theme != conv["unsorted"] else "basse")
    return nature, theme, sujet, confiance, raison


def date_de(meta, cree):
    for k in ("date",):
        if date_valide(str(meta.get(k, ""))):
            return meta[k]
    return (cree or "")[:10]


def producteur_de(ancien_auteur, memoire, ident=""):
    """produit_par déduit de l'ancien champ author (qui nommait souvent l'agent)."""
    a = sans_accent(ancien_auteur)
    if "relecture" in a or "agent" in a or (not a and "revues/" in sans_accent(ident)):
        return "agent-relecture", ""
    if "claude" in a or memoire:
        return "claude-code", ""
    if not a:
        return "claude-code", "produit_par supposé (author vide)"
    return "humain", ""


def login_de(valeur, alias, defaut):
    v = sans_accent(valeur).strip()
    v = alias.get(v, v)
    return v if nom_valide(v) else defaut


def analyser(base, nom, conv=None, ind=None, sortie=None, alias=None, auteur_defaut=""):
    """alias : {ancien login: login} ; auteur_defaut : login d'un élément sans auteur lisible."""
    conv = conv or lire_convention()
    ind = ind or lire_indices()
    alias = alias or {}
    con = ouvrir_lecture(base)
    try:
        docs = con.execute("select id, coalesce(title,''), coalesce(content,''), coalesce(metadata,'{}'), coalesce(created_at,''), "
                           "coalesce(author,'') from documents").fetchall()
        mems = con.execute("select m.id, '', m.content, coalesce(m.metadata,'{}'), coalesce(m.created_at,''), coalesce(s.user_id,'') "
                           "from messages m left join sessions s on s.id = m.session_id where m.role = 'memory'").fetchall()
    finally:
        con.close()
    declares = [d[0][len(PREFIXE_THEME):] for d in docs if d[0].startswith(PREFIXE_THEME)]
    lignes, inconnus = [], {}
    for genre, rangs in (("document", docs), ("memoire", mems)):
        for ident, titre, texte, meta_txt, cree, ancien_auteur in rangs:
            try:
                meta = json.loads(meta_txt) if meta_txt else {}
            except ValueError:
                meta = {}
            meta = {k: str(v) for k, v in meta.items()}
            remplace = bool(meta.get("superseded_by"))
            memoire = genre == "memoire"
            producteur, note_prod = (meta["produit_par"], "") if meta.get("produit_par") in conv["producteurs"] \
                else producteur_de(ancien_auteur, memoire, ident)
            auteur = login_de(ancien_auteur, alias, auteur_defaut) if memoire or nom_valide(sans_accent(ancien_auteur)) \
                else auteur_defaut
            note_auteur = "" if auteur else "auteur inconnu : donner --auteur-defaut"
            commun = {"author": auteur, "ancien_author": ancien_auteur, "produit_par": producteur}
            try:
                controler(conv, ident, meta, declares=declares)
                lignes.append(dict(commun, type=genre, ancien_id=ident, action="conforme", nouvel_id=ident,
                                   nature=meta.get("nature", ""), theme=meta.get("theme", ""),
                                   status=meta.get("status", ""), date=meta.get("date", ""),
                                   projet=meta.get("projet", ""), confiance="",
                                   remarque=" ; ".join(x for x in (note_auteur, note_prod) if x)))
                continue
            except Refus as r:
                motif = str(r)
            nature, theme, sujet, confiance, raison = proposer(conv, ind, ident, titre, texte, meta)
            if nature is None:
                tete = re.split(r"[-_:/. ]+", sans_accent(ident))[0]
                inconnus.setdefault(tete, []).append(ident)
            if note_auteur or note_prod:
                motif = " ; ".join(x for x in (raison or motif, note_auteur, note_prod) if x)
                raison = ""
            lignes.append({
                **commun,
                "type": genre, "ancien_id": ident,
                "action": "fusionner" if remplace else ("a-classer" if nature is None else "renommer"),
                "nouvel_id": "" if nature is None else "%s:%s:%s" % (nature, theme, sujet),
                "nature": nature or "", "theme": theme,
                "status": "replaced" if remplace else "current",
                "date": date_de(meta, cree), "projet": meta.get("projet", meta.get("namespace", "")),
                "confiance": confiance,
                "remarque": ("remplacé par " + meta["superseded_by"]) if remplace else (raison or motif)})
    regrouper_series(lignes)
    jour = datetime.date.today().isoformat()
    sortie = sortie or os.path.join(dossier_rapports(), "%s-%s" % (nom, jour))
    os.makedirs(sortie, exist_ok=True)
    champs = ["type", "ancien_id", "action", "nouvel_id", "nature", "theme", "status", "date", "projet",
              "author", "produit_par", "ancien_author", "confiance", "remarque"]
    with open(os.path.join(sortie, "inventaire.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=champs, delimiter=";")
        w.writeheader()
        w.writerows(lignes)
    ecrire_synthese(conv, nom, base, lignes, inconnus, sortie, jour)
    return sortie, lignes, inconnus


def regrouper_series(lignes):
    """Plusieurs éléments vers le même identifiant : le plus récent non remplacé est renommé,
    les autres sont fondus dedans. Le thème du gardé vaut pour toute la série."""
    groupes = {}
    for l in lignes:
        if l["nouvel_id"] and l["action"] != "conforme":
            groupes.setdefault(l["nouvel_id"], []).append(l)
    for cible, membres in groupes.items():
        if len(membres) < 2:
            continue
        vivants = [m for m in membres if m["status"] != "replaced"] or membres
        garde = max(vivants, key=lambda m: (m["date"], m["ancien_id"]))
        for m in membres:
            if m is garde:
                m["action"], m["status"] = "renommer", "current"
                m["remarque"] = "garde la série de %d éléments" % len(membres)
            else:
                m["action"], m["status"] = "fusionner", "replaced"
                m["remarque"] = "série : fondu dans %s (gardé : %s)" % (cible, garde["ancien_id"])
            m["theme"] = garde["theme"]
            m["nouvel_id"] = "%s:%s:%s" % (garde["nature"], garde["theme"], cible.split(":", 2)[2])
    # Contrôle final : un identifiant renommé n'apparaît qu'une fois.
    vus = {}
    for l in lignes:
        if l["action"] in ("renommer", "conforme"):
            if l["nouvel_id"] in vus:
                l["action"] = "a-classer"
                l["remarque"] = "collision avec " + vus[l["nouvel_id"]]
            else:
                vus[l["nouvel_id"]] = l["ancien_id"]


def compter(lignes, cle):
    c = {}
    for l in lignes:
        c[l[cle] or "(vide)"] = c.get(l[cle] or "(vide)", 0) + 1
    return sorted(c.items(), key=lambda x: -x[1])


def ecrire_synthese(conv, nom, base, lignes, inconnus, sortie, jour):
    seuil = conv["emerge"]
    candidats = {k: v for k, v in inconnus.items() if len(v) >= seuil}
    t = ["# Analyse du cerveau %s (%s)" % (nom, jour), "",
         "Base lue en lecture seule : `%s`. Convention version %d." % (base, conv["version"]), "",
         "## Bilan", "", "| Action | Nombre |", "|---|---|"]
    t += ["| %s | %d |" % kv for kv in compter(lignes, "action")]
    t += ["", "## Natures proposées", "", "| Nature | Nombre |", "|---|---|"]
    t += ["| %s | %d |" % kv for kv in compter(lignes, "nature")]
    t += ["", "## Thèmes proposés", "", "| Thème | Nombre |", "|---|---|"]
    t += ["| %s | %d |" % kv for kv in compter(lignes, "theme")]
    t += ["", "## Auteurs (login) et producteurs", "", "| Auteur | Nombre |", "|---|---|"]
    t += ["| %s | %d |" % kv for kv in compter(lignes, "author")]
    t += ["", "| produit_par | Nombre |", "|---|---|"]
    t += ["| %s | %d |" % kv for kv in compter(lignes, "produit_par")]
    t += ["", "## Éléments sans nature (à classer à la main)", ""]
    if inconnus:
        t += ["- `%s` : %d élément(s), par exemple `%s`" % (k, len(v), v[0]) for k, v in sorted(inconnus.items(), key=lambda x: -len(x[1]))]
    else:
        t += ["Aucun."]
    t += ["", "## Natures candidates", "",
          "Un même début d'identifiant revient au moins %d fois sans nature connue (seuil emerge). "
          "Voir LISEZMOI.md, section « Ajouter une nature », avant de l'ajouter." % seuil, ""]
    t += ["- `%s` (%d éléments)" % (k, len(v)) for k, v in candidats.items()] or ["Aucune."]
    t += ["", "## Confiance des propositions", "", "| Confiance | Nombre |", "|---|---|"]
    t += ["| %s | %d |" % kv for kv in compter([l for l in lignes if l["action"] != "conforme"], "confiance")]
    with open(os.path.join(sortie, "synthese.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(t) + "\n")


# ---------------------------------------------------------------- migration

import glob
import queue
import shutil
import subprocess
import threading
import time

ACTIONS = ("renommer", "fusionner", "supprimer", "conforme")
# Clés de métadonnées anciennes que la convention remplace, ou que le serveur gère lui-même.
CLES_RETIREES = {"importance", "kind", "namespace", "scope", "ttl_seconds", "recall_count", "last_recalled_at",
                 "superseded_by", "superseded_at", "categorie"}
VIDES_MCP = ("CORTEXDB_REMOTE", "CORTEXDB_GRPC_TOKEN", "CORTEXDB_EMBED_BASE_URL", "CORTEXDB_EMBED_API_KEY",
             "OPENAI_BASE_URL", "OPENAI_API_KEY", "CORTEXDB_LLM_BASE_URL", "CORTEXDB_LLM_URL", "CORTEXDB_LLM_API_KEY",
             "CORTEXDB_RERANK_BASE_URL", "CORTEXDB_RERANK_URL", "CORTEXDB_RERANK_API_KEY")


class ErreurMigration(Exception):
    pass


def serveur_defaut():
    racine = os.path.join(os.environ.get("LOCALAPPDATA", ""), "aoi", "serveurs")
    exes = sorted(glob.glob(os.path.join(racine, "cortexdb-server-*", "cortexdb-mcp.exe")))
    return exes[-1] if exes else ""


def lire_table(chemin):
    with open(chemin, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f, delimiter=";"))


def lire_meta(valeur):
    if not valeur:
        return {}
    try:
        m = json.loads(valeur)
    except ValueError:
        return {}
    return m if isinstance(m, dict) else {}


def etat_base(base):
    """Ce que la base contient, lu en lecture seule : {id: genre}, et les entités des mémoires."""
    con = ouvrir_lecture(base)
    try:
        ids = {r[0]: "document" for r in con.execute("select id from documents")}
        ids.update({r[0]: "memoire" for r in con.execute("select id from messages where role = 'memory'")})
        entites = {}
        for mid, nom, typ in con.execute(
                "select substr(e.from_node_id, 8), n.content, n.node_type from graph_edges e join graph_nodes n "
                "on n.id = e.to_node_id where e.from_node_id like 'memory:%' and e.edge_type = 'mentions'"):
            entites.setdefault(mid, []).append({"name": nom, "type": typ or "entity"})
        meta, contenus, auteurs = {}, {}, {}
        def col(table, nom):
            return nom if nom in {r[1] for r in con.execute("pragma table_info(%s)" % table)} else "''"
        for i, m, c, a in con.execute("select id, metadata, %s, %s from documents"
                                      % (col("documents", "content"), col("documents", "author"))):
            meta[i], contenus[i], auteurs[i] = lire_meta(m), c or "", a or ""
        for i, m, c in con.execute("select id, metadata, %s from messages where role = 'memory'"
                                   % col("messages", "content")):
            meta[i], contenus[i] = lire_meta(m), c or ""
    finally:
        con.close()
    return ids, entites, meta, contenus, auteurs


def deja_a_jour(l, genre, meta, ancienne_meta, contenu_base, auteur_base, dossier_table):
    """Vrai si réécrire la ligne sous le même identifiant ne changerait ni texte, ni métadonnées, ni auteur."""
    if any(ancienne_meta.get(k) != v for k, v in meta.items()):
        return False
    if genre == "document":
        # knowledge_save remplace les métadonnées : une ancienne clé retirée disparaîtrait.
        if any(k in CLES_RETIREES for k in ancienne_meta):
            return False
        if auteur_base != l["author"]:
            return False
    if l.get("contenu"):
        try:
            with open(os.path.join(dossier_table, l["contenu"]), encoding="utf-8") as f:
                if f.read().strip() != contenu_base.strip():
                    return False
        except OSError:
            return False
    return True


def nouvelles_meta(conv, ligne, ancienne, fusionnes):
    meta = {k: v for k, v in (ancienne or {}).items() if not k.startswith("_") and k not in CLES_RETIREES}
    meta.update({"nature": ligne["nature"], "theme": ligne["theme"], "status": ligne["status"] or "current",
                 "produit_par": ligne["produit_par"]})
    if ligne.get("date") and (ligne["nature"] in conv["dated"] or date_valide(ligne["date"])):
        meta["date"] = ligne["date"]
    if ligne.get("projet"):
        meta["projet"] = ligne["projet"]
    if ligne["ancien_id"] != ligne["nouvel_id"]:
        meta["replaces"] = ligne["ancien_id"]
    if fusionnes:
        meta["fusionne"] = ", ".join(sorted(fusionnes))
    if ligne.get("ancien_author") and ligne["ancien_author"] != ligne["author"]:
        meta["ancien_author"] = ligne["ancien_author"]
    return {k: str(v) for k, v in meta.items()}


def planifier(conv, lignes, base, dossier_table):
    """Rend (ecritures, suppressions, deja_faits, problemes). Lecture seule."""
    ids, entites, meta_docs, contenus, auteurs = etat_base(base)
    problemes, ecritures, suppressions, deja = [], [], [], []
    cibles = {}
    for l in lignes:
        if l["action"] not in ACTIONS:
            problemes.append("%s : action %r inconnue (attendu : %s)" % (l["ancien_id"], l["action"], ", ".join(ACTIONS)))
        if l["action"] in ("renommer", "conforme"):
            if l["nouvel_id"] in cibles:
                problemes.append("%s : identifiant %s déjà écrit par %s" % (l["ancien_id"], l["nouvel_id"], cibles[l["nouvel_id"]]))
            cibles[l["nouvel_id"]] = l["ancien_id"]
    fusions = {}
    for l in lignes:
        if l["action"] == "fusionner":
            if l["nouvel_id"] not in cibles:
                problemes.append("%s : fusion vers %s, qu'aucune ligne n'écrit" % (l["ancien_id"], l["nouvel_id"]))
            fusions.setdefault(l["nouvel_id"], []).append(l["ancien_id"])
    for l in lignes:
        ancien, nouveau, action = l["ancien_id"], l["nouvel_id"], l["action"]
        present_ancien, present_nouveau = ancien in ids, (nouveau in ids) if nouveau else False
        if action in ("renommer", "conforme"):
            genre = ids.get(ancien) or ids.get(nouveau) or ("memoire" if l["type"] == "memoire" else "document")
            meta = nouvelles_meta(conv, l, meta_docs.get(ancien, {}), fusions.get(nouveau, []))
            try:
                controler(conv, nouveau, meta)
                controler_auteur(conv, l["author"], meta, "user_id" if genre == "memoire" else "author")
            except Refus as r:
                problemes.append("%s -> %s : %s" % (ancien, nouveau, r))
            contenu = l.get("contenu", "")
            if contenu and not os.path.isfile(os.path.join(dossier_table, contenu)):
                problemes.append("%s : fichier de contenu absent : %s" % (ancien, contenu))
            if not present_ancien and not present_nouveau:
                problemes.append("%s : absent de la base" % ancien)
            elif not present_ancien and ancien != nouveau:
                deja.append(ancien)
                continue
            ancienne_meta = meta_docs.get(ancien, {})
            a_jour = action == "conforme" and ancienne_meta.get("produit_par") and all(
                ancienne_meta.get(k) == v for k, v in meta.items() if k in ("nature", "theme", "status", "produit_par"))
            if action == "conforme" and a_jour:
                continue
            if action == "renommer" and ancien == nouveau and present_ancien and deja_a_jour(
                    l, genre, meta, ancienne_meta, contenus.get(ancien, ""), auteurs.get(ancien, ""), dossier_table):
                deja.append(ancien)
                continue
            ecritures.append({"ligne": l, "genre": genre, "meta": meta, "contenu": contenu,
                              "entites": entites.get(ancien, [])})
        if action in ("renommer", "fusionner", "supprimer") and ancien != nouveau:
            if present_ancien:
                suppressions.append({"ancien_id": ancien, "genre": ids[ancien], "action": action, "vers": nouveau})
            elif action != "renommer":
                deja.append(ancien)
    return ecritures, suppressions, deja, problemes


class ClientMCP:
    """Client MCP en stdio, bibliothèque standard seulement."""

    def __init__(self, exe, base, journal_err):
        env = dict(os.environ)
        for k in VIDES_MCP:
            env[k] = ""
        env["CORTEXDB_PATH"] = base
        self.err = open(journal_err, "a", encoding="utf-8")
        self.p = subprocess.Popen([exe], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.err, env=env,
                                  cwd=os.path.dirname(base), creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        self.q = queue.Queue()
        threading.Thread(target=self._lire, daemon=True).start()
        self.n = 0
        self.requete("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                    "clientInfo": {"name": "memo", "version": "1"}})
        self._envoyer({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def _lire(self):
        for ligne in iter(self.p.stdout.readline, b""):
            try:
                self.q.put(json.loads(ligne.decode("utf-8")))
            except ValueError:
                pass
        self.q.put(None)

    def _envoyer(self, msg):
        self.p.stdin.write((json.dumps(msg, ensure_ascii=False) + "\n").encode("utf-8"))
        self.p.stdin.flush()

    def requete(self, methode, params, delai=120):
        self.n += 1
        ident = self.n
        self._envoyer({"jsonrpc": "2.0", "id": ident, "method": methode, "params": params})
        fin = time.time() + delai
        while True:
            try:
                msg = self.q.get(timeout=max(0.1, fin - time.time()))
            except queue.Empty:
                raise ErreurMigration("le serveur CortexDB ne répond pas à %s" % methode)
            if msg is None:
                raise ErreurMigration("le serveur CortexDB s'est arrêté (voir serveur.log)")
            if msg.get("id") == ident:
                if "error" in msg:
                    raise ErreurMigration("%s : %s" % (methode, msg["error"]))
                return msg.get("result")

    def outil(self, nom, args):
        r = self.requete("tools/call", {"name": nom, "arguments": args})
        texte = "".join(c.get("text", "") for c in (r or {}).get("content", []))
        if (r or {}).get("isError"):
            raise ErreurMigration("%s : %s" % (nom, texte[:500]))
        try:
            return json.loads(texte) if texte else {}
        except ValueError:
            return {"texte": texte}

    def fermer(self):
        try:
            self.p.stdin.close()
            self.p.wait(timeout=10)
        except Exception:
            self.p.kill()
        self.err.close()


def serveur_actif():
    try:
        sortie = subprocess.run(["tasklist", "/FI", "IMAGENAME eq cortexdb-mcp.exe", "/NH"], capture_output=True,
                                text=True, timeout=20).stdout
    except (OSError, subprocess.SubprocessError):
        return True
    return "cortexdb-mcp.exe" in sortie.lower()


def sauvegarder(base, dossier):
    os.makedirs(dossier, exist_ok=True)
    cible = os.path.join(dossier, "cortexdb-%s.db" % datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))
    src = ouvrir_lecture(base)
    dst = sqlite3.connect(cible)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    return cible


def ecrire_element(client, e, dossier_table):
    l = e["ligne"]
    if e["genre"] == "memoire":
        ancien = client.outil("memory_get", {"memory_id": l["ancien_id"]}).get("memory") or \
            client.outil("memory_get", {"memory_id": l["nouvel_id"]}).get("memory")
    else:
        ancien = client.outil("knowledge_get", {"knowledge_id": l["ancien_id"]}).get("knowledge") or \
            client.outil("knowledge_get", {"knowledge_id": l["nouvel_id"]}).get("knowledge")
    if not ancien:
        raise ErreurMigration("%s : introuvable par le serveur" % l["ancien_id"])
    contenu = ancien.get("content", "")
    if e["contenu"]:
        with open(os.path.join(dossier_table, e["contenu"]), encoding="utf-8") as f:
            contenu = f.read().strip() + "\n"
    if e["genre"] == "memoire":
        anc_meta = ancien.get("metadata") or {}
        meta = dict(e["meta"])
        meta.update({k: str(v) for k, v in anc_meta.items() if not k.startswith("_") and k not in CLES_RETIREES and k not in meta})
        args = {"memory_id": l["nouvel_id"], "content": contenu, "metadata": meta, "user_id": l["author"],
                "scope": ancien.get("scope") or "user", "namespace": ancien.get("namespace") or "assistant"}
        importance = ancien.get("importance", anc_meta.get("importance"))
        if isinstance(importance, (int, float)) and importance:
            args["importance"] = importance
        if e["entites"]:
            args["entities"] = e["entites"]
        client.outil("memory_save", args)
        verif = client.outil("memory_get", {"memory_id": l["nouvel_id"]}).get("memory") or {}
    else:
        args = {"knowledge_id": l["nouvel_id"], "content": contenu, "metadata": e["meta"], "author": l["author"]}
        for k in ("title", "source_url"):
            if ancien.get(k):
                args[k] = ancien[k]
        client.outil("knowledge_save", args)
        verif = client.outil("knowledge_get", {"knowledge_id": l["nouvel_id"]}).get("knowledge") or {}
    if verif.get("content", "").strip() != contenu.strip():
        raise ErreurMigration("%s : relu après écriture, le contenu diffère" % l["nouvel_id"])
    return ancien


def migrer(table, base, exe, simuler, conv=None, controle_processus=True, sortie=print):
    conv = conv or lire_convention()
    dossier_table = os.path.dirname(os.path.abspath(table))
    lignes = lire_table(table)
    ecritures, suppressions, deja, problemes = planifier(conv, lignes, base, dossier_table)
    horodatage = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    plan = ["Migration %s" % ("simulée" if simuler else "réelle"), "Table : %s" % table, "Base : %s" % base,
            "Écritures : %d ; suppressions : %d ; déjà faits : %d ; problèmes : %d"
            % (len(ecritures), len(suppressions), len(deja), len(problemes)), ""]
    plan += ["PROBLÈME  " + p for p in problemes]
    for e in ecritures:
        l = e["ligne"]
        plan.append("ÉCRIRE    %-9s %s -> %s  [author=%s, produit_par=%s%s%s]" % (
            e["genre"], l["ancien_id"], l["nouvel_id"], l["author"], l["produit_par"],
            ", contenu=" + e["contenu"] if e["contenu"] else "", ", entités=%d" % len(e["entites"]) if e["entites"] else ""))
    for s in suppressions:
        plan.append("SUPPRIMER %-9s %s  (%s%s)" % (s["genre"], s["ancien_id"], s["action"], " vers " + s["vers"] if s["vers"] else ""))
    plan += ["DÉJÀ FAIT %s" % d for d in deja]
    chemin_plan = os.path.join(dossier_table, "plan-migration-%s.txt" % horodatage)
    with open(chemin_plan, "w", encoding="utf-8") as f:
        f.write("\n".join(plan) + "\n")
    sortie(plan[3])
    sortie("Plan : %s" % chemin_plan)
    if problemes:
        for p in problemes:
            sortie("PROBLÈME : " + p)
        sortie("Rien n'est écrit : corriger la table, puis relancer avec --simuler.")
        return 1
    if simuler:
        sortie("Simulation : rien n'est écrit dans la base.")
        return 0
    if not exe or not os.path.isfile(exe):
        raise ErreurMigration("serveur CortexDB introuvable : donner --serveur <cortexdb-mcp.exe>")
    if controle_processus and serveur_actif():
        raise ErreurMigration("un serveur CortexDB tourne (Claude Code ouvert) : fermer Claude Code, puis relancer")
    copie = sauvegarder(base, os.path.join(os.path.dirname(os.path.abspath(base)), "sauvegardes"))
    sortie("Sauvegarde : %s" % copie)
    chemin_journal = os.path.join(dossier_table, "journal-migration-%s.jsonl" % horodatage)
    client = ClientMCP(exe, base, os.path.join(dossier_table, "serveur-%s.log" % horodatage))
    try:
        nb_memoires = sum(1 for g in etat_base(base)[0].values() if g == "memoire")
        vues, curseur = [], None
        while True:
            page = client.outil("memory_list_all", dict({"limit": 200}, **({"cursor": curseur} if curseur else {})))
            vues += page.get("memories", [])
            curseur = page.get("next_cursor")
            if not page.get("truncated") or not curseur:
                break
        if len(vues) != nb_memoires:
            raise ErreurMigration("le serveur ne lit pas la base attendue (%d mémoires vues, %d dans %s) : rien n'est écrit"
                                  % (len(vues), nb_memoires, base))
        with open(chemin_journal, "a", encoding="utf-8") as j:
            for i, e in enumerate(ecritures, 1):
                ancien = ecrire_element(client, e, dossier_table)
                j.write(json.dumps({"etape": "ecrire", "ancien_id": e["ligne"]["ancien_id"], "nouvel_id": e["ligne"]["nouvel_id"],
                                    "genre": e["genre"], "ancien": ancien}, ensure_ascii=False) + "\n")
                j.flush()
                sortie("écrit %d/%d : %s" % (i, len(ecritures), e["ligne"]["nouvel_id"]))
            for i, s in enumerate(suppressions, 1):
                outil, cle, lire = ("memory_delete", "memory_id", "memory_get") if s["genre"] == "memoire" \
                    else ("knowledge_delete", "knowledge_id", "knowledge_get")
                ancien = client.outil(lire, {cle: s["ancien_id"]})
                client.outil(outil, {cle: s["ancien_id"]})
                j.write(json.dumps({"etape": "supprimer", "ancien_id": s["ancien_id"], "genre": s["genre"],
                                    "ancien": ancien.get("memory") or ancien.get("knowledge")}, ensure_ascii=False) + "\n")
                j.flush()
                sortie("supprimé %d/%d : %s" % (i, len(suppressions), s["ancien_id"]))
    finally:
        client.fermer()
    sortie("Journal : %s" % chemin_journal)
    sortie("Pour revenir en arrière : fermer Claude Code, puis copier %s sur %s." % (copie, base))
    return 0


# ---------------------------------------------------------------- tests

def tests():
    import tempfile
    import unittest

    conv = lire_convention()

    class TestsConvention(unittest.TestCase):
        def ok(self, ident, meta, **kw):
            controler(conv, ident, meta, **kw)

        def refus(self, ident, meta, **kw):
            with self.assertRaises(Refus):
                controler(conv, ident, meta, **kw)

        M = {"nature": "methode", "theme": "outils-cao", "status": "current"}

        # failing first : ce qui doit être refusé
        def test_ancienne_forme_refusee(self):
            self.refus("processus-gabarit", self.M)

        def test_prefixe_faux(self):
            self.refus("decision:outils-cao:x", self.M)

        def test_nature_inconnue(self):
            self.refus("procedure:outils-cao:x", dict(self.M, nature="procedure"))

        def test_status_absent(self):
            self.refus("methode:outils-cao:x", {"nature": "methode", "theme": "outils-cao"})

        def test_date_obligatoire_nature_datee(self):
            self.refus("decision:postes:x", {"nature": "decision", "theme": "postes", "status": "current"})

        def test_date_fausse(self):
            self.refus("decision:postes:x", {"nature": "decision", "theme": "postes", "status": "current", "date": "24.11.2026"})

        def test_theme_inconnu(self):
            self.refus("methode:acoustique:x", dict(self.M, theme="acoustique"))

        def test_majuscule_et_accent(self):
            self.refus("methode:outils-cao:Cartouche", self.M)
            self.refus("methode:outils-cao:mise-à-jour", self.M)

        def test_theme_proche(self):
            self.refus("theme:poste", {"status": "current"})

        def test_theme_existant(self):
            self.refus("theme:postes", {"status": "current"})

        def test_theme_nombre(self):
            self.refus("theme:2026", {"status": "current"})

        def test_propose_connu(self):
            self.refus("methode:a-trier:x", dict(self.M, theme="a-trier", theme_proposed="postes"))

        # ce qui doit passer
        def test_conforme(self):
            self.ok("methode:outils-cao:export-dwg-vers-pdf", self.M)

        def test_datee_conforme(self):
            self.ok("decision:postes:x", {"nature": "decision", "theme": "postes", "status": "current", "date": "2026-11-24"})

        def test_theme_propose(self):
            self.ok("methode:acoustique:x", dict(self.M, theme="a-trier", theme_proposed="acoustique"))

        def test_theme_declare(self):
            self.ok("methode:acoustique:x", dict(self.M, theme="acoustique"), declares=["acoustique"])

        def test_existant_garde_son_id(self):
            self.ok("projet-a-etat-16", {"nature": "etat", "theme": "outils-cao", "status": "current", "date": "2026-10-28"}, existe_deja=True)

        def test_existant_metadonnees_controlees(self):
            self.refus("projet-a-etat-16", {}, existe_deja=True)

        def test_nouveau_theme(self):
            self.ok("theme:acoustique", {"status": "current"})

        def test_theme_distinct(self):
            self.ok("theme:poste", {"status": "current", "distinct_from": "postes"})

    class TestsGarde(unittest.TestCase):
        def setUp(self):  # login Windows fixe : les tests ne dépendent pas du poste
            self.ancien_login = os.environ.get("USERNAME")
            os.environ["USERNAME"] = "jdupont"

        def tearDown(self):
            if self.ancien_login is None:
                os.environ.pop("USERNAME", None)
            else:
                os.environ["USERNAME"] = self.ancien_login

        def appel(self, outil, args):
            return garde({"tool_name": "mcp__plugin_aoi_cortexdb__" + outil, "tool_input": args}, conv, base="")

        def test_autre_outil_ignore(self):
            self.assertEqual(garde({"tool_name": "Read", "tool_input": {}}, conv, base=""), (False, ""))

        def test_knowledge_save_refuse(self):
            refus, msg = self.appel("knowledge_save", {"knowledge_id": "note-libre", "content": "x"})
            self.assertTrue(refus)
            self.assertIn("status", msg)

        def test_memory_save_refuse(self):
            self.assertTrue(self.appel("memory_save", {"memory_id": "pref-x", "content": "x", "metadata": {"status": "current"}})[0])

        META = {"nature": "reference", "theme": "outils-ia", "status": "current", "produit_par": "claude-code"}

        def test_ingest_ok(self):
            self.assertFalse(self.appel("ingest_document", {"document_id": "reference:outils-ia:x", "content": "x",
                                                            "author": "jdupont", "metadata": self.META})[0])

        def test_auteur_absent_refuse(self):
            refus, msg = self.appel("knowledge_save", {"knowledge_id": "reference:outils-ia:x", "content": "x", "metadata": self.META})
            self.assertTrue(refus)
            self.assertIn("author", msg)

        def test_auteur_agent_refuse(self):
            self.assertTrue(self.appel("knowledge_save", {"knowledge_id": "reference:outils-ia:x", "content": "x",
                                                          "author": "Claude Code, session c8eb", "metadata": self.META})[0])

        def test_produit_par_absent_refuse(self):
            meta = dict(self.META)
            del meta["produit_par"]
            refus, msg = self.appel("knowledge_save", {"knowledge_id": "reference:outils-ia:x", "content": "x", "author": "jdupont", "metadata": meta})
            self.assertTrue(refus)
            self.assertIn("produit_par", msg)

        def test_produit_par_inconnu_refuse(self):
            self.assertTrue(self.appel("knowledge_save", {"knowledge_id": "reference:outils-ia:x", "content": "x", "author": "jdupont",
                                                          "metadata": dict(self.META, produit_par="gpt")})[0])

        def test_memoire_user_id(self):
            args = {"memory_id": "reference:outils-ia:x", "content": "x", "metadata": self.META}
            self.assertTrue(self.appel("memory_save", args)[0])
            self.assertFalse(self.appel("memory_save", dict(args, user_id="jdupont"))[0])

        def test_update_produit_par(self):
            self.assertTrue(self.appel("knowledge_update", {"knowledge_id": "x", "metadata": dict(self.META, produit_par="")})[0])
            self.assertFalse(self.appel("knowledge_update", {"knowledge_id": "x", "metadata": self.META})[0])

        def test_update_sans_metadonnees_libre(self):
            self.assertFalse(self.appel("knowledge_update", {"knowledge_id": "ancien", "content": "x"})[0])

        def test_update_metadonnees_controlees(self):
            self.assertTrue(self.appel("knowledge_update", {"knowledge_id": "ancien", "metadata": {"nature": "x"}})[0])

        def test_convention_illisible_refuse(self):
            with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False, encoding="utf-8") as f:
                f.write("convention:\n  natures:\n    - Mauvais Nom\n")
            try:
                with self.assertRaises(ValueError):
                    lire_convention(f.name)
            finally:
                os.unlink(f.name)

    class TestsAnalyse(unittest.TestCase):
        def test_rapports_hors_plugin(self):
            ancien = os.environ.pop("MEMO_RAPPORTS", None)
            try:
                d = dossier_rapports()
                if not os.path.isdir(os.path.join(RACINE, ".git")):
                    self.assertFalse(os.path.abspath(d).lower().startswith(RACINE.lower()))
                os.environ["MEMO_RAPPORTS"] = "C:\\x"
                self.assertEqual(dossier_rapports(), "C:\\x")
            finally:
                os.environ.pop("MEMO_RAPPORTS", None)
                if ancien is not None:
                    os.environ["MEMO_RAPPORTS"] = ancien

        def lancer_garde(self, octets):
            r = subprocess.run([sys.executable, os.path.abspath(__file__), "garde"], input=octets, capture_output=True, timeout=30)
            return r.returncode, r.stdout.decode("utf-8")

        def test_garde_bom_lu(self):
            appel = json.dumps({"tool_name": "mcp__plugin_aoi_cortexdb__memory_save",
                                "tool_input": {"memory_id": "note-libre", "content": "x"}}).encode("utf-8")
            code, sortie = self.lancer_garde(b"\xef\xbb\xbf" + appel)
            self.assertEqual(code, 0)
            self.assertIn('"deny"', sortie)

        def test_garde_illisible_cortexdb_refuse(self):
            code, sortie = self.lancer_garde(b'{"tool_name": "mcp__plugin_aoi_cortexdb__memory_save", tronque')
            self.assertIn('"deny"', sortie)

        def test_garde_illisible_autre_passe(self):
            code, sortie = self.lancer_garde(b"pas du json")
            self.assertEqual((code, sortie.strip()), (0, ""))

        def lancer(self, *args, env=None):
            e = dict(os.environ)
            e.update(env or {})
            r = subprocess.run([sys.executable, os.path.abspath(__file__)] + list(args), capture_output=True, timeout=60, env=e)
            return r.returncode, r.stdout.decode("utf-8", "replace")

        def test_aide_sans_effet(self):
            d = tempfile.mkdtemp(prefix="memo-essai-")
            try:
                for cmd in ("analyser", "migrer", "lire", "verifier"):
                    code, sortie = self.lancer(cmd, "--help", env={"MEMO_RAPPORTS": d})
                    self.assertEqual(code, 0, cmd)
                    self.assertIn("Sous-commandes", sortie)
                self.assertEqual(os.listdir(d), [])  # aucun rapport créé
            finally:
                shutil.rmtree(d)

        def test_base_absente_refusee(self):
            d = tempfile.mkdtemp(prefix="memo-essai-")
            try:
                code, sortie = self.lancer("analyser", os.path.join(d, "absente.db"), env={"MEMO_RAPPORTS": d})
                self.assertEqual(code, 1)
                self.assertIn("base absente", sortie)
                self.assertEqual(os.listdir(d), [])
            finally:
                shutil.rmtree(d)

        def test_avertissement_base_hors_racine(self):
            ancien = os.environ.pop("CORTEXDB_PATH", None)
            try:
                self.assertEqual(avertissement_base(BASE_DEFAUT), "")
                os.environ["CORTEXDB_PATH"] = "C:\\essai\\cortexdb.db"
                a = avertissement_base("C:\\essai\\cortexdb.db")
                self.assertIn("ATTENTION", a)
                self.assertIn("CORTEXDB_PATH", a)
                self.assertIn(BASE_DEFAUT, a)
            finally:
                os.environ.pop("CORTEXDB_PATH", None)
                if ancien is not None:
                    os.environ["CORTEXDB_PATH"] = ancien

        def test_cortexdb_path_par_defaut(self):
            ancien = os.environ.get("CORTEXDB_PATH")
            try:
                os.environ["CORTEXDB_PATH"] = "C:\\essai\\cortexdb.db"
                self.assertEqual(base_par_defaut(), "C:\\essai\\cortexdb.db")
                del os.environ["CORTEXDB_PATH"]
                self.assertEqual(base_par_defaut(), BASE_DEFAUT)
            finally:
                if ancien is not None:
                    os.environ["CORTEXDB_PATH"] = ancien

        def memoire(self, d, nom="pref-unites.md", type_="feedback", corps="Les cotes sont en mm."):
            dossier = os.path.join(d, ".claude", "projects", "C--projet", "memory")
            os.makedirs(dossier, exist_ok=True)
            chemin = os.path.join(dossier, nom)
            with open(chemin, "w", encoding="utf-8") as f:
                f.write("---\nname: unites-des-cotes\ndescription: Unités des cotes\nmetadata:\n  type: %s\n---\n\n%s\n"
                        % (type_, corps))
            return chemin

        def test_miroir_memoire_claude(self):
            d = tempfile.mkdtemp(prefix="memo-essai-")
            ancien = os.environ.get("USERNAME")
            os.environ["USERNAME"] = "jdupont"
            try:
                chemin = self.memoire(d)
                r = miroir({"tool_name": "Write", "tool_input": {"file_path": chemin}}, base="")
                texte = r["hookSpecificOutput"]["additionalContext"]
                self.assertEqual(r["hookSpecificOutput"]["hookEventName"], "PostToolUse")
                for attendu in ("memory_save", "preference:<theme>:unites-des-cotes", "jdupont", "produit_par",
                                "claude-code", chemin, "Les cotes sont en mm."):
                    self.assertIn(attendu, texte)
            finally:
                if ancien is None:
                    os.environ.pop("USERNAME", None)
                else:
                    os.environ["USERNAME"] = ancien
                shutil.rmtree(d)

        def test_miroir_types(self):
            d = tempfile.mkdtemp(prefix="memo-essai-")
            try:
                ref = miroir({"tool_name": "Edit", "tool_input": {"file_path": self.memoire(d, "r.md", "reference")}}, base="")
                self.assertIn("reference:<theme>:", ref["hookSpecificOutput"]["additionalContext"])
                proj = miroir({"tool_name": "Write", "tool_input": {"file_path": self.memoire(d, "p.md", "project")}}, base="")
                self.assertIn("decision, fait ou etat", proj["hookSpecificOutput"]["additionalContext"])
            finally:
                shutil.rmtree(d)

        def test_miroir_ignore_hors_memoire_et_index(self):
            d = tempfile.mkdtemp(prefix="memo-essai-")
            try:
                chemin = self.memoire(d)
                index = os.path.join(os.path.dirname(chemin), "MEMORY.md")
                with open(index, "w", encoding="utf-8") as f:
                    f.write("- [x](pref-unites.md)\n")
                autre = os.path.join(d, "notes.md")
                with open(autre, "w", encoding="utf-8") as f:
                    f.write("x")
                self.assertIsNone(miroir({"tool_name": "Write", "tool_input": {"file_path": index}}, base=""))
                self.assertIsNone(miroir({"tool_name": "Write", "tool_input": {"file_path": autre}}, base=""))
                self.assertIsNone(miroir({"tool_name": "Read", "tool_input": {"file_path": chemin}}, base=""))
                self.assertIsNone(miroir({"tool_name": "Write", "tool_input": {"file_path": os.path.join(
                    os.path.dirname(chemin), "absent.md")}}, base=""))
            finally:
                shutil.rmtree(d)

        def test_miroir_reecrit_l_identifiant_existant(self):
            d = tempfile.mkdtemp(prefix="memo-essai-")
            try:
                chemin = self.memoire(d)
                base = os.path.join(d, "b.db")
                con = sqlite3.connect(base)
                con.executescript("create table documents(id text, metadata text, content text);"
                                  "create table messages(id text, role text, metadata text, content text);")
                con.execute("insert into messages values(?, 'memory', ?, 'x')",
                            ("preference:travail-assistant:unites-des-cotes", json.dumps({"source": chemin})))
                con.commit()
                con.close()
                r = miroir({"tool_name": "Edit", "tool_input": {"file_path": chemin}}, base=base)
                self.assertIn("preference:travail-assistant:unites-des-cotes", r["hookSpecificOutput"]["additionalContext"])
                self.assertIn("réécris", r["hookSpecificOutput"]["additionalContext"])
            finally:
                shutil.rmtree(d)

        def projets(self, d):
            """Deux projets dans un faux dossier .claude\\projects, avec leurs mémoires."""
            racine = os.path.join(d, ".claude", "projects")
            for nom, fichiers in (("C--IT-projet-a", {"a1.md": "fait a1", "a2.md": "fait a2"}),
                                  ("C--IT-projet-b", {"b1.md": "fait b1"})):
                m = os.path.join(racine, nom, "memory")
                os.makedirs(m)
                for f, corps in fichiers.items():
                    with open(os.path.join(m, f), "w", encoding="utf-8") as h:
                        h.write("---\nname: %s\ndescription: x\nmetadata:\n  type: reference\n---\n\n%s\n"
                                % (f[:-3], corps))
                with open(os.path.join(m, "MEMORY.md"), "w", encoding="utf-8") as h:
                    h.write("- index\n")
            return racine

        def test_encoder_projet(self):
            self.assertEqual(encoder_projet("C:\\IT\\projet-a"), "C--IT-projet-a")
            self.assertEqual(encoder_projet("C:\\Users\\x\\Dossier partagé - é\\p"), "C--Users-x-Dossier-partag------p")

        def test_memoires_tout_et_par_projet(self):
            d = tempfile.mkdtemp(prefix="memo-essai-")
            try:
                racine = self.projets(d)
                tout = lister_memoires("tout", racine, base="")
                self.assertEqual(sorted(os.path.basename(m["fichier"]) for m in tout), ["a1.md", "a2.md", "b1.md"])
                a = lister_memoires("C:\\IT\\projet-a", racine, base="")
                self.assertEqual(sorted(os.path.basename(m["fichier"]) for m in a), ["a1.md", "a2.md"])
                m = lister_memoires(os.path.join(racine, "C--IT-projet-b", "memory"), racine, base="")
                self.assertEqual([x["identifiant"] for x in m], ["reference:<theme>:b1"])
                self.assertEqual(m[0]["etat"], "nouveau")
                self.assertEqual(m[0]["corps"], "fait b1")
            finally:
                shutil.rmtree(d)

        def test_memoires_projet_inconnu(self):
            d = tempfile.mkdtemp(prefix="memo-essai-")
            try:
                with self.assertRaises(ValueError):
                    lister_memoires("C:\\IT\\absent", self.projets(d), base="")
            finally:
                shutil.rmtree(d)

        def test_memoires_etat_dans_le_cerveau(self):
            d = tempfile.mkdtemp(prefix="memo-essai-")
            try:
                racine = self.projets(d)
                m = os.path.join(racine, "C--IT-projet-a", "memory")
                base = os.path.join(d, "b.db")
                con = sqlite3.connect(base)
                con.executescript("create table documents(id text, metadata text, content text);"
                                  "create table messages(id text, role text, metadata text, content text);")
                con.execute("insert into messages values('reference:outils-ia:a1', 'memory', ?, 'fait a1')",
                            (json.dumps({"source": os.path.join(m, "a1.md")}),))
                con.execute("insert into messages values('reference:outils-ia:a2', 'memory', ?, 'ancien texte')",
                            (json.dumps({"source": os.path.join(m, "a2.md")}),))
                con.commit()
                con.close()
                etats = {os.path.basename(x["fichier"]): (x["etat"], x["identifiant"])
                         for x in lister_memoires("C:\\IT\\projet-a", racine, base=base)}
                self.assertEqual(etats["a1.md"], ("deja-importe", "reference:outils-ia:a1"))
                self.assertEqual(etats["a2.md"], ("a-mettre-a-jour", "reference:outils-ia:a2"))
            finally:
                shutil.rmtree(d)

        def test_memoires_doublon_probable(self):
            d = tempfile.mkdtemp(prefix="memo-essai-")
            try:
                racine = self.projets(d)
                m = os.path.join(racine, "C--IT-projet-b", "memory", "b1.md")
                with open(m, "w", encoding="utf-8") as h:
                    h.write("---\nname: b1\ntype: reference\n---\n\nLe serveur MCP AutoCAD écoute sur le port 1997 en local.\n")
                base = os.path.join(d, "b.db")
                con = sqlite3.connect(base)
                con.executescript("create table documents(id text, metadata text, content text);"
                                  "create table messages(id text, role text, metadata text, content text);")
                con.execute("insert into documents values('reference:outils-cao:port-autocad', '{}', "
                            "'Le serveur MCP AutoCAD écoute sur le port 1997 en local.')")
                con.commit()
                con.close()
                x = lister_memoires("C:\\IT\\projet-b", racine, base=base)[0]
                self.assertEqual((x["etat"], x["identifiant"]), ("doublon-probable", "reference:outils-cao:port-autocad"))
            finally:
                shutil.rmtree(d)

        def test_memoires_doublon_contenu_dans_un_document(self):
            d = tempfile.mkdtemp(prefix="memo-essai-")
            try:
                racine = self.projets(d)
                m = os.path.join(racine, "C--IT-projet-b", "memory", "b1.md")
                fait = "Le dossier du profil ne doit pas exister sinon le logiciel ne démarre plus du tout."
                with open(m, "w", encoding="utf-8") as h:
                    h.write("---\nname: b1\ntype: project\n---\n\n%s\n" % fait)
                base = os.path.join(d, "b.db")
                con = sqlite3.connect(base)
                con.executescript("create table documents(id text, metadata text, content text);"
                                  "create table messages(id text, role text, metadata text, content text);")
                con.execute("insert into documents values('piege:postes:profil', '{}', ?)",
                            ("---\nname: piege-profil\ndescription: long en-tete avec beaucoup de mots differents\n"
                             "metadata:\n  type: project\n---\n\n" + fait,))
                con.commit()
                con.close()
                x = lister_memoires("C:\\IT\\projet-b", racine, base=base)[0]
                self.assertEqual((x["etat"], x["identifiant"]), ("doublon-probable", "piege:postes:profil"))
            finally:
                shutil.rmtree(d)

        def test_miroir_desactive(self):
            d = tempfile.mkdtemp(prefix="memo-essai-")
            ancien = os.environ.get("MEMO_MIROIR")
            try:
                os.environ["MEMO_MIROIR"] = "0"
                self.assertIsNone(miroir({"tool_name": "Write", "tool_input": {"file_path": self.memoire(d)}}, base=""))
            finally:
                os.environ.pop("MEMO_MIROIR", None)
                if ancien is not None:
                    os.environ["MEMO_MIROIR"] = ancien
                shutil.rmtree(d)

        def avec_login(self, valeur):
            ancien = os.environ.get("USERNAME")
            os.environ["USERNAME"] = valeur
            return ancien

        def remettre_login(self, ancien):
            if ancien is None:
                os.environ.pop("USERNAME", None)
            else:
                os.environ["USERNAME"] = ancien

        def test_login_windows_normalise(self):
            ancien = self.avec_login("Jean.Dupont")
            try:
                self.assertEqual(login_windows(), "jean-dupont")
                os.environ["USERNAME"] = "Hélène_Müller"
                self.assertEqual(login_windows(), "helene-muller")
            finally:
                self.remettre_login(ancien)

        def test_auteur_autre_que_le_login_refuse(self):
            ancien = self.avec_login("jdupont")
            try:
                meta = {"nature": "reference", "theme": "outils-ia", "status": "current", "produit_par": "claude-code"}
                refus, msg = garde({"tool_name": "knowledge_save", "tool_input": {
                    "knowledge_id": "reference:outils-ia:x", "content": "x", "author": "autre", "metadata": meta}}, conv, base="")
                self.assertTrue(refus)
                self.assertIn("jdupont", msg)
                refus, _ = garde({"tool_name": "knowledge_save", "tool_input": {
                    "knowledge_id": "reference:outils-ia:x", "content": "x", "author": "jdupont", "metadata": meta}}, conv, base="")
                self.assertFalse(refus)
            finally:
                self.remettre_login(ancien)

        def test_auteur_defaut_analyse_est_le_login(self):
            ancien = self.avec_login("Jean.Dupont")
            try:
                self.assertEqual(auteur_par_defaut(""), "jean-dupont")
                self.assertEqual(auteur_par_defaut("autre"), "autre")
            finally:
                self.remettre_login(ancien)

        def test_toutes_les_erreurs_ensemble(self):
            refus, msg = garde({"tool_name": "memory_save", "tool_input": {"memory_id": "note-libre", "content": "x"}}, conv, base="")
            self.assertTrue(refus)
            for attendu in ("status", "nature", "theme", "identifiant", "user_id", "produit_par"):
                self.assertIn(attendu, msg)
            self.assertIn("6 erreur(s)", msg)

        def test_lire(self):
            d = tempfile.mkdtemp(prefix="memo-essai-")
            chemin = os.path.join(d, "b.db")
            con = sqlite3.connect(chemin)
            con.executescript("create table documents(id text, title text, author text, metadata text, content text);"
                              "create table messages(id text, session_id text, role text, metadata text, content text);"
                              "create table sessions(id text, user_id text);"
                              "insert into documents values('d1', 'Titre', 'jdupont', '{}', 'corps du document');"
                              "insert into sessions values('s', 'jdupont');"
                              "insert into messages values('m1', 's', 'memory', '{}', 'texte de la mémoire');")
            con.commit()
            con.close()
            try:
                self.assertEqual(lire(chemin, "d1")["texte"], "corps du document")
                self.assertEqual(lire(chemin, "m1")["auteur"], "jdupont")
                self.assertIsNone(lire(chemin, "absent"))
            finally:
                shutil.rmtree(d)

        def test_message_sans_chemin_personnel(self):
            refus, msg = garde({"tool_name": "knowledge_save", "tool_input": {"knowledge_id": "x", "content": "x"}}, conv, base="")
            self.assertTrue(refus)
            self.assertIn(CONVENTION, msg)

        def test_base_hors_c_refusee(self):
            with self.assertRaises(ValueError):
                ouvrir_lecture("P:\\x\\cortexdb.db")

        def test_proposition(self):
            ind = lire_indices()
            n, t, s, c, _ = proposer(conv, ind, "decision-projet-a-xrefs-lot", "", "autocad", {})
            self.assertEqual((n, t, s, c), ("decision", "outils-cao", "projet-a-xrefs-lot", "haute"))
            n, t, s, c, _ = proposer(conv, ind, "projet-a/revues/phase1-2026-10-27.md", "Relecture adverse", "autocad", {})
            self.assertEqual((n, s), ("relecture", "projet-a-phase1"))

        def test_chemin_garde_le_projet(self):
            ind = lire_indices()
            s1 = proposer(conv, ind, "projet-a/docs/LISEZMOI.md", "Index", "", {})[2]
            s2 = proposer(conv, ind, "projet-a/spike/LISEZMOI.md", "Mode opératoire", "", {})[2]
            self.assertNotEqual(s1, s2)
            self.assertEqual(proposer(conv, ind, "projet-a/PLAN.md", "Plan : serveur MCP autocad", "", {})[2], "projet-a")

        def test_theme_par_le_titre(self):
            ind = lire_indices()
            t = proposer(conv, ind, "projet-a/tests/integration/RESULTATS-PHASE1.md", "Résultats des essais Rhino de la phase 1",
                         "tests tests tests commit", {})[1]
            self.assertEqual(t, "outils-cao")

        def test_serie_regroupee(self):
            l = [{"ancien_id": "x-etat-%d" % i, "nouvel_id": "etat:outils-cao:x-etat", "action": "renommer", "nature": "etat",
                  "theme": "outils-cao" if i else "outils-ia", "status": "current", "date": "2026-10-%02d" % (20 + i), "remarque": ""}
                 for i in range(3)]
            regrouper_series(l)
            self.assertEqual([m["action"] for m in l], ["fusionner", "fusionner", "renommer"])
            self.assertEqual({m["nouvel_id"] for m in l}, {"etat:outils-cao:x-etat"})

        def test_collision_signalee(self):
            l = [{"ancien_id": "a", "nouvel_id": "reference:outils-cao:x", "action": "conforme", "nature": "reference",
                  "theme": "outils-cao", "status": "current", "date": "", "remarque": ""},
                 {"ancien_id": "b", "nouvel_id": "reference:outils-cao:x", "action": "renommer", "nature": "reference",
                  "theme": "outils-cao", "status": "current", "date": "", "remarque": ""}]
            regrouper_series(l)
            self.assertEqual(l[1]["action"], "a-classer")

        def test_base_temporaire(self):
            d = tempfile.mkdtemp(prefix="memo-essai-")
            chemin = os.path.join(d, "b.db")
            con = sqlite3.connect(chemin)
            con.executescript("create table documents(id text, title text, content text, metadata text, created_at text, author text);"
                              "create table messages(id text, session_id text, role text, content text, metadata text, created_at text);"
                              "create table sessions(id text, user_id text);"
                              "insert into sessions values('s1', 'ancien-compte');")
            con.execute("insert into documents values('methode:outils-cao:a','t','c','{\"nature\":\"methode\",\"theme\":\"outils-cao\",\"status\":\"current\"}','2026-11-24','Agent de relecture tiers, session 1')")
            con.execute("insert into documents values('plan-b','t','c','{}','2026-11-24','')")
            con.execute("insert into documents values('p/revues/phase1.md','t','c','{}','2026-11-24','')")
            for i in range(5):
                con.execute("insert into messages values(?, 's1', 'memory', 'texte', '{}', '2026-11-24')", ("zorglub-%d" % i,))
            con.execute("insert into messages values('pref-y', 's1', 'memory', 'texte', '{\"superseded_by\":\"pref-z\"}', '2026-11-24')")
            con.commit()
            con.close()
            try:
                sortie, lignes, inconnus = analyser(chemin, "essai", conv, sortie=os.path.join(d, "r"),
                                                    alias={"ancien-compte": "jdupont"}, auteur_defaut="jdupont")
                par_id = {l["ancien_id"]: l for l in lignes}
                actions = {k: l["action"] for k, l in par_id.items()}
                self.assertEqual(actions["methode:outils-cao:a"], "conforme")
                self.assertEqual(actions["pref-y"], "fusionner")
                self.assertEqual(par_id["methode:outils-cao:a"]["produit_par"], "agent-relecture")
                self.assertEqual(par_id["methode:outils-cao:a"]["author"], "jdupont")
                self.assertEqual(par_id["pref-y"]["author"], "jdupont")
                self.assertIn("supposé", par_id["plan-b"]["remarque"])
                self.assertEqual(par_id["p/revues/phase1.md"]["produit_par"], "agent-relecture")
                self.assertEqual(len(inconnus["zorglub"]), 5)
                synthese = open(os.path.join(sortie, "synthese.md"), encoding="utf-8").read()
                self.assertIn("`zorglub` (5 éléments)", synthese)
            finally:
                import shutil
                shutil.rmtree(d)

    class TestsMigration(unittest.TestCase):
        def setUp(self):
            self.d = tempfile.mkdtemp(prefix="memo-essai-")
            self.base = os.path.join(self.d, "b.db")
            con = sqlite3.connect(self.base)
            con.executescript(
                "create table documents(id text, metadata text);"
                "create table messages(id text, role text, metadata text);"
                "create table graph_nodes(id text, content text, node_type text);"
                "create table graph_edges(from_node_id text, to_node_id text, edge_type text);"
                "insert into documents values('projet-a/PLAN.md', '{\"_chunk_size\":\"120\",\"commit\":\"abc\"}');"
                "insert into documents values('methode:outils-cao:x', '{\"nature\":\"methode\",\"theme\":\"outils-cao\",\"status\":\"current\"}');"
                "insert into messages values('etat-1', 'memory', '{\"superseded_by\":\"etat-2\"}');"
                "insert into messages values('etat-2', 'memory', '{\"importance\":0.9,\"kind\":\"memory\"}');"
                "insert into messages values('renvoi', 'memory', '{}');"
                "insert into graph_nodes values('entity:gh', 'gh', 'logiciel');"
                "insert into graph_edges values('memory:etat-2', 'entity:gh', 'mentions');")
            con.commit()
            con.close()
            os.makedirs(os.path.join(self.d, "contenus"))
            with open(os.path.join(self.d, "contenus", "x.md"), "w", encoding="utf-8") as f:
                f.write("texte")

        def tearDown(self):
            shutil.rmtree(self.d)

        def ligne(self, **k):
            base = {"type": "memoire", "ancien_id": "", "action": "renommer", "nouvel_id": "", "nature": "etat",
                    "theme": "outils-cao", "status": "current", "date": "2026-10-28", "projet": "projet-a",
                    "author": "jdupont", "produit_par": "claude-code", "ancien_author": "", "contenu": ""}
            base.update(k)
            return base

        def plan(self, lignes):
            return planifier(conv, lignes, self.base, self.d)

        def table_ok(self):
            return [
                self.ligne(ancien_id="etat-2", nouvel_id="etat:outils-cao:projet-a"),
                self.ligne(ancien_id="etat-1", action="fusionner", status="replaced", nouvel_id="etat:outils-cao:projet-a"),
                self.ligne(type="document", ancien_id="projet-a/PLAN.md", nouvel_id="plan:outils-cao:projet-a",
                           nature="plan", date="", contenu="contenus/x.md"),
                self.ligne(ancien_id="renvoi", action="supprimer", nouvel_id="", nature="reference"),
                self.ligne(type="document", ancien_id="methode:outils-cao:x", action="conforme", nouvel_id="methode:outils-cao:x",
                           nature="methode", date="")]

        def test_plan_correct(self):
            ecr, sup, deja, pb = self.plan(self.table_ok())
            self.assertEqual(pb, [])
            self.assertEqual([e["ligne"]["nouvel_id"] for e in ecr],
                             ["etat:outils-cao:projet-a", "plan:outils-cao:projet-a", "methode:outils-cao:x"])
            self.assertEqual(sorted(s["ancien_id"] for s in sup), ["etat-1", "etat-2", "projet-a/PLAN.md", "renvoi"])
            self.assertEqual(ecr[0]["entites"], [{"name": "gh", "type": "logiciel"}])
            self.assertEqual(ecr[0]["meta"]["fusionne"], "etat-1")
            self.assertEqual(ecr[0]["meta"]["replaces"], "etat-2")
            self.assertNotIn("kind", ecr[0]["meta"])
            self.assertEqual(ecr[1]["meta"]["commit"], "abc")
            self.assertNotIn("_chunk_size", ecr[1]["meta"])

        def test_fusion_sans_cible(self):
            t = self.table_ok()
            t[1]["nouvel_id"] = "etat:outils-cao:autre"
            self.assertTrue(any("qu'aucune ligne" in p for p in self.plan(t)[3]))

        def test_contenu_absent(self):
            t = self.table_ok()
            t[2]["contenu"] = "contenus/absent.md"
            self.assertTrue(any("contenu absent" in p for p in self.plan(t)[3]))

        def test_auteur_refuse(self):
            t = self.table_ok()
            t[0]["author"] = "Claude Code, session 1"
            self.assertTrue(any("user_id" in p for p in self.plan(t)[3]))

        def test_date_obligatoire(self):
            t = self.table_ok()
            t[0]["date"] = ""
            self.assertTrue(any("date" in p for p in self.plan(t)[3]))

        def test_doublon_de_cible(self):
            t = self.table_ok()
            t[2]["nouvel_id"] = "etat:outils-cao:projet-a"
            t[2]["nature"] = "etat"
            self.assertTrue(any("déjà écrit" in p for p in self.plan(t)[3]))

        def test_action_inconnue(self):
            t = self.table_ok()
            t[3]["action"] = "effacer"
            self.assertTrue(any("inconnue" in p for p in self.plan(t)[3]))

        def test_absent_de_la_base(self):
            t = self.table_ok() + [self.ligne(ancien_id="fantome", nouvel_id="etat:outils-cao:fantome")]
            self.assertTrue(any("absent de la base" in p for p in self.plan(t)[3]))

        def test_reprise_deja_fait(self):
            con = sqlite3.connect(self.base)
            con.execute("delete from messages where id = 'etat-2'")
            con.execute("insert into messages values('etat:outils-cao:projet-a', 'memory', '{}')")
            con.commit()
            con.close()
            ecr, sup, deja, pb = self.plan(self.table_ok())
            self.assertEqual(pb, [])
            self.assertIn("etat-2", deja)
            self.assertNotIn("etat:outils-cao:projet-a", [e["ligne"]["nouvel_id"] for e in ecr])

        def base_a_jour(self, meta_doc, auteur="jdupont", texte="texte"):
            """Base où un élément porte déjà son identifiant final, avec texte et auteur."""
            con = sqlite3.connect(self.base)
            con.executescript("drop table documents; create table documents(id text, metadata text, content text, author text);"
                              "drop table messages; create table messages(id text, role text, metadata text, content text);")
            con.execute("insert into documents values('plan:outils-cao:projet-a', ?, ?, ?)", (json.dumps(meta_doc), texte, auteur))
            con.execute("insert into messages values('etat:outils-cao:projet-a', 'memory', ?, 'm')", (json.dumps(
                {"nature": "etat", "theme": "outils-cao", "status": "current", "produit_par": "claude-code",
                 "date": "2026-10-28", "projet": "projet-a", "importance": "0.9"}),))
            con.commit()
            con.close()

        META_PLAN = {"nature": "plan", "theme": "outils-cao", "status": "current", "produit_par": "claude-code",
                     "projet": "projet-a", "commit": "abc"}

        def table_meme_id(self):
            return [self.ligne(ancien_id="etat:outils-cao:projet-a", nouvel_id="etat:outils-cao:projet-a"),
                    self.ligne(type="document", ancien_id="plan:outils-cao:projet-a", nouvel_id="plan:outils-cao:projet-a",
                               nature="plan", date="", contenu="contenus/x.md")]

        def test_seconde_passe_a_zero(self):
            self.base_a_jour(self.META_PLAN)
            ecr, sup, deja, pb = self.plan(self.table_meme_id())
            self.assertEqual((pb, ecr, sup), ([], [], []))
            self.assertEqual(sorted(deja), ["etat:outils-cao:projet-a", "plan:outils-cao:projet-a"])

        def test_meme_id_reecrit_si_different(self):
            cas = [dict(self.META_PLAN, projet="projet-b"),          # métadonnée différente
                   {k: v for k, v in self.META_PLAN.items() if k != "projet"},   # métadonnée absente
                   dict(self.META_PLAN, kind="memory")]               # clé retirée encore présente
            for meta in cas:
                self.base_a_jour(meta)
                self.assertEqual([e["ligne"]["nouvel_id"] for e in self.plan(self.table_meme_id())[0]],
                                 ["plan:outils-cao:projet-a"], meta)
            self.base_a_jour(self.META_PLAN, auteur="autre")
            self.assertEqual(len(self.plan(self.table_meme_id())[0]), 1)
            self.base_a_jour(self.META_PLAN, texte="ancien texte")
            self.assertEqual(len(self.plan(self.table_meme_id())[0]), 1)

        def test_simuler_n_ecrit_rien(self):
            chemin = os.path.join(self.d, "renommage.csv")
            t = self.table_ok()
            with open(chemin, "w", encoding="utf-8-sig", newline="") as f:
                w = csv.DictWriter(f, fieldnames=list(t[0].keys()), delimiter=";")
                w.writeheader()
                w.writerows(t)
            avant = open(self.base, "rb").read()
            messages = []
            self.assertEqual(migrer(chemin, self.base, "", True, conv, sortie=messages.append), 0)
            self.assertEqual(open(self.base, "rb").read(), avant)
            self.assertTrue(any("rien n'est écrit" in m for m in messages))

        def test_reel_sans_serveur_refuse(self):
            chemin = os.path.join(self.d, "renommage.csv")
            t = self.table_ok()
            with open(chemin, "w", encoding="utf-8-sig", newline="") as f:
                w = csv.DictWriter(f, fieldnames=list(t[0].keys()), delimiter=";")
                w.writeheader()
                w.writerows(t)
            with self.assertRaises(ErreurMigration):
                migrer(chemin, self.base, os.path.join(self.d, "absent.exe"), False, conv, sortie=lambda m: None)

    suite = unittest.TestSuite()
    for cas in (TestsConvention, TestsGarde, TestsAnalyse, TestsMigration):
        suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(cas))
    r = unittest.TextTestRunner(verbosity=1).run(suite)
    return 0 if r.wasSuccessful() else 1


# ---------------------------------------------------------------- entrée

def base_par_defaut():
    """Même règle que le crochet : CORTEXDB_PATH s'il est défini, sinon la base de l'utilisateur."""
    return os.environ.get("CORTEXDB_PATH") or BASE_DEFAUT


def avertissement_base(base):
    """Phrase d'avertissement si la base lue n'est pas le cerveau racine de l'utilisateur, sinon chaîne vide."""
    if os.path.normcase(os.path.abspath(base)) == os.path.normcase(os.path.abspath(BASE_DEFAUT)):
        return ""
    origine = "CORTEXDB_PATH" if os.environ.get("CORTEXDB_PATH") else "chemin donné"
    return ("ATTENTION : la base lue n'est pas le cerveau racine %s (elle vient de %s). "
            "En usage normal, lancez Claude Code depuis un terminal sans CORTEXDB_PATH." % (BASE_DEFAUT, origine))


def base_existante(base):
    if not os.path.isfile(base):
        raise ValueError("base absente : %s (aucun rapport n'est écrit)" % base)
    return base


def main(argv):
    if not argv or argv[0] in ("-h", "--help", "aide"):
        print(__doc__)
        return 0 if argv else 2
    cmd, reste = argv[0], argv[1:]
    if "-h" in reste or "--help" in reste:
        print(__doc__)
        return 0
    if cmd == "garde":
        return commande_garde()
    if cmd == "miroir":
        return commande_miroir()
    if cmd == "memoires":
        cible = " ".join(a for a in reste if a != "--json").strip().strip('"') or "tout"
        try:
            liste = lister_memoires(cible)
        except (ValueError, OSError) as e:
            print("ARRÊT : %s" % e)
            return 1
        print("Login Windows (auteur) : %s" % (login_windows() or "(inconnu)"))
        if avertissement_base(base_par_defaut()):
            print(avertissement_base(base_par_defaut()))
        print("Base : %s" % base_par_defaut())
        compte = {}
        for m in liste:
            compte[m["etat"]] = compte.get(m["etat"], 0) + 1
        try:
            print("Fichiers : %d (%s)" % (len(liste), ", ".join("%s %d" % kv for kv in sorted(compte.items())) or "aucun"))
            for m in liste:
                print(json.dumps(m, ensure_ascii=False))
        except OSError:  # tube fermé par le lecteur (par exemple « head ») : rien à signaler
            pass
        return 0
    if cmd == "tests":
        return tests()
    if cmd == "verifier":
        ident = reste[0]
        meta = json.loads(reste[reste.index("--meta") + 1]) if "--meta" in reste else {}
        outil = reste[reste.index("--outil") + 1] if "--outil" in reste else "knowledge_save"
        auteur = reste[reste.index("--auteur") + 1] if "--auteur" in reste else ""
        champ = "user_id" if outil == "memory_save" else "author"
        refus, msg = garde({"tool_name": outil, "tool_input": {OUTILS[outil]: ident, "metadata": meta, champ: auteur}})
        print(msg if refus else "conforme")
        return 1 if refus else 0
    if cmd == "analyser":
        base = reste[0] if reste and not reste[0].startswith("--") else base_par_defaut()
        try:
            base_existante(base)
        except ValueError as e:
            print("ARRÊT : %s" % e)
            return 1
        if avertissement_base(base):
            print(avertissement_base(base))
        print("Base lue : %s" % base)
        nom = reste[reste.index("--nom") + 1] if "--nom" in reste else "local"
        defaut = reste[reste.index("--auteur-defaut") + 1] if "--auteur-defaut" in reste else ""
        alias = {}
        for i, a in enumerate(reste):
            if a == "--alias":
                ancien, _, nouveau = reste[i + 1].partition("=")
                alias[ancien] = nouveau
        defaut = auteur_par_defaut(defaut)
        print("Auteur par défaut : %s" % (defaut or "(inconnu : donner --auteur-defaut)"))
        sortie, lignes, _ = analyser(base, nom, alias=alias, auteur_defaut=defaut)
        print("%d éléments analysés ; rapport : %s" % (len(lignes), sortie))
        return 0
    if cmd == "lire":
        if len(reste) < 2:
            print("usage : lire BASE ID [ID ...]")
            return 2
        code = 0
        for ident in reste[1:]:
            e = lire(reste[0], ident)
            if e is None:
                print("=== %s : absent de la base" % ident)
                code = 1
                continue
            print("=== %s (%s)\ntitre : %s\nauteur : %s\nmétadonnées : %s\n---\n%s\n" % (
                e["id"], e["genre"], e["titre"], e["auteur"], e["metadata"], e["texte"]))
        return code
    if cmd == "migrer":
        if not reste or reste[0].startswith("--"):
            print("usage : migrer TABLE.csv [--base cortexdb.db] [--serveur cortexdb-mcp.exe] [--simuler]")
            return 2
        base = reste[reste.index("--base") + 1] if "--base" in reste else base_par_defaut()
        exe = reste[reste.index("--serveur") + 1] if "--serveur" in reste else serveur_defaut()
        try:
            base_existante(base)
            if avertissement_base(base):
                print(avertissement_base(base))
            print("Base lue : %s" % base)
            # Une session Claude Code ouverte sert la base par défaut (ou CORTEXDB_PATH) : contrôle du serveur actif.
            return migrer(reste[0], base, exe, "--simuler" in reste,
                          controle_processus=os.path.abspath(base).lower() in (
                              os.path.abspath(BASE_DEFAUT).lower(), os.path.abspath(base_par_defaut()).lower()))
        except (ErreurMigration, ValueError) as e:
            print("ARRÊT : %s" % e)
            return 1
        except Exception as e:  # erreur imprévue : un message lisible, jamais une trace seule
            print("ARRÊT : erreur imprévue (%s) : %s" % (type(e).__name__, e))
            return 1
    print(__doc__)
    return 2


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main(sys.argv[1:]))
