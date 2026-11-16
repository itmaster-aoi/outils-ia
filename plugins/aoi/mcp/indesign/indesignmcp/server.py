"""Serveur MCP indesign : serveur WebSocket local pour le plugin UXP, et serveur MCP.

Le plugin UXP (plugin/, dans InDesign) se connecte à ws://127.0.0.1:PORT. Un plugin UXP
ne peut pas écouter sur un port : c'est donc le serveur MCP qui écoute.
Protocole : requête {"id", "c": commande, "p": paramètres} ; réponse {"id", "ok": true, "r"}
ou {"id", "ok": false, "e": {"code", "message"}}. À la connexion, le plugin envoie
{"hello": {"version", "indesign", "execute_script"}}.

Variables d'environnement : INDESIGN_MCP_PORT (8765), INDESIGN_MCP_TIMEOUT (60 s par appel),
INDESIGN_MCP_LOG_LEVEL (INFO), INDESIGN_MCP_LECTEURS ("C"), INDESIGN_MCP_UNC (non).
"""
import collections
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

from indesignmcp import ws

logging.basicConfig(level=os.environ.get("INDESIGN_MCP_LOG_LEVEL", "INFO"),
                    format="%(asctime)s %(name)s %(levelname)s %(message)s", stream=sys.stderr)
logger = logging.getLogger("indesignmcp")

HOTE = "127.0.0.1"
PORT = int(os.environ.get("INDESIGN_MCP_PORT", "8765"))
DELAI_S = float(os.environ.get("INDESIGN_MCP_TIMEOUT", "60"))
VERSION_PLUGIN_ATTENDUE = "0.1.0"

MSG_LANCER = ("Plugin InDesign non connecté. Ouvrez InDesign, puis Fenêtre > Modules externes > "
              "Claude MCP. Cliquez sur Connecter dans le panneau : il ne se connecte pas seul.")

# Chemins acceptés dans une commande. Par défaut : le lecteur C: seul, et aucun chemin réseau.
#   INDESIGN_MCP_LECTEURS : lettres des lecteurs acceptés ("C", "CD"), ou "*" pour tous.
#   INDESIGN_MCP_UNC=1    : accepte aussi les chemins réseau \\serveur\partage.
LECTEURS = os.environ.get("INDESIGN_MCP_LECTEURS", "C").upper().replace(":", "").replace(",", "").replace(" ", "")
UNC_ACCEPTE = os.environ.get("INDESIGN_MCP_UNC", "") == "1"


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
    """Le plugin n'est pas connecté (InDesign fermé, panneau fermé, port occupé)."""


class ErreurPont(ToolError):
    """Le plugin a répondu par une erreur, ou la requête est refusée avant l'envoi."""

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
    """Écoute le plugin. Un seul plugin actif : une nouvelle connexion remplace l'ancienne."""

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
        self.journal: collections.deque = collections.deque(maxlen=20)  # erreurs JavaScript du plugin

    # --- écoute ---------------------------------------------------------------------------
    def demarrer(self) -> None:
        try:
            self.ecoute = socket.create_server((self.hote, self.port))
        except OSError as e:
            self.erreur_ecoute = "port %d indisponible (%s) : un autre serveur indesign-mcp tourne peut-être" \
                                 % (self.port, e)
            logger.warning(self.erreur_ecoute)
            return
        self.actif = True
        threading.Thread(target=self._accepter, name="ws-ecoute", daemon=True).start()
        logger.info("en attente du plugin sur ws://%s:%d", self.hote, self.port)

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
        logger.info("plugin connecté")
        try:
            while True:
                opcode, donnees = ws.lire_message(conn, lambda d, o: self._envoyer(conn, d, o))
                if opcode == ws.FERMER:
                    break
                try:
                    message = json.loads(donnees.decode("utf-8"))
                except ValueError:
                    logger.warning("message illisible du plugin")
                    continue
                if "hello" in message:
                    self.info = message["hello"] or {}
                    if self.info.get("version") != VERSION_PLUGIN_ATTENDUE:
                        logger.warning("plugin version %s, serveur prévu pour %s", self.info.get("version"),
                                       VERSION_PLUGIN_ATTENDUE)
                    continue
                if "log" in message:
                    self.journal.append(str(message["log"])[:500])
                    logger.warning("plugin : %s", self.journal[-1])
                    continue
                attente = self.attentes.get(message.get("id"))
                if attente is not None:
                    attente[1] = message
                    attente[0].set()
        except (OSError, ws.ErreurWS) as e:
            logger.info("plugin déconnecté (%s)", e)
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

    def appeler(self, commande: str, params: Optional[Dict[str, Any]] = None,
                delai: Optional[float] = None) -> Any:
        """Envoie une commande au plugin et rend son résultat `r`. Une requête à la fois."""
        params = {k: v for k, v in (params or {}).items() if v is not None}
        verifier_chemins(params)
        with self.verrou_appel:
            conn = self.client
            if conn is None:
                raise PontIndisponible(self.erreur_ecoute or MSG_LANCER)
            ident = next(self.ids)
            attente = [threading.Event(), None]
            self.attentes[ident] = attente
            try:
                donnees = json.dumps({"id": ident, "c": commande, "p": params}, ensure_ascii=False)
                try:
                    self._envoyer(conn, donnees.encode("utf-8"))
                except OSError as e:
                    raise PontIndisponible("Envoi au plugin impossible (%s). %s" % (e, MSG_LANCER))
                if not attente[0].wait(delai or DELAI_S):
                    raise ErreurPont("delai", "InDesign n'a pas répondu en %.0f s à %s. Une boîte de dialogue "
                                     "est peut-être ouverte dans InDesign." % (delai or DELAI_S, commande))
            finally:
                self.attentes.pop(ident, None)
        reponse = attente[1]
        if reponse is None:
            raise PontIndisponible("Connexion au plugin perdue pendant %s." % commande)
        if not reponse.get("ok"):
            e = reponse.get("e") or {}
            raise ErreurPont(e.get("code", "erreur"), e.get("message", "erreur du plugin"))
        return reponse.get("r")


_pont = Pont()


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
    "Pilote Adobe InDesign par un plugin UXP. Pour économiser les allers-retours : lis l'état avec "
    "un seul appel snapshot (sans items d'abord), puis groupe toutes les modifications dans un seul appel batch. "
    "Utilise dry_run=true pour vérifier un lot long. Un lot = une seule annulation (Ctrl+Z) dans InDesign. "
    "Placer une image coûte 90 ms ; copier un bloc 3 ms. Pour contrôler une mise en page, ajoute preview au lot "
    "et lis le PNG. "
    "Chemins de fichiers : " + REGLE_CHEMINS + ".")

mcp = MCPServer("InDesignMCP", instructions=INSTRUCTIONS, lifespan=server_lifespan)


def main() -> None:
    mcp.run()
