"""Serveur MCP pour Adobe Photoshop (plugin UXP)."""
__version__ = "0.1.0"

from photoshopmcp.server import mcp, main  # noqa: E402,F401
from photoshopmcp import outils  # noqa: E402,F401  (enregistre les outils)
