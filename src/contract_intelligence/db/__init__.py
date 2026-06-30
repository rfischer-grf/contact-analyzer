"""Couche persistance (PostgreSQL = source de vérité unique, spec §5).

RLS multi-tenant dès le dev ; `document` (pièce) vs `contrat` (état effectif) ;
piste d'audit append-only ; séries d'indices.
"""

from .base import Base
from .models import Contrat, Document, EvenementAudit, SerieIndice
from .repository import committer
from .session import make_engine, make_sessionmaker, tenant_session

__all__ = [
    "Base",
    "Document",
    "Contrat",
    "EvenementAudit",
    "SerieIndice",
    "committer",
    "make_engine",
    "make_sessionmaker",
    "tenant_session",
]
