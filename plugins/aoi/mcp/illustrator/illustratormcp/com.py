"""Canal COM : le serveur appelle Illustrator par l'automatisation COM de Windows, sans panneau.

Illustrator exécute le moteur ExtendScript (moteur.jsx). Le moteur reste chargé dans Illustrator
entre deux appels : le serveur l'envoie une fois, puis à chaque changement du fichier.
Le canal ne démarre jamais Illustrator : il parle seulement à un Illustrator qui tourne.
"""
import concurrent.futures
import hashlib
import json
import os
import queue
import threading
from typing import Any, Callable, Dict, Optional

CHARGER = "\u0001charger"
# Un seul fichier de moteur pour les deux canaux : il est dans le dossier du panneau.
MOTEUR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "panneau", "moteur.jsx")

# Codes COM : aucun objet actif ; appel rejeté ou à refaire plus tard (Illustrator occupé).
PAS_LANCE = (-2147221021, -2147221005)
OCCUPE = (-2147418111, -2147417846)


class Absent(Exception):
    """Illustrator ne tourne pas."""


class Occupe(Exception):
    """Illustrator refuse l'appel : une fenêtre est ouverte, ou une opération est en cours."""


class CanalCOM:
    def __init__(self) -> None:
        self.file: "queue.Queue" = queue.Queue()
        self.fil: Optional[threading.Thread] = None
        self.verrou = threading.Lock()

    # COM lie un objet au fil qui l'a créé : un seul fil fait tous les appels.
    def _boucle(self) -> None:
        import pythoncom
        import win32com.client
        pythoncom.CoInitialize()
        while True:
            tache = self.file.get()
            if tache is None:
                return
            source, futur = tache
            try:
                app = win32com.client.GetActiveObject("Illustrator.Application")
                futur.set_result(app.DoJavaScript(source))
            except pythoncom.com_error as e:
                if e.hresult in PAS_LANCE:
                    futur.set_exception(Absent())
                elif e.hresult in OCCUPE:
                    futur.set_exception(Occupe())
                else:
                    detail = e.excepinfo[2] if e.excepinfo and e.excepinfo[2] else e.strerror
                    futur.set_exception(RuntimeError(str(detail).replace("\r", " ")))
            except Exception as e:  # noqa: BLE001 : le fil doit survivre
                futur.set_exception(e)

    def _executer(self, source: str, delai: float) -> Any:
        with self.verrou:
            if self.fil is None or not self.fil.is_alive():
                self.fil = threading.Thread(target=self._boucle, name="com-illustrator", daemon=True)
                self.fil.start()
        futur: "concurrent.futures.Future" = concurrent.futures.Future()
        self.file.put((source, futur))
        return futur.result(delai)  # lève concurrent.futures.TimeoutError

    def arreter(self) -> None:
        self.file.put(None)

    def appeler(self, commande: str, params: Dict[str, Any], delai: float) -> Dict[str, Any]:
        """Rend la réponse du moteur : {"ok": true, "r"} ou {"ok": false, "e": {"code", "message"}}."""
        with open(MOTEUR, encoding="utf-8") as f:
            moteur = f.read()
        signature = hashlib.sha256(moteur.encode("utf-8")).hexdigest()[:12]
        # json.dumps avec ensure_ascii : un littéral JavaScript valide, sans caractère hors ASCII.
        source = ("(function(){var m=$.global.__aimcp;if(!m||m.signature!==%s)return %s;return m.appel(%s,%s);})();"
                  % (json.dumps(signature), json.dumps(CHARGER), json.dumps(commande), json.dumps(params)))
        brut = self._executer(source, delai)
        if brut == CHARGER:
            self._executer(moteur + "\n$.global.__aimcp.signature=%s;'ok';" % json.dumps(signature), delai)
            brut = self._executer(source, delai)
        return json.loads(brut)
