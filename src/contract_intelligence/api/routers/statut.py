"""Statut d'ingestion (#22) — relaie la Query Temporal `statut` au front.

Le lecteur de statut est injecté (dépendance) : l'implémentation par défaut
interroge Temporal (import différé pour ne pas coupler l'API à `temporalio`) ;
les tests fournissent un double.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import APIRouter, Depends, HTTPException, status

from ..auth import Principal, get_principal

router = APIRouter(prefix="/statut", tags=["statut"])

StatutReader = Callable[[str], Awaitable[str]]


async def _reader_temporal(workflow_id: str) -> str:
    from temporalio.client import Client

    from ...config import get_settings
    from ...worker.workflows import IngestionWorkflow

    settings = get_settings()
    client = await Client.connect(settings.temporal_target, namespace=settings.temporal_namespace)
    handle = client.get_workflow_handle(workflow_id)
    return await handle.query(IngestionWorkflow.statut)


def get_statut_reader() -> StatutReader:
    return _reader_temporal


@router.get("/{workflow_id}")
async def statut(
    workflow_id: str,
    principal: Principal = Depends(get_principal),
    reader: StatutReader = Depends(get_statut_reader),
) -> dict[str, str]:
    try:
        etat = await reader(workflow_id)
    except Exception as exc:  # noqa: BLE001 - remonté en 404 explicite
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="Workflow inconnu ou injoignable"
        ) from exc
    return {"workflow_id": workflow_id, "statut": etat}
