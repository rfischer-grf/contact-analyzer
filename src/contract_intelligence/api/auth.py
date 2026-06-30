"""Authentification OIDC (Keycloak).

Invariant (§7) : le `tenant` est **dérivé du token**, jamais fourni par le client.
La validation de signature s'appuie sur le JWKS Keycloak ; un mode dev explicite
(`CI_AUTH_DEV_INSECURE=true`) permet de désactiver la vérification de signature
en local — à n'utiliser JAMAIS en production.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

import jwt
from fastapi import Depends, Header, HTTPException, status
from jwt import PyJWKClient

from ..config import Settings, get_settings


@dataclass(frozen=True)
class Principal:
    """Identité authentifiée résolue depuis l'access token."""

    sujet: str
    tenant: str
    claims: dict[str, Any] = field(default_factory=dict)


@lru_cache
def _jwks_client(url: str) -> PyJWKClient:
    return PyJWKClient(url)


def _decoder(token: str, settings: Settings) -> dict[str, Any]:
    if settings.auth_dev_insecure:
        return jwt.decode(
            token,
            options={"verify_signature": False, "verify_aud": False},
        )
    signing_key = _jwks_client(settings.jwks_url).get_signing_key_from_jwt(token)
    return jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256"],
        audience=settings.oidc_audience,
        issuer=settings.oidc_issuer,
    )


def get_principal(
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> Principal:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token bearer manquant"
        )
    token = authorization.split(" ", 1)[1].strip()
    try:
        claims = _decoder(token, settings)
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalide"
        ) from exc

    tenant = claims.get(settings.tenant_claim)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Claim tenant absent du token",
        )
    return Principal(sujet=str(claims.get("sub", "")), tenant=str(tenant), claims=claims)
