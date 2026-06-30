"""Recherche (#52).

Garde-fou (§6) : la recherche par **facette extraite** (« contrats à clause Syntec »,
« échéances Q3 ») est du SQL `WHERE` sur Postgres — PAS du vectoriel. Le vectoriel
(Weaviate) sert uniquement au sémantique sur le corps des clauses et au RAG.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from ..auth import Principal, get_principal

router = APIRouter(prefix="/recherche", tags=["recherche"])


@router.get("/facette")
def recherche_facette(principal: Principal = Depends(get_principal)) -> dict[str, str]:
    """Recherche structurée (SQL Postgres, filtrée par tenant via RLS) (#52)."""
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, detail="À implémenter (#52)")


@router.get("/semantique")
def recherche_semantique(principal: Principal = Depends(get_principal)) -> dict[str, str]:
    """Recherche sémantique / RAG (Weaviate, tenant injecté côté API) (#52)."""
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, detail="À implémenter (#52)")
