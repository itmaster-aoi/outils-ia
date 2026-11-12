"""Enveloppe de D5LiteWorkflowCli pour D5 Lite (Rhino).

Bibliotheque standard seulement. Le module enchaine : validation, plan,
controle du risque, execution avec un recu neuf, lecture du resultat.

Usage en ligne de commande :
    python d5lite.py etat
    python d5lite.py aide <mot>
    python d5lite.py operation <type>
    python d5lite.py lire <type> [--cible JSON] [--params JSON]
    python d5lite.py executer <workflow.json> [--risque-max safeWrite]
    python d5lite.py instantane [--lumieres GUID,GUID]
    python d5lite.py regler <type> --params JSON --lecture <type> --champ <chemin>

Le journal des ecritures va dans ./journal_d5lite (ou D5LITE_JOURNAL).
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import subprocess
import sys
from pathlib import Path

RISQUES = ["readOnly", "safeWrite", "confirmWrite"]
CLES_REGISTRE = ["literhino1", "Rhino"]
NOM_CLI = "D5LiteWorkflowCli.exe"
# Empreinte des contrats de la CLI testee le 12.11.2026 (D5 Lite pour Rhino 1.2.0.0017).
CONTRATS_TESTES = "sha256:f2cc11f00b949698d61661b9ea8cf95c33855c0b3583dc6b17136d3ea246d344"


class ErreurD5(Exception):
    """Erreur de localisation, de plan ou d'execution."""


def localiser_cli() -> Path:
    """Retourne le chemin de la CLI. Ordre : variable, registre, dossier par defaut."""
    candidats = []
    env = os.environ.get("D5_LITE_WORKFLOW_CLI")
    if env:
        candidats.append(Path(env))
    try:
        import winreg

        for cle in CLES_REGISTRE:
            try:
                with winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    rf"Software\Dimension5\Lite\{cle}\Install",
                ) as k:
                    racine = Path(winreg.QueryValueEx(k, "InstallLocation")[0])
                    candidats += [racine / NOM_CLI, racine / "engine" / NOM_CLI]
            except OSError:
                continue
    except ImportError:
        pass
    appdata = os.environ.get("APPDATA")
    if appdata:
        candidats.append(Path(appdata) / "D5 Lite for Rhino" / "engine" / NOM_CLI)
    for c in candidats:
        if c.is_file():
            return c
    raise ErreurD5(
        "D5LiteWorkflowCli.exe introuvable. Chemins testes : "
        + "; ".join(str(c) for c in candidats)
    )


def _valeur(segment: dict):
    """Extrait la valeur utile d'un segment de sortie."""
    sorties = segment.get("outputs") or {}
    relu = sorties.get("readBack")
    if isinstance(relu, dict):
        if isinstance(relu.get("value"), dict):
            return relu["value"]
        return relu
    return sorties


def _champ(valeur, chemin: str):
    for cle in chemin.split("."):
        if not isinstance(valeur, dict) or cle not in valeur:
            return None
        valeur = valeur[cle]
    return valeur


def _egal(a, b, tol: float = 1e-3) -> bool:
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b) <= tol * max(1.0, abs(b))
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(_egal(x, y, tol) for x, y in zip(a, b))
    return a == b


class D5Lite:
    def __init__(self, journal: Path | str | None = None, delai_ms: int = 30000):
        self.cli = localiser_cli()
        base = Path(journal or os.environ.get("D5LITE_JOURNAL") or Path.cwd() / "journal_d5lite")
        self.journal = base
        self.journal.mkdir(parents=True, exist_ok=True)
        self.delai_ms = delai_ms
        self._compteur = 0

    # -- appels bruts ---------------------------------------------------
    def _appel(self, *args: str, delai_s: float = 180) -> tuple[int, dict]:
        proc = subprocess.run(
            [str(self.cli), *args, "--json"],
            capture_output=True,
            timeout=delai_s,
        )
        texte = proc.stdout.decode("utf-8", errors="replace").strip()
        try:
            donnees = json.loads(texte) if texte else {}
        except json.JSONDecodeError:
            donnees = {"ok": False, "brut": texte[:2000]}
        return proc.returncode, donnees

    def etat(self, delai_ms: int = 20000) -> dict:
        """Controle de connexion en lecture seule."""
        code, d = self._appel("doctor", "--online", "--target", "lite", "--timeout-ms", str(delai_ms))
        controle = ((d.get("online") or {}).get("checks") or [{}])[0]
        return {
            "connecte": bool((d.get("online") or {}).get("ok")),
            "statut": controle.get("status"),
            "code": controle.get("code"),
            "contrats": (d.get("contractSet") or {}).get("digest"),
            # False : la CLI a change depuis la campagne de tests. Relancez tests/campagne.py.
            "contrats_testes": (d.get("contractSet") or {}).get("digest") == CONTRATS_TESTES,
            "cli": str(self.cli),
        }

    def aide_recherche(self, mot: str, limite: int = 30) -> list[dict]:
        _, d = self._appel("help", "search", mot, "--limit", str(limite))
        return d.get("results") or []

    def aide_operation(self, type_op: str) -> dict:
        code, d = self._appel("help", "operation", type_op)
        if code != 0 or "operation" not in d:
            raise ErreurD5(f"Operation inconnue : {type_op}")
        return d["operation"]

    # -- workflows ------------------------------------------------------
    def executer(
        self,
        operations: list[dict],
        nom: str = "wf",
        risque_max: str = "safeWrite",
        confirme: bool = False,
        enchainer: bool = True,
    ) -> dict:
        """Valide, planifie et execute une liste d'operations.

        risque_max : niveau le plus haut accepte. Le controle lit le plan.
        confirme   : ajoute la declaration userConfirmation. A utiliser
                     seulement apres l'accord reel de l'utilisateur.
        enchainer  : ajoute dependsOn pour garder l'ordre de la liste.
        """
        ops = []
        precedent = None
        for i, op in enumerate(operations):
            o = dict(op)
            o.setdefault("id", f"op{i}")
            o.setdefault("params", {})
            if enchainer and precedent and "dependsOn" not in o:
                o["dependsOn"] = [precedent]
            precedent = o["id"]
            ops.append(o)
        wf: dict = {"workflowVersion": "1.0", "operations": ops}
        if confirme:
            wf["requires"] = ["userConfirmation"]

        self._compteur += 1
        horodatage = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        racine = self.journal / f"{horodatage}-{self._compteur:03d}-{nom}"
        f_wf = racine.with_suffix(".workflow.json")
        f_recu = racine.with_suffix(".recu.json")
        f_wf.write_text(json.dumps(wf, indent=2), encoding="ascii")

        code, val = self._appel("workflow", "validate", "--file", str(f_wf))
        if not val.get("ok"):
            return {"ok": False, "etape": "validation", "diagnostics": val.get("diagnostics"), "fichier": str(f_wf)}
        code, plan = self._appel("workflow", "plan", "--file", str(f_wf))
        if not plan.get("ok") and confirme:
            # La CLI nomme les declarations d'accord qui manquent (ex. params.confirmed.apply).
            # L'outil les ajoute seulement quand l'appelant a deja declare l'accord de l'utilisateur.
            manquants = [t for d in plan.get("diagnostics") or [] if d.get("code") == "missing_requirement"
                         for t in d.get("suggestedRequires") or []]
            if manquants:
                wf["requires"] = sorted(set(wf["requires"]) | set(manquants))
                f_wf.write_text(json.dumps(wf, indent=2), encoding="ascii")
                code, plan = self._appel("workflow", "plan", "--file", str(f_wf))
        if not plan.get("ok"):
            return {"ok": False, "etape": "plan", "diagnostics": plan.get("diagnostics"), "fichier": str(f_wf)}
        risque = ((plan.get("plan") or {}).get("risk") or {}).get("overall", "confirmWrite")
        if RISQUES.index(risque) > RISQUES.index(risque_max):
            return {
                "ok": False,
                "etape": "risque",
                "risque": risque,
                "risque_max": risque_max,
                "empreinte": plan["plan"]["planDigest"],
                "fichier": str(f_wf),
            }
        empreinte = plan["plan"]["planDigest"]
        code, res = self._appel(
            "workflow", "execute", "--file", str(f_wf),
            "--approve-plan", empreinte, "--receipt", str(f_recu),
            "--timeout-ms", str(self.delai_ms),
            delai_s=max(180, self.delai_ms / 1000 * (len(ops) + 2)),
        )
        segments = {}
        for s in res.get("segments") or []:
            segments[s["id"]] = {
                "statut": s.get("status"),
                "valeur": _valeur(s),
                "erreur": (s.get("error") or {}).get("code"),
                "message": (s.get("error") or {}).get("message"),
                "etat_execution": s.get("executionState"),
            }
        reussi = bool(res.get("ok")) and code == 0
        if risque == "readOnly" and reussi:
            # Le journal garde les ecritures et les echecs. Une lecture reussie ne laisse pas de trace.
            for f in (f_wf, f_recu):
                try:
                    f.unlink()
                except OSError:
                    pass
        return {
            "ok": reussi,
            "etape": "execution",
            "code": code,
            "risque": risque,
            "empreinte": empreinte,
            "segments": segments,
            "diagnostics": res.get("diagnostics") or [],
            "fichier": str(f_wf),
            "recu": str(f_recu),
        }

    def lire(self, type_op: str, cible: dict | None = None, params: dict | None = None) -> dict:
        """Execute une seule operation de lecture. Refuse tout autre risque."""
        op = {"id": "lire", "type": type_op, "params": params or {}}
        if cible:
            op["target"] = cible
        r = self.executer([op], nom="lire", risque_max="readOnly")
        s = (r.get("segments") or {}).get("lire") or {}
        return {"ok": r["ok"] and s.get("statut") == "completed", "valeur": s.get("valeur"),
                "erreur": s.get("erreur") or r.get("etape"), "message": s.get("message"),
                "diagnostics": r.get("diagnostics")}

    def regler(self, ecriture: str, params: dict, lecture: str, champ: str,
               cible: dict | None = None, cible_lecture: dict | None = None,
               attendu=None, risque_max: str = "safeWrite", confirme: bool = False) -> dict:
        """Ecrit une valeur et la verifie par relecture.

        La reponse applied:true de Lite ne prouve pas l'effet. Le verdict vient
        de la relecture : OK, SANS EFFET (valeur inchangee) ou ECART.
        champ : chemin dans la valeur lue, par exemple "geoSunEleAzi.altitude".
        attendu : valeur attendue a la relecture. Par defaut, la valeur du seul parametre.
        """
        if attendu is None and len(params) == 1:
            attendu = next(iter(params.values()))
        cible_lecture = cible_lecture or cible
        op_l = {"id": "avant", "type": lecture}
        op_e = {"id": "ecrire", "type": ecriture, "params": params}
        if cible:
            op_e["target"] = cible
        if cible_lecture:
            op_l["target"] = cible_lecture
        r = self.executer([op_l, op_e, {**op_l, "id": "apres"}], nom=ecriture.replace(".", "_"),
                          risque_max=risque_max, confirme=confirme)
        if r["etape"] != "execution":
            return {"verdict": "REFUSE", **{k: r.get(k) for k in ("etape", "diagnostics", "risque", "empreinte")}}
        seg = r["segments"]
        avant = _champ((seg.get("avant") or {}).get("valeur"), champ)
        apres = _champ((seg.get("apres") or {}).get("valeur"), champ)
        ecr = seg.get("ecrire") or {}
        if ecr.get("statut") != "completed":
            verdict = "ECHEC"
        elif _egal(apres, attendu):
            verdict = "OK"
        elif _egal(apres, avant):
            verdict = "SANS EFFET"
        else:
            verdict = "ECART"
        return {"verdict": verdict, "avant": avant, "ecrit": params, "apres": apres,
                "erreur": ecr.get("erreur"), "message": ecr.get("message"), "recu": r.get("recu")}

    def instantane(self, lumieres: list[str] | None = None) -> dict:
        """Lit l'etat complet de la scene Lite. Lecture seule."""
        resultat: dict = {}
        blocs = {
            "scene": ("lite.scene.read", {"kind": "scene"}),
            "scenes": ("lite.scene.list", {"kind": "scene"}),
            "camera": ("lite.camera.read.state", {"kind": "camera"}),
            "post_traitement": ("lite.postprocess.read", {"kind": "postprocess"}),
            "rendu": ("lite.render.settings.read", {"kind": "renderJob"}),
            "ciel_mode": ("lite.sky.read.mode", {"kind": "sky"}),
            "ciel_intensite": ("lite.sky.read.intensity", {"kind": "sky"}),
            "ciel_rotation": ("lite.sky.read.skyRotation", {"kind": "sky"}),
            "ciel_soleil": ("lite.sky.read.sunEleAzi", {"kind": "sky"}),
            "ciel_soleil_hdri": ("lite.sky.read.hdriSunlightIntensity", {"kind": "sky"}),
            "ciel_direction_hdri": ("lite.sky.read.hdriSunDirectionMode", {"kind": "sky"}),
            "ciel_fichier": ("lite.sky.read.hdriFile", {"kind": "sky"}),
            "dcc": ("lite.dcc.read", {"kind": "dcc"}),
        }
        for nom, (t, cible) in blocs.items():
            r = self.lire(t, cible)
            resultat[nom] = r["valeur"] if r["ok"] else {"erreur": r["erreur"]}
        champs = ["light_type", "brightness", "color", "colorTemperature", "isTemperature",
                  "location", "rotation", "attenuationRadius", "reflectionVisibility"]
        resultat["lumieres"] = {}
        for guid in lumieres or []:
            gid = guid.strip().strip("{}").upper()
            cible = {"kind": "light", "light_id": gid}
            lum: dict = {}
            for c in champs:
                r = self.lire(f"lite.light.read.{c}", cible)
                if r["ok"]:
                    lum.update({k: v for k, v in r["valeur"].items() if k != "light_id"})
                else:
                    lum[c] = {"erreur": r["erreur"]}
            if lum.get("light_type") == "spot":
                r = self.lire("lite.light.read.coneAngle", cible)
                if r["ok"]:
                    lum["coneAngle"] = r["valeur"].get("coneAngle")
            if lum.get("light_type") in ("area", "strip", "disk", "belt", "line"):
                r = self.lire("lite.light.read.size", cible)
                if r["ok"]:
                    lum["size"] = r["valeur"].get("size")
            resultat["lumieres"][gid] = lum
        return resultat


# ====================================================== ambiances
CIEL, POST, RENDU, VUE = {"kind": "sky"}, {"kind": "postprocess"}, {"kind": "renderJob"}, {"kind": "viewport"}
CHAMPS_POST = ["autoExposure", "exposure", "contrast", "highlight", "shadow", "saturation", "temperature", "tint", "tonalContrast"]


def dossier_ambiances() -> Path:
    d = Path(os.environ.get("D5LITE_AMBIANCES") or Path.cwd() / "ambiances")
    d.mkdir(parents=True, exist_ok=True)
    return d


def lire_ambiance(d5: D5Lite) -> dict:
    """Lit le ciel, le post-traitement et les reglages de rendu. Lecture seule."""
    def v(t, cible):
        r = d5.lire(t, cible)
        return r["valeur"] if r["ok"] else {}
    soleil = v("lite.sky.read.sunEleAzi", CIEL)
    fichier = v("lite.sky.read.hdriFile", CIEL)
    return {
        "format": "d5lite-ambiance-1",
        "ciel": {
            "mode": v("lite.sky.read.mode", CIEL).get("mode"),
            "hdri_intensite": v("lite.sky.read.intensity", CIEL).get("intensity"),
            "hdri_rotation": v("lite.sky.read.skyRotation", CIEL).get("skyRotation"),
            "hdri_soleil_intensite": v("lite.sky.read.hdriSunlightIntensity", CIEL).get("hdriSunlightIntensity"),
            "hdri_soleil_mode": v("lite.sky.read.hdriSunDirectionMode", CIEL).get("mode"),
            "hdri_soleil": soleil.get("hdriSunEleAzi"),
            "geo_soleil": soleil.get("geoSunEleAzi"),
            "hdri_fichier": fichier.get("filePath"),
            "hdri_defaut": v("lite.sky.read.isDefaultHdri", CIEL).get("isDefaultHdri"),
        },
        "post": {k: val for k, val in v("lite.postprocess.read", POST).items() if k in CHAMPS_POST},
        "rendu": v("lite.render.settings.read", RENDU),
    }


def _ops_ambiance(a: dict, actuel: dict, parties: list[str]) -> list[dict]:
    ops: list[dict] = []

    def op(t, cible, params=None):
        ops.append({"id": "a%02d" % len(ops), "type": t, "target": cible, "params": params or {}})

    c = a.get("ciel") or {}
    if "ciel" in parties and c:
        fichier, courant = c.get("hdri_fichier"), (actuel.get("ciel") or {}).get("hdri_fichier")
        if c.get("hdri_defaut"):
            if not (actuel.get("ciel") or {}).get("hdri_defaut"):
                op("lite.sky.resetHdri", CIEL)
        elif fichier and fichier != courant and Path(fichier).is_file():
            op("lite.sky.patch.hdriFile", CIEL, {"filePath": fichier})
        g = c.get("geo_soleil") or {}
        if g:
            op("lite.sky.patch.mode", CIEL, {"mode": "GEO"})
            op("lite.sky.patch.geoAltitude", CIEL, {"altitude": g.get("altitude")})
            op("lite.sky.patch.geoAzimuth", CIEL, {"azimuth": g.get("azimuth")})
        op("lite.sky.patch.mode", CIEL, {"mode": "HDRI"})
        if c.get("hdri_rotation") is not None:
            op("lite.sky.patch.hdriRotation", CIEL, {"rotation": c["hdri_rotation"]})
        if c.get("hdri_intensite") is not None:
            op("lite.sky.patch.hdriIntensity", CIEL, {"intensity": c["hdri_intensite"]})
        if c.get("hdri_soleil_intensite") is not None:
            op("lite.sky.patch.hdriSunlightIntensity", CIEL, {"sunlightIntensity": c["hdri_soleil_intensite"]})
        if c.get("hdri_soleil_mode") == "custom" and c.get("hdri_soleil"):
            s = c["hdri_soleil"]
            op("lite.sky.patch.hdriSunDirection", CIEL, {"sunDirection": {
                "mode": "custom", "altitude": max(0.0, min(90.0, s.get("altitude", 45.0))), "azimuth": s.get("azimuth", 180.0)}})
        elif c.get("hdri_soleil_mode") == "followHdri":
            op("lite.sky.patch.hdriSunDirection", CIEL, {"sunDirection": {"mode": "followHdri"}})
        if c.get("mode") == "GEO":
            op("lite.sky.patch.mode", CIEL, {"mode": "GEO"})
    p = a.get("post") or {}
    if "post" in parties:
        for k in CHAMPS_POST:
            if k in p and p[k] is not None:
                op(f"lite.postprocess.patch.{k}", POST, {k: p[k]})
    r = a.get("rendu") or {}
    if "rendu" in parties:
        for champ, nom_op in (("outputType", "outputType"), ("quality", "quality"), ("format", "format"), ("aspectRatio", "aspect")):
            if r.get(champ):
                op(f"lite.render.settings.patch.{nom_op}", RENDU, {champ: r[champ]})
    return ops


def _ecarts(voulu: dict, relu: dict, parties: list[str]) -> list[dict]:
    ecarts = []
    for partie in parties:
        for k, v in (voulu.get(partie) or {}).items():
            if v is None or k in ("hdri_defaut",):
                continue
            w = (relu.get(partie) or {}).get(k)
            if isinstance(v, dict) and isinstance(w, dict):
                ok = all(_egal(v[x], w.get(x)) for x in v)
            elif isinstance(v, str) and isinstance(w, str):
                ok = v.lower() == w.lower()
            else:
                ok = _egal(v, w)
            if not ok:
                ecarts.append({"partie": partie, "champ": k, "voulu": v, "relu": w})
    return ecarts


def appliquer_ambiance(d5: D5Lite, a: dict, parties: list[str] | None = None) -> dict:
    """Applique une ambiance, puis la relit. Retourne les ecarts entre le voulu et le relu."""
    parties = parties or ["ciel", "post", "rendu"]
    actuel = lire_ambiance(d5)
    ops = _ops_ambiance(a, actuel, parties)
    if not ops:
        return {"ok": True, "operations": 0, "ecarts": []}
    r = d5.executer(ops, nom="ambiance")
    echecs = {k: (s["erreur"], s["message"]) for k, s in (r.get("segments") or {}).items() if s["statut"] != "completed"}
    relu = lire_ambiance(d5)
    # Les reglages d'un mode de ciel inactif ne se comparent pas.
    ignorer = set()
    if (a.get("ciel") or {}).get("mode") == "HDRI":
        ignorer.add("geo_soleil")
    ecarts = [e for e in _ecarts(a, relu, parties)
              if e["champ"] not in ignorer and not (e["champ"] == "hdri_soleil" and (a.get("ciel") or {}).get("hdri_soleil_mode") != "custom")]
    return {"ok": r["ok"] and not ecarts, "operations": len(ops), "echecs": echecs, "ecarts": ecarts,
            "diagnostics": r.get("diagnostics") if not r["ok"] else []}


def enregistrer_ambiance(d5: D5Lite, nom: str) -> dict:
    a = lire_ambiance(d5)
    a["nom"] = nom
    f = dossier_ambiances() / f"{nom}.json"
    f.write_text(json.dumps(a, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"fichier": str(f), "ambiance": a}


def charger_ambiance(nom_ou_fichier: str) -> dict:
    f = Path(nom_ou_fichier)
    if not f.is_file():
        f = dossier_ambiances() / f"{nom_ou_fichier}.json"
    if not f.is_file():
        dispo = sorted(p.stem for p in dossier_ambiances().glob("*.json"))
        raise ErreurD5(f"Ambiance introuvable : {nom_ou_fichier}. Disponibles : {', '.join(dispo) or 'aucune'}")
    return json.loads(f.read_text(encoding="utf-8"))


def _est_nuit(a: dict) -> bool:
    c = a.get("ciel") or {}
    if c.get("mode") == "GEO":
        return ((c.get("geo_soleil") or {}).get("altitude") or 0) < 0
    return (c.get("hdri_intensite") or 0) <= 0.001 and (c.get("hdri_soleil_intensite") or 0) <= 0.001


def nuit(d5: D5Lite) -> dict:
    """Passe le ciel en nuit. Garde l'ambiance de jour dans ambiances/_avant_nuit.json.

    Le ciel devient noir. La scene est alors eclairee par les lumieres de Rhino :
    lancez aussi d5lum.mode("nuit") dans Rhino.
    """
    a = lire_ambiance(d5)
    if _est_nuit(a):
        return {"ok": True, "deja_nuit": True}
    enregistrer_ambiance(d5, "_avant_nuit")
    if (a["ciel"].get("mode") == "GEO"):
        ops = [{"id": "n0", "type": "lite.sky.patch.geoAltitude", "target": CIEL, "params": {"altitude": -15}}]
    else:
        ops = [{"id": "n0", "type": "lite.sky.patch.hdriIntensity", "target": CIEL, "params": {"intensity": 0.0}},
               {"id": "n1", "type": "lite.sky.patch.hdriSunlightIntensity", "target": CIEL, "params": {"sunlightIntensity": 0.0}}]
    r = d5.executer(ops, nom="nuit")
    return {"ok": r["ok"] and _est_nuit(lire_ambiance(d5)), "ambiance_de_jour": str(dossier_ambiances() / "_avant_nuit.json"),
            "suite": "Dans Rhino : d5lum.mode('nuit')"}


def jour(d5: D5Lite, ambiance: str = "_avant_nuit") -> dict:
    """Remet le ciel de jour, d'apres l'ambiance gardee par nuit() ou une ambiance nommee."""
    r = appliquer_ambiance(d5, charger_ambiance(ambiance), ["ciel"])
    r["suite"] = "Dans Rhino : d5lum.mode('jour')"
    return r


# ================================================== ensoleillement
def position_soleil(latitude: float, longitude: float, instant_utc: _dt.datetime) -> tuple[float, float]:
    """Altitude et azimut du soleil en degres. Azimut : 0 = nord, 90 = est. Precision : 0,5 degre."""
    import math
    jour_julien = instant_utc.toordinal() + 1721424.5 + (instant_utc.hour + instant_utc.minute / 60 + instant_utc.second / 3600) / 24
    n = jour_julien - 2451545.0
    L = (280.460 + 0.9856474 * n) % 360
    g = math.radians((357.528 + 0.9856003 * n) % 360)
    lam = math.radians(L + 1.915 * math.sin(g) + 0.020 * math.sin(2 * g))
    eps = math.radians(23.439 - 0.0000004 * n)
    ad = math.atan2(math.cos(eps) * math.sin(lam), math.cos(lam))
    decl = math.asin(math.sin(eps) * math.sin(lam))
    tsmg = (18.697374558 + 24.06570982441908 * n) % 24
    angle_horaire = math.radians((tsmg * 15 + longitude) % 360) - ad
    lat = math.radians(latitude)
    altitude = math.asin(math.sin(lat) * math.sin(decl) + math.cos(lat) * math.cos(decl) * math.cos(angle_horaire))
    azimut = math.atan2(-math.sin(angle_horaire), math.tan(decl) * math.cos(lat) - math.sin(lat) * math.cos(angle_horaire))
    return math.degrees(altitude), math.degrees(azimut) % 360


def ensoleillement(d5: D5Lite, latitude: float, longitude: float, date: str, heures: list[str],
                   decalage_utc: float, dossier: str, nord: float = 0.0, taille: int = 1600) -> dict:
    """Capture la vue de Lite a plusieurs heures d'une journee.

    date : AAAA-MM-JJ. heures : ["08:00", "12:00", ...] en heure locale.
    decalage_utc : heures entre l'heure locale et UTC (ete en Suisse : 2, hiver : 1).
    nord : angle du nord geographique par rapport a l'axe +Y de Rhino, en degres, sens horaire.
    Le ciel passe en mode GEO pendant l'etude. L'ambiance d'origine est remise a la fin.
    """
    import time
    sortie = Path(dossier).resolve()  # D5 Lite demande un chemin absolu
    sortie.mkdir(parents=True, exist_ok=True)
    origine = lire_ambiance(d5)
    lignes = []
    try:
        for h in heures:
            hh, mm = [int(x) for x in h.split(":")]
            local = _dt.datetime.strptime(date, "%Y-%m-%d").replace(hour=hh, minute=mm)
            alt, azi = position_soleil(latitude, longitude, local - _dt.timedelta(hours=decalage_utc))
            ligne = {"heure": h, "altitude": round(alt, 2), "azimut": round(azi, 2), "azimut_rhino": round((azi + nord) % 360, 2)}
            if alt <= 0:
                ligne["capture"] = None
                ligne["remarque"] = "soleil sous l'horizon"
                lignes.append(ligne)
                continue
            fichier = (sortie / f"soleil_{date}_{hh:02d}{mm:02d}.png").as_posix()
            r = d5.executer([
                {"id": "m", "type": "lite.sky.patch.mode", "target": CIEL, "params": {"mode": "GEO"}},
                {"id": "a", "type": "lite.sky.patch.geoAltitude", "target": CIEL, "params": {"altitude": alt}},
                {"id": "z", "type": "lite.sky.patch.geoAzimuth", "target": CIEL, "params": {"azimuth": (azi + nord) % 360}}], nom="soleil")
            time.sleep(3)
            d5.executer([{"id": "c", "type": "lite.screenshot.capture", "target": VUE, "params": {"maxSize": taille, "path": fichier}}], nom="soleil_capture")
            time.sleep(4)
            ligne["capture"] = fichier if Path(fichier).is_file() else None
            ligne["ok"] = r["ok"] and ligne["capture"] is not None
            lignes.append(ligne)
    finally:
        remise = appliquer_ambiance(d5, origine, ["ciel"])
    return {"lieu": {"latitude": latitude, "longitude": longitude, "nord": nord}, "date": date,
            "captures": lignes, "ambiance_remise": remise["ok"], "ecarts_remise": remise["ecarts"]}


# ================================================== serie de rendus
def preparer_rendus(d5: D5Lite, dossier: str, scenes: list[str] | None = None, qualite: str = "high",
                    format_image: str = "png", type_sortie: str = "image", rapport: str | None = None) -> dict:
    """Ecrit un workflow de rendu par scene. Ne lance aucun rendu.

    L'utilisateur lance ensuite : d5lite.py lancer-rendus <dossier>
    """
    sortie = Path(dossier).resolve()  # D5 Lite demande un chemin absolu
    sortie.mkdir(parents=True, exist_ok=True)
    for ancien in sortie.glob("*.rendu.json"):
        ancien.unlink()
    liste = d5.lire("lite.scene.list", {"kind": "scene"})["valeur"].get("items") or []
    if scenes:
        liste = [s for s in liste if s["name"] in scenes]
    noms = [s["name"] for s in liste]
    doublons = sorted({n for n in noms if noms.count(n) > 1})
    prets = []
    for i, s in enumerate(liste):
        nom_fichier = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in s["name"]) or f"scene_{i}"
        if s["name"] in doublons:
            nom_fichier += f"_{i}"
        params = {"confirmed": True, "outputPath": (sortie / f"{nom_fichier}.{format_image}").as_posix(),
                  "quality": qualite, "format": format_image, "outputType": type_sortie}
        if rapport:
            params["aspectRatio"] = rapport
        wf = {"workflowVersion": "1.0", "scene": s["name"], "operations": [
            {"id": "choisir", "type": "lite.scene.select", "target": {"kind": "scene"}, "params": {"sceneId": s["sceneId"]}},
            {"id": "rendu", "type": "lite.render.job.start", "target": RENDU, "params": params, "dependsOn": ["choisir"]}]}
        f = sortie / f"{i + 1:02d}_{nom_fichier}.rendu.json"
        f.write_text(json.dumps(wf, indent=2, ensure_ascii=False), encoding="utf-8")
        prets.append({"scene": s["name"], "workflow": str(f), "image": params["outputPath"]})
    commande = f'"{sys.executable}" "{Path(__file__).resolve()}" lancer-rendus "{sortie}"'.replace("\\", "/")
    return {"rendus": prets, "noms_en_double": doublons, "qualite": qualite, "commande_a_lancer_par_l_utilisateur": commande}


def lancer_rendus(d5: D5Lite, dossier: str, delai_s: int = 1800) -> dict:
    """Lance les rendus prepares, l'un apres l'autre. A lancer par l'utilisateur.

    Lancer cette commande vaut accord pour les plans de rendu du dossier.
    """
    import time
    bilan = []
    for f in sorted(Path(dossier).glob("*.rendu.json")):
        wf = json.loads(f.read_text(encoding="utf-8"))
        image = Path(wf["operations"][-1]["params"]["outputPath"])
        if image.is_file():
            bilan.append({"scene": wf.get("scene"), "etat": "deja rendu", "image": str(image)})
            continue
        debut = time.time()
        r = d5.executer(wf["operations"], nom="rendu", risque_max="confirmWrite", confirme=True, enchainer=False)
        if not r["ok"]:
            bilan.append({"scene": wf.get("scene"), "etat": "refuse", "detail": r.get("diagnostics") or r.get("segments")})
            continue
        time.sleep(2)
        while time.time() - debut < delai_s:
            e = d5.lire("lite.render.job.status", RENDU)["valeur"] or {}
            if not e.get("active") and image.is_file():
                break
            if not e.get("active") and time.time() - debut > 60:
                break
            time.sleep(3)
        duree = round(time.time() - debut)
        ok = image.is_file() and image.stat().st_size > 0
        bilan.append({"scene": wf.get("scene"), "etat": "rendu" if ok else "image absente", "duree_s": duree,
                      "image": str(image), "octets": image.stat().st_size if ok else 0})
        print(json.dumps(bilan[-1], ensure_ascii=False), flush=True)
    (Path(dossier) / "bilan_rendus.json").write_text(json.dumps(bilan, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"rendus": bilan, "reussis": len([b for b in bilan if b["etat"] in ("rendu", "deja rendu")]), "total": len(bilan)}


# ================================================ controle avant rendu
def controle(d5: D5Lite) -> dict:
    """Controle avant rendu, cote D5 Lite. Lecture seule.

    Le controle cote Rhino (materiaux, lumieres, vues) se fait par d5scene.rapport().
    """
    etat = d5.etat()
    alertes, infos = [], []
    if not etat["connecte"]:
        return {"pret": False, "alertes": ["D5 Lite ne repond pas : " + str(etat.get("code"))], "etat": etat}
    if not etat.get("contrats_testes"):
        alertes.append("La CLI a change depuis les tests du skill. Verifiez chaque ecriture.")
    a = lire_ambiance(d5)
    scenes = d5.lire("lite.scene.list", {"kind": "scene"})["valeur"] or {}
    contenu = d5.lire("lite.scene.read", {"kind": "scene"})["valeur"] or {}
    tache = d5.lire("lite.render.job.status", RENDU)["valeur"] or {}
    noms = [s["name"] for s in scenes.get("items") or []]
    if not noms:
        alertes.append("Aucune scene. Creez des vues nommees dans Rhino.")
    for n in sorted({n for n in noms if noms.count(n) > 1}):
        alertes.append(f"Deux scenes portent le nom {n}.")
    if not scenes.get("currentSceneId"):
        infos.append("Aucune scene courante : la vue de Lite ne correspond a aucune scene enregistree.")
    if tache.get("active"):
        alertes.append("Un rendu est en cours.")
    c, p, r = a["ciel"], a["post"], a["rendu"]
    if _est_nuit(a):
        lumieres = sum(contenu.get(k, 0) for k in ("point_light", "spot_light", "area_light", "belt_light", "disk_light"))
        (alertes if lumieres == 0 else infos).append(
            f"Ciel de nuit avec {lumieres} lumiere(s) allumee(s)." + (" L'image sera noire." if lumieres == 0 else ""))
    if c.get("mode") == "HDRI" and c.get("hdri_fichier") and not Path(c["hdri_fichier"]).is_file():
        alertes.append(f"Fichier HDRI introuvable : {c['hdri_fichier']}")
    if p.get("exposure") is not None and abs(p["exposure"]) > 0.6:
        alertes.append(f"Exposition forte : {p['exposure']}")
    if p.get("autoExposure") is False:
        infos.append("Exposition automatique desactivee.")
    if r.get("quality") == "low":
        infos.append("Qualite de rendu : low.")
    if r.get("outputType") == "panorama":
        infos.append("Type de sortie : panorama.")
    if contenu.get("instance", 0) == 0:
        alertes.append("La scene de Lite ne contient aucun objet.")
    return {"pret": not alertes, "alertes": alertes, "infos": infos, "scenes": noms, "scene_courante": scenes.get("currentSceneId"),
            "contenu": contenu, "ciel": c, "post": p, "rendu": r}


# ================================================ comparaison d'images
def comparer(image: str, reference: str) -> dict:
    """Compare une capture a une image de reference. Donne des pistes de reglage.

    Les pistes sont des ordres de grandeur. Reglez un champ a la fois, puis recapturez.
    """
    try:
        import numpy as np
        from PIL import Image
    except ImportError as err:
        raise ErreurD5("La comparaison demande Pillow et numpy (presents dans le Python AOI).") from err

    def mesures(chemin):
        im = np.asarray(Image.open(chemin).convert("RGB").resize((256, 256)), dtype=float) / 255.0
        lum = 0.2126 * im[..., 0] + 0.7152 * im[..., 1] + 0.0722 * im[..., 2]
        mx, mn = im.max(axis=2), im.min(axis=2)
        sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0)
        return {"luminance": float(lum.mean()), "contraste": float(lum.std()), "saturation": float(sat.mean()),
                "rouge": float(im[..., 0].mean()), "vert": float(im[..., 1].mean()), "bleu": float(im[..., 2].mean()),
                "ombres": float(np.percentile(lum, 5)), "hautes_lumieres": float(np.percentile(lum, 95))}

    a, b = mesures(image), mesures(reference)
    ecart = {k: round(b[k] - a[k], 4) for k in a}
    pistes = []
    if abs(ecart["luminance"]) > 0.03:
        pistes.append({"champ": "exposure", "sens": "augmenter" if ecart["luminance"] > 0 else "diminuer",
                       "pas_conseille": round(min(0.3, abs(ecart["luminance"])), 2)})
    chaleur = (b["rouge"] - b["bleu"]) - (a["rouge"] - a["bleu"])
    if abs(chaleur) > 0.03:
        pistes.append({"champ": "temperature", "sens": "image plus chaude" if chaleur > 0 else "image plus froide",
                       "remarque": "le sens du reglage en kelvins est a verifier par une capture"})
    if abs(ecart["saturation"]) > 0.04:
        pistes.append({"champ": "saturation", "sens": "augmenter" if ecart["saturation"] > 0 else "diminuer",
                       "pas_conseille": round(min(0.3, abs(ecart["saturation"])), 2)})
    if abs(ecart["contraste"]) > 0.03:
        pistes.append({"champ": "contrast", "sens": "augmenter" if ecart["contraste"] > 0 else "diminuer",
                       "pas_conseille": round(min(0.3, abs(ecart["contraste"]) * 2), 2)})
    return {"image": {k: round(v, 4) for k, v in a.items()}, "reference": {k: round(v, 4) for k, v in b.items()},
            "ecart": ecart, "pistes": pistes, "proche": not pistes}


def _json_arg(texte: str | None) -> dict | None:
    return json.loads(texte) if texte else None


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Pilotage de D5 Lite par sa CLI officielle.")
    sp = p.add_subparsers(dest="commande", required=True)
    sp.add_parser("etat")
    a = sp.add_parser("aide"); a.add_argument("mot")
    o = sp.add_parser("operation"); o.add_argument("type")
    l = sp.add_parser("lire"); l.add_argument("type"); l.add_argument("--cible"); l.add_argument("--params")
    e = sp.add_parser("executer"); e.add_argument("fichier")
    e.add_argument("--risque-max", default="safeWrite", choices=RISQUES)
    e.add_argument("--confirme", action="store_true",
                   help="Declare l'accord de l'utilisateur. A passer seulement apres cet accord.")
    i = sp.add_parser("instantane"); i.add_argument("--lumieres", default="")
    g = sp.add_parser("regler", help="Ecrit une valeur et la verifie par relecture.")
    g.add_argument("ecriture"); g.add_argument("--params", required=True)
    g.add_argument("--lecture", required=True); g.add_argument("--champ", required=True)
    g.add_argument("--cible"); g.add_argument("--cible-lecture"); g.add_argument("--attendu")
    am = sp.add_parser("ambiance", help="lire | enregistrer <nom> | appliquer <nom> | lister")
    am.add_argument("action", choices=["lire", "enregistrer", "appliquer", "lister"])
    am.add_argument("nom", nargs="?")
    am.add_argument("--parties", default="ciel,post,rendu")
    sp.add_parser("nuit", help="Ciel de nuit. Garde l'ambiance de jour.")
    jr = sp.add_parser("jour", help="Remet le ciel de jour."); jr.add_argument("--ambiance", default="_avant_nuit")
    en = sp.add_parser("ensoleillement", help="Captures a plusieurs heures d'une journee.")
    en.add_argument("--latitude", type=float, required=True); en.add_argument("--longitude", type=float, required=True)
    en.add_argument("--date", required=True); en.add_argument("--heures", required=True, help="08:00,10:00,12:00")
    en.add_argument("--decalage-utc", type=float, required=True); en.add_argument("--dossier", required=True)
    en.add_argument("--nord", type=float, default=0.0); en.add_argument("--taille", type=int, default=1600)
    pr = sp.add_parser("preparer-rendus", help="Ecrit un workflow de rendu par scene. Ne rend rien.")
    pr.add_argument("dossier"); pr.add_argument("--scenes", default="")
    pr.add_argument("--qualite", default="high", choices=["low", "high"]); pr.add_argument("--format", default="png", choices=["png", "jpg"])
    pr.add_argument("--type", default="image", choices=["image", "panorama"]); pr.add_argument("--rapport")
    lr = sp.add_parser("lancer-rendus", help="Lance les rendus prepares. A lancer par l'utilisateur.")
    lr.add_argument("dossier"); lr.add_argument("--delai", type=int, default=1800)
    sp.add_parser("controle", help="Controle avant rendu, cote D5 Lite.")
    cp = sp.add_parser("comparer", help="Compare une capture a une image de reference.")
    cp.add_argument("image"); cp.add_argument("reference")
    ca = sp.add_parser("capturer", help="Capture la vue de Lite dans un fichier PNG.")
    ca.add_argument("fichier"); ca.add_argument("--taille", type=int, default=1600)
    args = p.parse_args(argv)

    try:
        d5 = D5Lite()
        if args.commande == "etat":
            sortie = d5.etat()
        elif args.commande == "aide":
            sortie = [{"type": r.get("type"), "risque": r.get("risk"), "description": r.get("description")}
                      for r in d5.aide_recherche(args.mot)]
        elif args.commande == "operation":
            op = d5.aide_operation(args.type)
            sortie = {k: op.get(k) for k in ("type", "risk", "status", "executableHint", "requires", "description", "usage")}
        elif args.commande == "lire":
            sortie = d5.lire(args.type, _json_arg(args.cible), _json_arg(args.params))
        elif args.commande == "executer":
            wf = json.loads(Path(args.fichier).read_text(encoding="utf-8-sig"))
            sortie = d5.executer(wf["operations"], nom=Path(args.fichier).stem,
                                 risque_max=args.risque_max, confirme=args.confirme, enchainer=False)
        elif args.commande == "regler":
            sortie = d5.regler(args.ecriture, json.loads(args.params), args.lecture, args.champ,
                               cible=_json_arg(args.cible), cible_lecture=_json_arg(args.cible_lecture),
                               attendu=json.loads(args.attendu) if args.attendu else None)
            if sortie["verdict"] != "OK":
                sortie["ok"] = False
        elif args.commande == "ambiance":
            if args.action == "lire":
                sortie = lire_ambiance(d5)
            elif args.action == "lister":
                sortie = sorted(f.stem for f in dossier_ambiances().glob("*.json"))
            elif not args.nom:
                raise ErreurD5("Donnez le nom de l'ambiance.")
            elif args.action == "enregistrer":
                sortie = enregistrer_ambiance(d5, args.nom)
            else:
                sortie = appliquer_ambiance(d5, charger_ambiance(args.nom), [x for x in args.parties.split(",") if x])
        elif args.commande == "nuit":
            sortie = nuit(d5)
        elif args.commande == "jour":
            sortie = jour(d5, args.ambiance)
        elif args.commande == "ensoleillement":
            sortie = ensoleillement(d5, args.latitude, args.longitude, args.date, args.heures.split(","),
                                    args.decalage_utc, args.dossier, args.nord, args.taille)
        elif args.commande == "preparer-rendus":
            sortie = preparer_rendus(d5, args.dossier, [s for s in args.scenes.split(",") if s] or None,
                                     args.qualite, args.format, args.type, args.rapport)
        elif args.commande == "lancer-rendus":
            sortie = lancer_rendus(d5, args.dossier, args.delai)
        elif args.commande == "controle":
            sortie = controle(d5)
        elif args.commande == "comparer":
            sortie = comparer(args.image, args.reference)
        elif args.commande == "capturer":
            import time
            chemin = Path(args.fichier).resolve().as_posix()
            Path(chemin).parent.mkdir(parents=True, exist_ok=True)
            r = d5.executer([{"id": "c", "type": "lite.screenshot.capture", "target": VUE,
                              "params": {"maxSize": args.taille, "path": chemin}}], nom="capture")
            for _ in range(20):
                if Path(chemin).is_file():
                    break
                time.sleep(0.5)
            sortie = {"ok": r["ok"] and Path(chemin).is_file(), "fichier": chemin}
        else:
            guids = [g for g in args.lumieres.split(",") if g.strip()]
            sortie = d5.instantane(guids)
    except ErreurD5 as err:
        print(json.dumps({"ok": False, "erreur": str(err)}, ensure_ascii=False))
        return 2
    print(json.dumps(sortie, ensure_ascii=False, indent=2))
    if isinstance(sortie, dict) and sortie.get("ok") is False:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
