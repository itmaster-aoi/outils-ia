"""WebSocket minimal (RFC 6455), bibliothèque standard seule.

Sert au serveur (le plugin UXP se connecte) et aux tests (faux plugin client).
Pas d'extension (permessage-deflate) ni de sous-protocole.
"""
import base64
import hashlib
import os
import struct
from typing import Dict, Tuple

GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
SUITE, TEXTE, BINAIRE, FERMER, PING, PONG = 0, 1, 2, 8, 9, 10
MESSAGE_MAX = 64 * 1024 * 1024
ENTETES_MAX = 16 * 1024


class ErreurWS(Exception):
    """Poignée de main ou trame invalide."""


def lire_exact(sock, n: int) -> bytes:
    tampon = bytearray()
    while len(tampon) < n:
        bloc = sock.recv(min(1 << 20, n - len(tampon)))
        if not bloc:
            raise ConnectionResetError("connexion fermée (%d/%d octets)" % (len(tampon), n))
        tampon += bloc
    return bytes(tampon)


def lire_entetes(sock) -> Tuple[str, Dict[str, str]]:
    """Lit une requête ou une réponse HTTP jusqu'à la ligne vide. Rend (première ligne, en-têtes en minuscules)."""
    tampon = bytearray()
    while b"\r\n\r\n" not in tampon:
        bloc = sock.recv(1)
        if not bloc:
            raise ConnectionResetError("connexion fermée pendant la poignée de main")
        tampon += bloc
        if len(tampon) > ENTETES_MAX:
            raise ErreurWS("en-têtes trop longs")
    lignes = tampon.decode("latin-1").split("\r\n")
    entetes = {}
    for ligne in lignes[1:]:
        if ":" in ligne:
            cle, valeur = ligne.split(":", 1)
            entetes[cle.strip().lower()] = valeur.strip()
    return lignes[0], entetes


def cle_acceptation(cle: str) -> str:
    return base64.b64encode(hashlib.sha1((cle + GUID).encode("ascii")).digest()).decode("ascii")


def poignee_serveur(sock) -> Dict[str, str]:
    """Accepte la poignée de main d'un client. Refuse les navigateurs (Origin http/https)."""
    ligne, entetes = lire_entetes(sock)
    origine = entetes.get("origin", "").lower()
    if not ligne.startswith("GET ") or entetes.get("upgrade", "").lower() != "websocket" \
            or "sec-websocket-key" not in entetes:
        sock.sendall(b"HTTP/1.1 400 Bad Request\r\nContent-Length: 0\r\n\r\n")
        raise ErreurWS("requête non WebSocket : %r" % ligne)
    if origine.startswith(("http://", "https://")):
        sock.sendall(b"HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\n\r\n")
        raise ErreurWS("origine refusée : %s" % origine)
    sock.sendall(("HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                  "Sec-WebSocket-Accept: %s\r\n\r\n" % cle_acceptation(entetes["sec-websocket-key"]))
                 .encode("ascii"))
    return entetes


def poignee_client(sock, hote: str, port: int, origine: str = "") -> None:
    """Poignée de main côté client (tests)."""
    cle = base64.b64encode(os.urandom(16)).decode("ascii")
    requete = ("GET / HTTP/1.1\r\nHost: %s:%d\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
               "Sec-WebSocket-Key: %s\r\nSec-WebSocket-Version: 13\r\n" % (hote, port, cle))
    if origine:
        requete += "Origin: %s\r\n" % origine
    sock.sendall((requete + "\r\n").encode("ascii"))
    ligne, entetes = lire_entetes(sock)
    if " 101 " not in ligne + " " or entetes.get("sec-websocket-accept") != cle_acceptation(cle):
        raise ErreurWS("poignée de main refusée : %s" % ligne)


def trame(donnees: bytes, opcode: int = TEXTE, masque: bool = False) -> bytes:
    """Une trame finale. Le client masque (masque=True), le serveur non."""
    entete = bytearray([0x80 | opcode])
    bit = 0x80 if masque else 0
    n = len(donnees)
    if n < 126:
        entete.append(bit | n)
    elif n < 1 << 16:
        entete.append(bit | 126)
        entete += struct.pack(">H", n)
    else:
        entete.append(bit | 127)
        entete += struct.pack(">Q", n)
    if masque:
        cle = os.urandom(4)
        entete += cle
        donnees = bytes(b ^ cle[i % 4] for i, b in enumerate(donnees))
    return bytes(entete) + donnees


def _lire_trame(sock) -> Tuple[bool, int, bytes]:
    b0, b1 = lire_exact(sock, 2)
    fin, opcode, masque, n = bool(b0 & 0x80), b0 & 0x0F, bool(b1 & 0x80), b1 & 0x7F
    if n == 126:
        n = struct.unpack(">H", lire_exact(sock, 2))[0]
    elif n == 127:
        n = struct.unpack(">Q", lire_exact(sock, 8))[0]
    if n > MESSAGE_MAX:
        raise ErreurWS("trame trop longue (%d octets)" % n)
    cle = lire_exact(sock, 4) if masque else b""
    donnees = lire_exact(sock, n)
    if masque:
        donnees = bytes(b ^ cle[i % 4] for i, b in enumerate(donnees))
    return fin, opcode, donnees


def lire_message(sock, envoyer=None) -> Tuple[int, bytes]:
    """Lit un message complet (fragments réunis). Répond aux PING si `envoyer` est fourni.
    Rend (TEXTE | BINAIRE | FERMER, données)."""
    morceaux, type_message = bytearray(), None
    while True:
        fin, opcode, donnees = _lire_trame(sock)
        if opcode == PING:
            if envoyer:
                envoyer(donnees, PONG)
            continue
        if opcode == PONG:
            continue
        if opcode == FERMER:
            return FERMER, donnees
        if opcode != SUITE:
            type_message = opcode
        morceaux += donnees
        if len(morceaux) > MESSAGE_MAX:
            raise ErreurWS("message trop long")
        if fin:
            return type_message or TEXTE, bytes(morceaux)
