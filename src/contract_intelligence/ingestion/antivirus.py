"""Scan antivirus ClamAV via clamd (#18, spec §2.1, §4).

Client `INSTREAM` minimal écrit directement sur une socket TCP (`socket` stdlib),
sans dépendance tierce. On envoie le contenu déjà déposé sur S3 à clamd et on
interprète la réponse.

Garde-fou §4 — « AV positif ≠ retry » : on distingue deux familles d'échec.

- `AntivirusIndisponible` (erreur d'INFRA : socket injoignable, réponse illisible,
  protocole inattendu) → **retryable** : clamd peut redémarrer, on retentera.
- `MalwareDetecte` (clamd a répondu ``FOUND``) → **décision métier TERMINALE** :
  le fichier est malveillant, on bascule en `REJETE_TECHNIQUE`, jamais de retry.

Protocole clamd `INSTREAM` (mode « z », commandes terminées par NUL) :

    zINSTREAM\0
    <taille big-endian uint32><données>   (répété par chunk)
    \x00\x00\x00\x00                        (chunk de taille 0 = fin du flux)

Réponse : ``stream: OK\0`` si sain, ``stream: <Signature> FOUND\0`` sinon,
``... ERROR\0`` en cas d'erreur côté clamd.
"""

from __future__ import annotations

import socket
import struct

from ..config import get_settings

#: Taille des chunks envoyés à clamd (octets). Borne aussi `StreamMaxLength`.
TAILLE_CHUNK: int = 64 * 1024
#: Délai max sur les opérations socket (connexion + I/O), en secondes.
DELAI_SOCKET: float = 30.0


class AntivirusIndisponible(Exception):
    """clamd injoignable ou réponse illisible — erreur d'infra, RETRYABLE (§4)."""


class MalwareDetecte(Exception):
    """clamd a détecté une signature (``FOUND``) — décision métier TERMINALE (§4).

    Porte la signature retournée par clamd pour la traçabilité (audit, §2.1).
    """

    def __init__(self, signature: str) -> None:
        self.signature = signature
        super().__init__(f"Malware détecté par ClamAV : {signature}")


def analyser(octets: bytes, hote: str | None = None, port: int | None = None) -> None:
    """Scanne `octets` via clamd `INSTREAM`. Retourne `None` si le contenu est sain.

    `hote`/`port` par défaut = `get_settings().clamav_host` / `clamav_port`.

    - Contenu sain (``stream: OK``)              → retourne `None`.
    - Signature détectée (``... FOUND``)         → lève `MalwareDetecte` (terminal).
    - Toute erreur socket/protocole (y compris   → lève `AntivirusIndisponible`
      ``ERROR`` renvoyé par clamd)                  (retryable).
    """
    if hote is None or port is None:
        settings = get_settings()
        hote = hote if hote is not None else settings.clamav_host
        port = port if port is not None else settings.clamav_port

    try:
        with socket.create_connection((hote, port), timeout=DELAI_SOCKET) as sock:
            sock.settimeout(DELAI_SOCKET)
            sock.sendall(b"zINSTREAM\0")
            for debut in range(0, len(octets), TAILLE_CHUNK):
                bloc = octets[debut : debut + TAILLE_CHUNK]
                sock.sendall(struct.pack("!I", len(bloc)) + bloc)
            # Chunk de taille 0 = fin du flux.
            sock.sendall(struct.pack("!I", 0))
            reponse = _lire_reponse(sock)
    except (OSError, struct.error) as exc:
        raise AntivirusIndisponible(f"clamd injoignable ({hote}:{port}) : {exc}") from exc

    _interpreter(reponse)


def _lire_reponse(sock: socket.socket) -> str:
    """Lit la réponse clamd jusqu'au terminateur NUL (ou fermeture) et la décode."""
    morceaux: list[bytes] = []
    while True:
        donnee = sock.recv(4096)
        if not donnee:
            break
        morceaux.append(donnee)
        if donnee.endswith(b"\0"):
            break
    return b"".join(morceaux).rstrip(b"\0").decode("utf-8", "replace").strip()


def _interpreter(reponse: str) -> None:
    """Traduit la réponse clamd en retour normal / exception (§4)."""
    if not reponse:
        raise AntivirusIndisponible("Réponse clamd vide")
    if reponse.endswith("FOUND"):
        # Format : « stream: <Signature> FOUND ».
        corps = reponse[: -len("FOUND")].strip()
        _, _, signature = corps.partition(":")
        raise MalwareDetecte(signature.strip() or corps)
    if reponse.endswith("OK"):
        return
    # « ... ERROR » ou tout autre verdict inattendu = problème d'infra/protocole.
    raise AntivirusIndisponible(f"Réponse clamd inattendue : {reponse!r}")
