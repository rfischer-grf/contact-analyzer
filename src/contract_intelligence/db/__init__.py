"""Couche persistance (PostgreSQL = source de vérité unique, spec §5).

RLS multi-tenant dès le dev ; `document` (pièce) vs `contrat` (état effectif) ;
piste d'audit append-only ; séries d'indices.
"""

from .base import Base
from .models import Contrat, Correction, Document, EvenementAudit, FeedToken, SerieIndice
from .repository import committer
from .session import make_engine, make_sessionmaker, tenant_session

__all__ = [
    "Base",
    "Document",
    "Contrat",
    "Correction",
    "EvenementAudit",
    "SerieIndice",
    "FeedToken",
    "committer",
    "make_engine",
    "make_sessionmaker",
    "tenant_session",
]
