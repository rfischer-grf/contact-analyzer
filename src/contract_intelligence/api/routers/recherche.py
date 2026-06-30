"""Recherche (#52) : facette (SQL) vs sémantique (vectoriel).

Garde-fou (§6) : la recherche par **facette extraite** (« contrats à clause
Syntec », « échéances Q3 ») est du SQL `WHERE` sur Postgres — PAS du vectoriel.
Le vectoriel (Weaviate) sert uniquement au sémantique sur le corps des clauses et
au RAG. Le `tenant` provient TOUJOURS du principal (token), jamais du client (§7).

Le vector store et l'embeddeur sont injectés par dépendances surchargeables en
test (`get_vector_store` / `get_embeddeur`). Le défaut suit la configuration :
Weaviate (multi-tenancy natif) + embeddeur HTTP si renseignés (CI_WEAVIATE_URL /
CI_EMBEDDINGS_BASE_URL), sinon repli sur les implémentations Fake en mémoire.
"""

from __future__ import annotations

from datetime import date
from functools import lru_cache

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, sessionmaker

from ...config import get_settings
from ...db import tenant_session
from ...rag import (
    Embeddeur,
    VectorStore,
    embeddeur_par_defaut,
    recherche_facette,
    recherche_semantique,
    store_par_defaut,
)
from ..auth import Principal, get_principal
from ..deps import get_session_factory

router = APIRouter(prefix="/recherche", tags=["recherche"])


@lru_cache
def get_vector_store() -> VectorStore:
    """Vector store partagé : Weaviate si `CI_WEAVIATE_URL`, sinon Fake. Surchargé en test."""
    return store_par_defaut(get_settings())


@lru_cache
def get_embeddeur() -> Embeddeur:
    """Embeddeur BYO partagé : HTTP si `CI_EMBEDDINGS_BASE_URL`, sinon Fake. Surchargé en test."""
    return embeddeur_par_defaut(get_settings())


@router.get("/facette")
def facette(
    principal: Principal = Depends(get_principal),
    factory: sessionmaker[Session] = Depends(get_session_factory),
    indice: str | None = Query(default=None),
    echeance_avant: date | None = Query(default=None),
    fournisseur_siren: str | None = Query(default=None),
) -> list[dict[str, object]]:
    """Recherche structurée par facette (SQL Postgres, tenant via RLS) (#52)."""
    with tenant_session(factory, principal.tenant) as session:
        contrats = recherche_facette(
            session,
            principal.tenant,
            indice=indice,
            echeance_avant=echeance_avant,
            fournisseur_siren=fournisseur_siren,
        )
        return [
            {
                "id": str(c.id),
                "reference": c.reference,
                "objet": c.objet,
                "fournisseur_siren": c.fournisseur_siren,
                "indice": c.indice,
                "date_echeance": c.date_echeance.isoformat() if c.date_echeance else None,
            }
            for c in contrats
        ]


@router.get("/semantique")
def semantique(
    q: str = Query(..., description="Requête en langage naturel"),
    k: int = Query(default=5, ge=1, le=50),
    principal: Principal = Depends(get_principal),
    store: VectorStore = Depends(get_vector_store),
    embeddeur: Embeddeur = Depends(get_embeddeur),
) -> list[dict[str, object]]:
    """Recherche sémantique / RAG (vectoriel, tenant injecté côté API) (#52)."""
    chunks = recherche_semantique(store, embeddeur, principal.tenant, q, k=k)
    return [
        {
            "contrat_id": chunk.contrat_id,
            "type_clause": chunk.type_clause,
            "texte": chunk.texte,
            "metadata": chunk.metadata,
        }
        for chunk in chunks
    ]
