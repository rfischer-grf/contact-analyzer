"""Tests du client antivirus clamd INSTREAM (#18, spec §2.1, §4).

On remplace la socket par un faux objet (aucun clamd réel requis). Le faux gère le
protocole côté serveur a minima : il accumule ce qu'on lui envoie et renvoie une
réponse fixée par le test (``stream: OK\\0``, ``... FOUND\\0``), ou lève `OSError`
pour simuler une panne d'infra.
"""

from __future__ import annotations

import socket

import pytest

from contract_intelligence.ingestion import antivirus
from contract_intelligence.ingestion.antivirus import (
    AntivirusIndisponible,
    MalwareDetecte,
    analyser,
)


class _FausseSocket:
    """Faux socket clamd : capture les octets envoyés, rejoue une réponse figée."""

    def __init__(self, reponse: bytes) -> None:
        self._reponse = reponse
        self._lu = False
        self.recu = bytearray()

    # Protocole de gestionnaire de contexte (with socket.create_connection(...) as s).
    def __enter__(self) -> _FausseSocket:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def settimeout(self, _delai: float | None) -> None:
        return None

    def sendall(self, donnee: bytes) -> None:
        self.recu.extend(donnee)

    def recv(self, _taille: int) -> bytes:
        if self._lu:
            return b""
        self._lu = True
        return self._reponse


def _brancher(monkeypatch: pytest.MonkeyPatch, fausse: _FausseSocket) -> None:
    """Injecte la fausse socket à la place de la vraie connexion clamd."""

    def _fabrique(*_args: object, **_kwargs: object) -> _FausseSocket:
        return fausse

    # `analyser()` ouvre la socket via `socket.create_connection`.
    monkeypatch.setattr(socket, "create_connection", _fabrique)


def test_contenu_sain_ne_leve_pas(monkeypatch: pytest.MonkeyPatch):
    fausse = _FausseSocket(b"stream: OK\0")
    _brancher(monkeypatch, fausse)

    assert analyser(b"contenu sain") is None
    # Le protocole INSTREAM a bien été amorcé.
    assert bytes(fausse.recu).startswith(b"zINSTREAM\0")
    # Et le flux est terminé par un chunk de taille 0.
    assert bytes(fausse.recu).endswith(b"\x00\x00\x00\x00")


def test_malware_detecte_leve_malware_detecte(monkeypatch: pytest.MonkeyPatch):
    fausse = _FausseSocket(b"stream: Eicar-Test-Signature FOUND\0")
    _brancher(monkeypatch, fausse)

    with pytest.raises(MalwareDetecte) as info:
        analyser(b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR")
    # La signature est portée par l'exception (traçabilité §2.1).
    assert info.value.signature == "Eicar-Test-Signature"


def test_socket_en_erreur_leve_antivirus_indisponible(monkeypatch: pytest.MonkeyPatch):
    def _explose(*_args: object, **_kwargs: object) -> _FausseSocket:
        raise OSError("connexion refusée")

    monkeypatch.setattr(socket, "create_connection", _explose)

    with pytest.raises(AntivirusIndisponible):
        analyser(b"peu importe")


def test_erreur_clamd_leve_antivirus_indisponible(monkeypatch: pytest.MonkeyPatch):
    # Une réponse « ERROR » de clamd = problème d'infra/protocole, retryable.
    fausse = _FausseSocket(b"INSTREAM size limit exceeded ERROR\0")
    _brancher(monkeypatch, fausse)

    with pytest.raises(AntivirusIndisponible):
        analyser(b"peu importe")


def test_defaut_host_port_depuis_settings(monkeypatch: pytest.MonkeyPatch):
    # Sans host/port explicites, on retombe sur get_settings() — capturé ici.
    captures: dict[str, object] = {}

    def _fabrique(adresse: tuple[str, int], *_args: object, **_kwargs: object) -> _FausseSocket:
        captures["adresse"] = adresse
        return _FausseSocket(b"stream: OK\0")

    monkeypatch.setattr(socket, "create_connection", _fabrique)

    from contract_intelligence.config import get_settings

    settings = get_settings()
    analyser(b"sain")
    assert captures["adresse"] == (settings.clamav_host, settings.clamav_port)


def test_module_expose_constantes():
    # Garde-fou : chunking et délai sont bien définis (pas de magie cachée).
    assert antivirus.TAILLE_CHUNK > 0
    assert antivirus.DELAI_SOCKET > 0
