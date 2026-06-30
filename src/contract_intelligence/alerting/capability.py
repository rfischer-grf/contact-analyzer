"""Capability token du feed ICS (spec §2.6) : long aléatoire, révocable/rotatable.

On stocke uniquement le SHA256 du token ; la résolution se fait par hash.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.models import FeedToken


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def creer_token(session: Session, tenant: str, sujet: str) -> tuple[str, FeedToken]:
    """Génère un token (renvoyé en clair une seule fois) et persiste son hash."""
    token = secrets.token_urlsafe(32)
    ft = FeedToken(tenant=tenant, sujet=sujet, token_hash=_hash(token))
    session.add(ft)
    session.flush()
    return token, ft


def resoudre_token(session: Session, token: str) -> FeedToken | None:
    """Retourne le FeedToken actif correspondant, ou None (inconnu/révoqué)."""
    ft = session.execute(
        select(FeedToken).where(FeedToken.token_hash == _hash(token))
    ).scalar_one_or_none()
    if ft is None or ft.revoque:
        return None
    return ft


def revoquer(session: Session, token_id: uuid.UUID) -> bool:
    ft = session.get(FeedToken, token_id)
    if ft is None:
        return False
    ft.revoque = True
    session.flush()
    return True


def roter(session: Session, token_id: uuid.UUID) -> str | None:
    """Révoque l'ancien token et en émet un nouveau (même tenant/sujet)."""
    ft = session.get(FeedToken, token_id)
    if ft is None:
        return None
    ft.revoque = True
    nouveau, _ = creer_token(session, ft.tenant, ft.sujet)
    return nouveau
