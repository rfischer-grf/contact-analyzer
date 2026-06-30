"""Statut d'ingestion (#22) — relaie la Query Temporal `statut` au front."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from ..auth import Principal, get_principal

router = APIRouter(prefix="/statut", tags=["statut"])


@router.get("/{workflow_id}")
def statut(workflow_id: str, principal: Principal = Depends(get_principal)) -> dict[str, str]:
    """Lecture seule de l'avancement de la saga (polling/SSE côté front) (#22)."""
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, detail="À implémenter (#22)")
