"""Fabrique de l'application FastAPI."""

from __future__ import annotations

from fastapi import FastAPI

from ..config import get_settings
from .routers import (
    contrats,
    health,
    hitl,
    ics,
    recherche,
    statut,
    tableau_de_bord,
    uploads,
)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        summary="Plateforme souveraine de gestion intelligente des contrats fournisseurs.",
    )
    app.include_router(health.router)
    app.include_router(uploads.router)
    app.include_router(contrats.router)
    app.include_router(tableau_de_bord.router)
    app.include_router(hitl.router)
    app.include_router(recherche.router)
    app.include_router(statut.router)
    app.include_router(ics.router)
    return app


app = create_app()
