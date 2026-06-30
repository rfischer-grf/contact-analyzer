"""Feed ICS + abonnements (capability token) — spec §2.6.

Garde-fous : capability bearer (token long aléatoire, révocable/rotatable) ; le feed
ne contient que dates + intitulé (jamais le contenu des clauses) ; pas de `VALARM`.
Le feed lui-même n'utilise pas Keycloak : l'accès est porté par le token de capability.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session, sessionmaker

from ...alerting import creer_token, feed_pour_tenant, generer_ics, resoudre_token, roter
from ...db import FeedToken, tenant_session
from ..auth import Principal, get_principal
from ..deps import get_session_factory

router = APIRouter(prefix="/ics", tags=["ics"])


@router.post("/abonnement", status_code=status.HTTP_201_CREATED)
def creer_abonnement(
    principal: Principal = Depends(get_principal),
    factory: sessionmaker[Session] = Depends(get_session_factory),
) -> dict[str, str]:
    """Crée un abonnement ICS pour l'utilisateur courant ; renvoie l'URL capability."""
    with tenant_session(factory, principal.tenant) as session:
        token, ft = creer_token(session, principal.tenant, principal.sujet)
        token_id = str(ft.id)
    return {"id": token_id, "url": f"/ics/{token}.ics"}


@router.delete("/abonnement/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoquer_abonnement(
    token_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    factory: sessionmaker[Session] = Depends(get_session_factory),
) -> None:
    with tenant_session(factory, principal.tenant) as session:
        ft = session.get(FeedToken, token_id)
        if ft is None or ft.tenant != principal.tenant:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Abonnement introuvable")
        ft.revoque = True


@router.post("/abonnement/{token_id}/rotation")
def roter_abonnement(
    token_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    factory: sessionmaker[Session] = Depends(get_session_factory),
) -> dict[str, str]:
    with tenant_session(factory, principal.tenant) as session:
        ft = session.get(FeedToken, token_id)
        if ft is None or ft.tenant != principal.tenant:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Abonnement introuvable")
        nouveau = roter(session, token_id)
    return {"url": f"/ics/{nouveau}.ics"}


@router.get("/{token}.ics")
def feed_ics(
    token: str,
    factory: sessionmaker[Session] = Depends(get_session_factory),
) -> Response:
    with factory() as session:
        ft = resoudre_token(session, token)
        tenant = ft.tenant if ft is not None else None
    if tenant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Feed introuvable ou révoqué")
    with tenant_session(factory, tenant) as session:
        evenements = feed_pour_tenant(session, tenant)
    return Response(content=generer_ics(evenements), media_type="text/calendar")
