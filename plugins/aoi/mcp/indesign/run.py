r"""Lanceur du serveur indesign-mcp.

Il faut Python 3.10 ou plus récent, avec le paquet mcp 2.x. Aucune autre librairie.
Un Python embarqué (fichier ._pth) ne met pas le dossier du script dans sys.path : on l'ajoute.
`python run.py --check` vérifie les imports sans démarrer le serveur.
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import indesignmcp  # noqa: E402

if __name__ == "__main__":
    if "--check" in sys.argv:
        import mcp
        print("indesign-mcp : imports ok")
        print("  indesignmcp :", indesignmcp.__file__, indesignmcp.__version__)
        print("  mcp         :", mcp.__file__)
        print("  outils      :", ", ".join(t.name for t in asyncio.run(indesignmcp.mcp.list_tools())))
    else:
        indesignmcp.main()
