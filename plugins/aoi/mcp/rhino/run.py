r"""Lanceur du serveur rhino.

Lancé par le Python AOI de l'atelier (%LOCALAPPDATA%\aoi\python), avec `-I -S` :
les copies figées de ce dossier (server/ et libs/) passent avant tout autre paquet, et le
contrôle des imports, réservé aux scripts de Claude, n'est pas chargé.
`python -I -S run.py --check` vérifie les imports sans démarrer le serveur.
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

from rhinomcp.server import main  # noqa: E402

if __name__ == "__main__":
    if "--check" in sys.argv:
        import mcp
        print("rhino : imports ok")
        print("  rhinomcp :", sys.modules["rhinomcp"].__file__)
        print("  mcp      :", mcp.__file__)
    else:
        main()
