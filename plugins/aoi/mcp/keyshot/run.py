r"""Lanceur du serveur keyshot.

Lancé par le Python AOI de l'atelier (%LOCALAPPDATA%\aoi\python), avec `-I -S` :
les copies figées de ce dossier (server/ et libs/) passent avant tout autre paquet, et le
contrôle des imports, réservé aux scripts de Claude, n'est pas chargé.
`python -I -S run.py --check` vérifie les imports sans démarrer le serveur.

Librairies : celles de ce dossier (libs/), copie identique de celles du serveur rhino (même
liste validée dans VERSIONS.md). Elles doivent rester sous ce dossier : le contrôle des imports
n'accepte d'office que les modules situés sous le dossier du script lancé. `mcp` importe
pywin32 sous Windows, d'où ses dossiers ajoutés comme pour rhino.
"""
import os
import sys

here = os.path.dirname(os.path.abspath(__file__))
libs = os.path.join(here, "libs")

sys.path[:0] = [
    os.path.join(here, "server"),
    libs,
    os.path.join(libs, "win32"),
    os.path.join(libs, "win32", "lib"),
    os.path.join(libs, "Pythonwin"),
]
dlls = os.path.join(libs, "pywin32_system32")
if os.path.isdir(dlls):
    os.add_dll_directory(dlls)

from keyshotmcp.server import main  # noqa: E402

if __name__ == "__main__":
    if "--check" in sys.argv:
        import mcp
        import keyshotmcp
        print("keyshot : imports ok")
        print("  keyshotmcp :", sys.modules["keyshotmcp"].__file__, keyshotmcp.__version__)
        print("  mcp        :", mcp.__file__)
        print("  libs       :", libs)
        print("  outils     :", len(keyshotmcp.mcp._tool_manager.list_tools()))
    else:
        main()
