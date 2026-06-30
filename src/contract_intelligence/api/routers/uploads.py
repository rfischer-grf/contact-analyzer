"""Ingestion : URL présignée (#14) + confirmation d'upload (#16).

Garde-fous (§7) :
- Les octets ne transitent jamais par l'API → upload direct navigateur→S3 (PUT présigné).
- Le bucket/préfixe est **dérivé du token** (tenant), jamais fourni par le client.
- Clé canonique = SHA256 du fichier (dédoublonnage, idempotence).
"""

from __future__ import annotations

import boto3
from botocore.config import Config
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from ...config import Settings, get_settings
from ..auth import Principal, get_principal

router = APIRouter(prefix="/uploads", tags=["ingestion"])


class PresignRequest(BaseModel):
    sha256: str = Field(pattern=r"^[0-9a-fA-F]{64}$", description="SHA256 calculé côté client")
    content_type: str = "application/pdf"


class PresignResponse(BaseModel):
    url: str
    methode: str = "PUT"
    cle: str
    bucket: str
    expire_dans: int


def _objet_cle(tenant: str, sha256: str) -> str:
    """Préfixe dérivé du tenant + clé canonique SHA256 (spec §2.1)."""
    return f"{tenant}/{sha256.lower()}"


def _s3_client(settings: Settings, *, endpoint: str | None = None):  # type: ignore[no-untyped-def]
    # Path-style forcé : URLs `…/contrats/<clé>` déterministes (pas de vhost
    # `contrats.localhost` que le navigateur ne résoudrait pas).
    return boto3.client(
        "s3",
        endpoint_url=endpoint or settings.s3_endpoint_url,
        region_name=settings.s3_region,
        aws_access_key_id=settings.s3_access_key or None,
        aws_secret_access_key=settings.s3_secret_key or None,
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


@router.post("/presign", response_model=PresignResponse)
def presign(
    req: PresignRequest,
    principal: Principal = Depends(get_principal),
    settings: Settings = Depends(get_settings),
) -> PresignResponse:
    cle = _objet_cle(principal.tenant, req.sha256)
    # Signé avec l'endpoint PUBLIC : c'est l'hôte que le navigateur contactera (il
    # fait partie de la signature SigV4, donc pas de réécriture possible a posteriori).
    url = _s3_client(settings, endpoint=settings.s3_presign_endpoint).generate_presigned_url(
        "put_object",
        Params={"Bucket": settings.s3_bucket, "Key": cle, "ContentType": req.content_type},
        ExpiresIn=settings.presign_ttl_seconds,
    )
    return PresignResponse(
        url=url, cle=cle, bucket=settings.s3_bucket, expire_dans=settings.presign_ttl_seconds
    )


class ConfirmRequest(BaseModel):
    sha256: str = Field(pattern=r"^[0-9a-fA-F]{64}$")


class ConfirmResponse(BaseModel):
    cle: str
    etat: str
    workflow_id: str


def _workflow_id(tenant: str, sha256: str) -> str:
    """ID de saga = tenant + SHA256 (idempotent ; scopé tenant, sans `/` pour l'URL statut)."""
    return f"{tenant}:{sha256.lower()}"


async def _demarrer_ingestion(settings: Settings, tenant: str, sha256: str) -> str:
    """Démarre la saga Temporal (idempotent sur le workflow_id). Import différé pour
    ne pas coupler l'API à `temporalio` au chargement (cf. routers/statut.py)."""
    from temporalio.client import Client
    from temporalio.exceptions import WorkflowAlreadyStartedError

    from ...worker.workflows import IngestionWorkflow

    workflow_id = _workflow_id(tenant, sha256)
    client = await Client.connect(settings.temporal_target, namespace=settings.temporal_namespace)
    try:
        await client.start_workflow(
            IngestionWorkflow.run,
            sha256,
            id=workflow_id,
            task_queue=settings.temporal_task_queue,
        )
    except WorkflowAlreadyStartedError:
        pass  # ré-confirmation du même fichier : la saga tourne déjà.
    return workflow_id


@router.post("/confirm", status_code=status.HTTP_202_ACCEPTED, response_model=ConfirmResponse)
async def confirm(
    req: ConfirmRequest,
    principal: Principal = Depends(get_principal),
    settings: Settings = Depends(get_settings),
) -> ConfirmResponse:
    """HEAD l'objet (endpoint interne) puis démarre la saga Temporal, idempotent sur le SHA256."""
    cle = _objet_cle(principal.tenant, req.sha256)
    client = _s3_client(settings)
    try:
        client.head_object(Bucket=settings.s3_bucket, Key=cle)
    except Exception as exc:  # noqa: BLE001 - remonté en 404 explicite
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Objet introuvable : l'upload n'est pas confirmé",
        ) from exc
    workflow_id = await _demarrer_ingestion(settings, principal.tenant, req.sha256)
    return ConfirmResponse(cle=cle, etat="RECU", workflow_id=workflow_id)
