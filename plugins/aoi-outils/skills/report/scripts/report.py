"""Rapport des imports Python contrôlés par aoi-outils.

Usage : python report.py [--jours N]
Lit le journal %LOCALAPPDATA%\\aoi\\imports.jsonl et le compare à la liste blanche.
"""
import argparse
import collections
import datetime
import json
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

here = os.path.dirname(os.path.abspath(__file__))
whitelist_path = os.environ.get("AOI_IMPORT_WHITELIST") or os.path.join(os.path.dirname(here), "whitelist.txt")
log_path = os.environ.get("AOI_IMPORT_LOG") or os.path.join(
    os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "aoi", "imports.jsonl")

p = argparse.ArgumentParser()
p.add_argument("--jours", type=int, default=7, help="période couverte (défaut : 7 jours)")
p.add_argument("--mcp", default="", help="serveurs MCP chargés dans la session, séparés par des virgules")
args = p.parse_args()

if args.mcp:
    mcp_path = os.path.join(os.path.dirname(here), "mcp-whitelist.txt")
    try:
        with open(mcp_path, encoding="utf-8") as f:
            mcp_allowed = {l.split("#", 1)[0].strip() for l in f} - {""}
    except OSError:
        mcp_allowed = set()
        print(f"⚠ Liste blanche MCP introuvable : {mcp_path}")
    loaded = [m.strip() for m in args.mcp.split(",") if m.strip()]
    print("# Serveurs MCP chargés dans la session\n")
    print("| Serveur | Statut |")
    print("|---|---|")
    for m in loaded:
        ok = m in mcp_allowed or m.startswith("claude.ai ")
        statut = "autorisé" if m in mcp_allowed else (
            "connecteur claude.ai (géré par la console)" if ok else "**non identifié : à signaler à l'IT**")
        print(f"| `{m}` | {statut} |")
    missing = sorted(mcp_allowed - set(loaded))
    if missing:
        print(f"\nServeurs autorisés absents de la session : {', '.join(f'`{m}`' for m in missing)}")
    print()

whitelist = set()
try:
    with open(whitelist_path, encoding="utf-8") as f:
        whitelist = {l.split("#", 1)[0].strip() for l in f} - {""}
except OSError:
    print(f"⚠ Liste blanche introuvable : {whitelist_path}")

if not os.path.exists(log_path):
    print(f"Aucun import journalisé pour le moment ({log_path}).")
    print("Vérifier que le contrôle est actif : la variable PYTHONPATH doit contenir le dossier guard du plugin.")
    sys.exit(0)

since = datetime.datetime.now() - datetime.timedelta(days=args.jours)
stats = collections.defaultdict(lambda: {"n": 0, "dernier": "", "detail": "", "scripts": set()})
for line in open(log_path, encoding="utf-8"):
    try:
        e = json.loads(line)
        if datetime.datetime.fromisoformat(e["date"]) < since:
            continue
    except (ValueError, KeyError):
        continue
    s = stats[(e["decision"], e["librairie"])]
    s["n"] += 1
    s["dernier"] = max(s["dernier"], e["date"])
    s["detail"] = e.get("detail", "")
    s["scripts"].add(os.path.basename(e.get("script") or "") or "(commande)")

print(f"# Imports Python des {args.jours} derniers jours\n")
print(f"Journal : {log_path}")
print(f"Liste blanche : {whitelist_path} ({len(whitelist)} librairies)\n")
for decision, titre in (("refusé", "Refusés : librairies non identifiées"),
                        ("signalé", "Signalés en mode d'essai (non bloqués)"),
                        ("dépendance", "Acceptés comme dépendances"),
                        ("accepté", "Acceptés : liste blanche"),
                        ("local", "Modules locaux du projet")):
    rows = sorted((k[1], v) for k, v in stats.items() if k[0] == decision)
    if not rows:
        continue
    print(f"## {titre} ({len(rows)})\n")
    print("| Librairie | Imports | Dernier | Scripts | Détail |")
    print("|---|---|---|---|---|")
    for lib, v in rows:
        print(f"| `{lib}` | {v['n']} | {v['dernier']} | {', '.join(sorted(v['scripts']))[:60]} | {v['detail'][:70]} |")
    print()

unused = sorted(whitelist - {k[1] for k in stats})
if unused:
    print(f"## Liste blanche : librairies non utilisées sur la période ({len(unused)})\n")
    print(", ".join(f"`{u}`" for u in unused))
