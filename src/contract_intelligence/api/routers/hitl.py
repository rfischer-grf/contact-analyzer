"""Validation humaine (HITL) — file de revue (#35) et signaux valider/rejeter (#36).

Squelette : les endpoints sont câblés (auth + tenant) mais l'implémentation
(file de revue, corrections, émission du signal Temporal) relève des tickets dédiés.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from ..auth import Principal, get_principal

router = APIRouter(prefix="/hitl", tags=["hitl"])


@router.get("/file")
def file_de_revue(principal: Principal = Depends(get_principal)) -> dict[str, str]:
    """Liste les contrats `A_VALIDER` du tenant et leurs champs sous le seuil (#35)."""
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, detail="À implémenter (#35)")


@router.post("/contrats/{contrat_id}/valider")
def valider(contrat_id: str, principal: Principal = Depends(get_principal)) -> dict[str, str]:
    """Émet le signal `valider` au workflow en attente → VALIDE→COMMITE (#36)."""
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, detail="À implémenter (#36)")


@router.post("/contrats/{contrat_id}/rejeter")
def rejeter(contrat_id: str, principal: Principal = Depends(get_principal)) -> dict[str, str]:
    """Émet le signal `rejeter` au workflow en attente → REJETE_METIER (#36)."""
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, detail="À implémenter (#36)")
