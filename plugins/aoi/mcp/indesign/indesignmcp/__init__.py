"""Serveur MCP pour Adobe InDesign (plugin UXP)."""
__version__ = "0.1.0"

from indesignmcp.server import mcp, main  # noqa: E402,F401
from indesignmcp import outils  # noqa: E402,F401  (enregistre les outils)
