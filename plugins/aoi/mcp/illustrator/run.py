r"""Lanceur du serveur illustrator-mcp.

Il faut Windows, Python 3.10 ou plus récent, avec les paquets mcp 2.x et pywin32.
Un Python embarqué (fichier ._pth) ne met pas le dossier du script dans sys.path : on l'ajoute.
`python run.py --check` vérifie les imports sans démarrer le serveur.
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import illustratormcp  # noqa: E402

if __name__ == "__main__":
    if "--check" in sys.argv:
        import mcp
        import win32com
        print("illustrator-mcp : imports ok")
        print("  illustratormcp :", illustratormcp.__file__, illustratormcp.__version__)
        print("  mcp            :", mcp.__file__)
        print("  win32com       :", win32com.__file__)
        print("  outils         :", ", ".join(t.name for t in asyncio.run(illustratormcp.mcp.list_tools())))
    else:
        illustratormcp.main()
