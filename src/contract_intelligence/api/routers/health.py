"""Endpoint de santé (non authentifié)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ...config import Settings, get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health(settings: Settings = Depends(get_settings)) -> dict[str, str]:
    return {
        "status": "ok",
        "app": settings.app_name,
        "environment": settings.environment,
    }
