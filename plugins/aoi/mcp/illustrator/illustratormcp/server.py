"""Serveur MCP illustrator : pilote Adobe Illustrator par son moteur ExtendScript (panneau/moteur.jsx).

Deux canaux, un seul moteur :
- panneau (défaut) : le serveur écoute sur ws://127.0.0.1:PORT. Le panneau CEP « Claude MCP » se connecte
  quand l'utilisateur clique sur Connecter. Requête {"id", "c": commande, "p": paramètres} ; réponse
  {"id", "ok": true, "r"} ou {"id", "ok": false, "e": {"code", "message"}}. À la connexion, le panneau
  envoie {"hello": {"version", "illustrator", "moteur", "execute_script"}}.
- com : pas de panneau, voir com.py. Le serveur parle à tout Illustrator qui tourne.
Le serveur ne démarre jamais Illustrator.

Variables d'environnement : ILLUSTRATOR_MCP_CANAL ("panneau" ou "com"), ILLUSTRATOR_MCP_PORT (8766),
ILLUSTRATOR_MCP_TIMEOUT (60 s par appel), ILLUSTRATOR_MCP_LOG_LEVEL (INFO), ILLUSTRATOR_MCP_LECTEURS ("C"),
ILLUSTRATOR_MCP_UNC (non), ILLUSTRATOR_MCP_SCRIPTS (canal com seulement ; non : execute_script refusé).
"""
import collections
import concurrent.futures
import itertools
import json
import logging
import os
import re
import socket
import sys
import threading
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict, Optional

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from illustratormcp import com, ws

logging.basicConfig(level=os.environ.get("ILLUSTRATOR_MCP_LOG_LEVEL", "INFO"),
                    format="%(asctime)s %(name)s %(levelname)s %(message)s", stream=sys.stderr)
logger = logging.getLogger("illustratormcp")

DELAI_S = float(os.environ.get("ILLUSTRATOR_MCP_TIMEOUT", "60"))
SCRIPTS_AUTORISES = os.environ.get("ILLUSTRATOR_MCP_SCRIPTS", "") == "1"

CANAL = os.environ.get("ILLUSTRATOR_MCP_CANAL", "panneau").strip().lower()
HOTE = "127.0.0.1"
PORT = int(os.environ.get("ILLUSTRATOR_MCP_PORT", "8766"))
VERSION_PANNEAU_ATTENDUE = "0.1.0"

MSG_LANCER = "Illustrator ne tourne pas. Ouvrez Illustrator : le serveur ne le démarre pas."
MSG_PANNEAU = ("Panneau Illustrator non connecté. Ouvrez Illustrator, puis Fenêtre > Extensions > "
               "Claude MCP. Cliquez sur Connecter dans le panneau : il ne se connecte pas seul.")
MSG_DELAI = ("Illustrator n'a pas répondu en %.0f s à %s. Une boîte de dialogue "
             "est peut-être ouverte dans Illustrator.")

# Chemins acceptés dans une commande. Par défaut : le lecteur C: seul, et aucun chemin réseau.
#   ILLUSTRATOR_MCP_LECTEURS : lettres des lecteurs acceptés ("C", "CD"), ou "*" pour tous.
#   ILLUSTRATOR_MCP_UNC=1    : accepte aussi les chemins réseau \\serveur\partage.
LECTEURS = os.environ.get("ILLUSTRATOR_MCP_LECTEURS", "C").upper().replace(":", "").replace(",", "").replace(" ", "")
UNC_ACCEPTE = os.environ.get("ILLUSTRATOR_MCP_UNC", "") == "1"


def _motif_interdit() -> Optional["re.Pattern[str]"]:
    parties = []
    if "*" not in LECTEURS:
        refuses = "".join(c for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" if c not in LECTEURS)
        if refuses:
            parties.append(r"(?<![A-Za-z0-9])[%s]:[\\/]" % refuses)
    if not UNC_ACCEPTE:
        # \\serveur\... partout dans le texte ; //serveur/... en début de texte seulement,
        # pour ne pas refuser un commentaire « // » ou une adresse « http:// » dans un script.
        parties.append(r"\\\\[\w.$-]+\\|^//[\w.$-]+/")
    return re.compile("(?i)" + "|".join(parties)) if parties else None


CHEMIN_INTERDIT = _motif_interdit()
REGLE_CHEMINS = "%s ; %s" % (
    "tous les lecteurs sont acceptés" if "*" in LECTEURS
    else "lecteurs acceptés : %s" % ", ".join(c + ":" for c in LECTEURS),
    "chemins réseau acceptés" if UNC_ACCEPTE else "chemins réseau \\\\serveur refusés")


class PontIndisponible(ToolError):
    """Illustrator ne tourne pas, ou ne répond pas."""


class ErreurPont(ToolError):
    """Le moteur a répondu par une erreur, ou la requête est refusée avant l'envoi."""

    def __init__(self, code: str, message: str):
        super().__init__("%s (%s)" % (message, code))
        self.code = code


def verifier_chemins(objet: Any) -> None:
    """Refuse toute chaîne qui cite un lecteur non accepté ou un chemin réseau (voir LECTEURS)."""
    if isinstance(objet, str):
        if CHEMIN_INTERDIT is not None and CHEMIN_INTERDIT.search(objet):
            raise ErreurPont("chemin_interdit", "Chemin refusé (%s) : %s. Copiez le fichier sur un lecteur accepté "
                             "ou faites l'opération vous-même." % (REGLE_CHEMINS, objet[:200]))
    elif isinstance(objet, dict):
        for valeur in objet.values():
            verifier_chemins(valeur)
    elif isinstance(objet, (list, tuple)):
        for valeur in objet:
            verifier_chemins(valeur)


class Pont:
    """Un appel à la fois vers Illustrator. Les deux canaux rendent la réponse du moteur."""

    nom = ""

    def demarrer(self) -> None:
        pass

    def arreter(self) -> None:
        pass

    def etat(self) -> Dict[str, Any]:
        """Champs du canal pour l'outil status."""
        return {}

    def verifier_scripts(self) -> None:
        """Lève une erreur si execute_script n'est pas autorisé."""
        raise NotImplementedError

    def _echanger(self, commande: str, params: Dict[str, Any], delai: float) -> Dict[str, Any]:
        raise NotImplementedError

    def appeler(self, commande: str, params: Optional[Dict[str, Any]] = None,
                delai: Optional[float] = None) -> Any:
        """Envoie une commande au moteur et rend son résultat `r`."""
        params = {k: v for k, v in (params or {}).items() if v is not None}
        verifier_chemins(params)
        reponse = self._echanger(commande, params, delai or DELAI_S)
        if not reponse.get("ok"):
            e = reponse.get("e") or {}
            raise ErreurPont(e.get("code", "erreur"), e.get("message", "erreur du moteur"))
        return reponse.get("r")


class PontCOM(Pont):
    """Canal COM : pas de panneau. Le serveur parle à tout Illustrator qui tourne."""

    nom = "com"

    def __init__(self) -> None:
        self.canal = com.CanalCOM()

    def arreter(self) -> None:
        self.canal.arreter()

    def etat(self) -> Dict[str, Any]:
        return {"execute_script": SCRIPTS_AUTORISES}

    def verifier_scripts(self) -> None:
        if not SCRIPTS_AUTORISES:
            raise ErreurPont("non_autorise", "execute_script est désactivé. Pour l'autoriser, mettez "
                             "ILLUSTRATOR_MCP_SCRIPTS=1 dans l'environnement du serveur, puis relancez-le.")

    def _echanger(self, commande: str, params: Dict[str, Any], delai: float) -> Dict[str, Any]:
        try:
            return self.canal.appeler(commande, params, delai)
        except com.Absent:
            raise PontIndisponible(MSG_LANCER)
        except com.Occupe:
            raise ErreurPont("occupe", "Illustrator refuse l'appel : une fenêtre est ouverte dans Illustrator, "
                             "ou une opération est en cours. Fermez la fenêtre, puis recommencez.")
        except concurrent.futures.TimeoutError:
            raise ErreurPont("delai", MSG_DELAI % (delai, commande))
        except (RuntimeError, ValueError, ImportError) as e:
            raise ErreurPont("canal", "Appel à Illustrator impossible : %s" % e)


class PontPanneau(Pont):
    """Canal panneau : le serveur écoute, le panneau CEP se connecte quand l'utilisateur clique.
    Un seul panneau actif : une nouvelle connexion remplace l'ancienne."""

    nom = "panneau"

    def __init__(self, hote: str = HOTE, port: int = PORT):
        self.hote, self.port = hote, port
        self.ecoute: Optional[socket.socket] = None
        self.erreur_ecoute = ""
        self.client: Optional[socket.socket] = None
        self.info: Dict[str, Any] = {}
        self.verrou_envoi = threading.Lock()
        self.verrou_appel = threading.Lock()
        self.attentes: Dict[int, list] = {}
        self.ids = itertools.count(1)
        self.actif = False
        self.journal: collections.deque = collections.deque(maxlen=20)  # erreurs JavaScript du panneau

    # --- écoute ---------------------------------------------------------------------------
    def demarrer(self) -> None:
        if self.actif:
            return
        try:
            self.ecoute = socket.create_server((self.hote, self.port))
        except OSError as e:
            self.erreur_ecoute = "port %d indisponible (%s) : un autre serveur illustrator-mcp tourne peut-être" \
                                 % (self.port, e)
            logger.warning(self.erreur_ecoute)
            return
        self.actif = True
        threading.Thread(target=self._accepter, name="ws-ecoute", daemon=True).start()
        logger.info("en attente du panneau sur ws://%s:%d", self.hote, self.port)

    def arreter(self) -> None:
        self.actif = False
        for s in (self.ecoute, self.client):
            if s is not None:
                try:
                    s.close()
                except OSError:
                    pass

    def _accepter(self) -> None:
        while self.actif:
            try:
                conn, _ = self.ecoute.accept()
            except OSError:
                return
            threading.Thread(target=self._servir, args=(conn,), name="ws-client", daemon=True).start()

    def _envoyer(self, conn: socket.socket, donnees: bytes, opcode: int = ws.TEXTE) -> None:
        with self.verrou_envoi:
            conn.sendall(ws.trame(donnees, opcode))

    def _servir(self, conn: socket.socket) -> None:
        try:
            conn.settimeout(10)
            ws.poignee_serveur(conn)
            conn.settimeout(None)
        except (OSError, ws.ErreurWS) as e:
            logger.warning("connexion refusée : %s", e)
            conn.close()
            return
        ancien, self.client, self.info = self.client, conn, {}
        if ancien is not None:
            try:
                ancien.close()
            except OSError:
                pass
        logger.info("panneau connecté")
        try:
            while True:
                opcode, donnees = ws.lire_message(conn, lambda d, o: self._envoyer(conn, d, o))
                if opcode == ws.FERMER:
                    break
                try:
                    message = json.loads(donnees.decode("utf-8"))
                except ValueError:
                    logger.warning("message illisible du panneau")
                    continue
                if "hello" in message:
                    self.info = message["hello"] or {}
                    if self.info.get("version") != VERSION_PANNEAU_ATTENDUE:
                        logger.warning("panneau version %s, serveur prévu pour %s", self.info.get("version"),
                                       VERSION_PANNEAU_ATTENDUE)
                    continue
                if "log" in message:
                    self.journal.append(str(message["log"])[:500])
                    logger.warning("panneau : %s", self.journal[-1])
                    continue
                attente = self.attentes.get(message.get("id"))
                if attente is not None:
                    attente[1] = message
                    attente[0].set()
        except (OSError, ws.ErreurWS) as e:
            logger.info("panneau déconnecté (%s)", e)
        finally:
            try:
                conn.close()
            except OSError:
                pass
            if self.client is conn:
                self.client, self.info = None, {}
                for attente in list(self.attentes.values()):
                    attente[0].set()  # réponse None : connexion perdue

    # --- appels ---------------------------------------------------------------------------
    def connecte(self) -> bool:
        return self.client is not None

    def etat(self) -> Dict[str, Any]:
        etat: Dict[str, Any] = {"port": self.port, "execute_script": bool(self.info.get("execute_script"))}
        if self.info.get("version"):
            etat["panneau"] = self.info["version"]
        if self.erreur_ecoute:
            etat["erreur"] = self.erreur_ecoute
        if self.journal:
            etat["journal"] = list(self.journal)
        return etat

    def verifier_scripts(self) -> None:
        if not self.connecte():
            raise PontIndisponible(self.erreur_ecoute or MSG_PANNEAU)
        if not self.info.get("execute_script"):
            raise ErreurPont("non_autorise", "execute_script est désactivé. Pour l'autoriser, cochez "
                             "« Autoriser les scripts ExtendScript (JSX) » dans le panneau Claude MCP.")

    def _echanger(self, commande: str, params: Dict[str, Any], delai: float) -> Dict[str, Any]:
        """Une requête à la fois."""
        with self.verrou_appel:
            conn = self.client
            if conn is None:
                raise PontIndisponible(self.erreur_ecoute or MSG_PANNEAU)
            ident = next(self.ids)
            attente = [threading.Event(), None]
            self.attentes[ident] = attente
            try:
                donnees = json.dumps({"id": ident, "c": commande, "p": params}, ensure_ascii=False)
                try:
                    self._envoyer(conn, donnees.encode("utf-8"))
                except OSError as e:
                    raise PontIndisponible("Envoi au panneau impossible (%s). %s" % (e, MSG_PANNEAU))
                if not attente[0].wait(delai):
                    raise ErreurPont("delai", MSG_DELAI % (delai, commande))
            finally:
                self.attentes.pop(ident, None)
        if attente[1] is None:
            raise PontIndisponible("Connexion au panneau perdue pendant %s." % commande)
        return attente[1]


_pont: Pont = PontCOM() if CANAL == "com" else PontPanneau()


def get_pont() -> Pont:
    return _pont


@asynccontextmanager
async def server_lifespan(server: MCPServer) -> AsyncIterator[Dict[str, Any]]:
    _pont.demarrer()
    try:
        yield {}
    finally:
        _pont.arreter()


INSTRUCTIONS = (
    "Pilote Adobe Illustrator" + (" par le panneau Claude MCP, que l'utilisateur connecte lui-même. "
                                  if CANAL != "com" else ". ") + "Pour économiser les allers-retours : lis l'état avec un seul appel snapshot "
    "(sans items d'abord), puis groupe toutes les modifications dans un seul appel batch. "
    "Utilise dry_run=true pour vérifier un lot long. Un lot = une seule annulation (Ctrl+Z) dans Illustrator. "
    "Illustrator est rapide (200 objets en moins de 10 ms) : le coût est dans la taille des textes échangés. "
    "Pour contrôler un dessin, ajoute preview au lot et lis le PNG. "
    "Chemins de fichiers : " + REGLE_CHEMINS + ".")

mcp = MCPServer("IllustratorMCP", instructions=INSTRUCTIONS, lifespan=server_lifespan)


def main() -> None:
    mcp.run()
