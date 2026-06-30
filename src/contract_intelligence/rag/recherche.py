"""Recherche : facette (SQL) vs sémantique (vectoriel) (#52, spec §6).

Garde-fou (§6) :
- La recherche par **facette extraite** (« contrats à clause Syntec »,
  « échéances Q3 ») est du **SQL `WHERE` sur Postgres/Contrat** — JAMAIS du
  vectoriel.
- Le **vectoriel** (Weaviate) sert UNIQUEMENT au sémantique sur le corps des
  clauses et au RAG.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.models import Contrat
from .embeddings import Embeddeur
from .store import Chunk, VectorStore


def recherche_facette(
    session: Session,
    tenant: str,
    *,
    indice: str | None = None,
    echeance_avant: date | None = None,
    fournisseur_siren: str | None = None,
) -> list[Contrat]:
    """Recherche structurée par facette = SQL `WHERE` (PAS de vectoriel).

    Filtre les contrats du `tenant` (la RLS borne déjà côté Postgres ; on filtre
    aussi explicitement par sécurité en SQLite/test). Les facettes non fournies
    sont ignorées.
    """
    stmt = select(Contrat).where(Contrat.tenant == tenant)
    if indice is not None:
        stmt = stmt.where(Contrat.indice == indice)
    if echeance_avant is not None:
        stmt = stmt.where(Contrat.date_echeance <= echeance_avant)
    if fournisseur_siren is not None:
        stmt = stmt.where(Contrat.fournisseur_siren == fournisseur_siren)
    return list(session.execute(stmt).scalars().all())


def recherche_semantique(
    store: VectorStore,
    embeddeur: Embeddeur,
    tenant: str,
    requete: str,
    k: int = 5,
) -> list[Chunk]:
    """Recherche sémantique = vectoriel sur le corps des clauses (Weaviate).

    La requête est vectorisée (embeddings BYO) puis confrontée au store, borné au
    `tenant` (injecté côté API, jamais fourni par le client — la RLS Postgres ne
    protège pas le vector store, spec §6).
    """
    vecteur = embeddeur.vectoriser([requete])[0]
    return store.rechercher(tenant, vecteur, k=k)
