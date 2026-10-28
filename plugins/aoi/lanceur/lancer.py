"""Lance un serveur MCP de l'atelier publié à part du plugin, depuis l'organisation de dossiers active.

    controle/runtime/python.exe lanceur/lancer.py cortexdb|revit

Entrée de .mcp.json. Le lanceur trouve le dossier du serveur (fiche <nom>-server-aoi.json et
skills/regen/scripts/chemins_aoi.py), pose ses variables, puis le lance avec les flux standard
hérités : Claude Code dialogue directement avec le serveur. Il ne migre rien (migrer_dossiers.py).

- Le serveur tourne dans un Job Object Windows (KILL_ON_JOB_CLOSE) : si Claude Code tue le
  lanceur, Windows arrête aussi le serveur. Sans lui, le serveur resterait orphelin, la base ouverte.
- Le lanceur n'écrit jamais sur la sortie standard (flux JSON-RPC). Ses messages vont sur
  stderr, que Claude Code garde dans son journal du serveur.
N'utilise que la bibliothèque standard.
"""
import json
import os
import signal
import subprocess
import sys
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN / "skills" / "regen" / "scripts"))
import chemins_aoi  # noqa: E402

FICHES = {"cortexdb": "cortexdb-server", "revit": "revit-server"}


def dire(message):
    print(f"lancer.py : {message}", file=sys.stderr, flush=True)


def job_tue_a_la_fermeture():
    """Job Object dont les processus s'arrêtent quand le dernier descripteur se ferme (fin du lanceur)."""
    import ctypes
    from ctypes import wintypes

    class Base(ctypes.Structure):
        _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                    ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                    ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                    ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD),
                    ("SchedulingClass", wintypes.DWORD)]

    class Etendue(ctypes.Structure):
        _fields_ = [("BasicLimitInformation", Base), ("IoInfo", ctypes.c_uint64 * 6),
                    ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                    ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]

    k = ctypes.WinDLL("kernel32", use_last_error=True)
    k.CreateJobObjectW.restype = wintypes.HANDLE
    k.OpenProcess.restype = wintypes.HANDLE  # sinon le descripteur 64 bits est tronqué en int
    job = k.CreateJobObjectW(None, None)
    info = Etendue()
    info.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    if not job or not k.SetInformationJobObject(job, 9, ctypes.byref(info), ctypes.sizeof(info)):
        return None, k
    return job, k


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in FICHES:
        dire(f"usage : lancer.py {'|'.join(FICHES)}")
        return 2
    serveur, nom = sys.argv[1], FICHES[sys.argv[1]]
    try:
        fiche = json.loads((PLUGIN / f"{nom}-aoi.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        dire(f"fiche {nom}-aoi.json illisible : {e}")
        return 1
    dossier = chemins_aoi.dossier_serveur(nom, fiche["version"])
    if dossier is None:
        dire(f"{nom} {fiche['version']} n'est pas installé sur ce poste : tapez /aoi:regen.")
        return 1
    env = dict(os.environ)
    if serveur == "cortexdb":
        base = chemins_aoi.base_cortexdb()
        if base is not None:
            env["CORTEXDB_PATH"] = str(base)
        commande = [str(dossier / fiche["exe"])]
    else:
        commande = [str(chemins_aoi.AOI / "node" / "node.exe"), str(dossier / fiche["exe"])]

    # Ctrl+C (console) : le serveur reçoit le signal lui aussi ; le lanceur attend qu'il s'arrête.
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    job, k = job_tue_a_la_fermeture()
    if job is None:
        dire("Job Object indisponible : le serveur pourrait survivre à la fermeture de Claude Code.")
    try:
        p = subprocess.Popen(commande, env=env)
    except OSError as e:
        dire(f"{commande[0]} : {e}")
        return 1
    if job is not None:
        # Seuls droits qu'exige AssignProcessToJobObject. PROCESS_ALL_ACCESS ressemble à une
        # injection pour l'antivirus (Bitdefender ATC, 28.10.2026).
        h = k.OpenProcess(0x0101, False, p.pid)  # PROCESS_SET_QUOTA | PROCESS_TERMINATE
        if not (h and k.AssignProcessToJobObject(job, h)):
            dire("serveur non rattaché au Job Object : il pourrait survivre à la fermeture de Claude Code.")
    return p.wait()


if __name__ == "__main__":
    sys.exit(main())
