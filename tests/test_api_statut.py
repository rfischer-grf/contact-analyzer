"""Test de l'endpoint statut avec un lecteur injecté (sans Temporal)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from contract_intelligence.api.app import app
from contract_intelligence.api.auth import Principal, get_principal
from contract_intelligence.api.routers.statut import get_statut_reader


@pytest.fixture(autouse=True)
def _principal():
    app.dependency_overrides[get_principal] = lambda: Principal("alice", "acme", {})
    yield
    app.dependency_overrides.clear()


def test_statut_ok() -> None:
    async def reader(workflow_id: str) -> str:
        return "A_VALIDER"

    app.dependency_overrides[get_statut_reader] = lambda: reader
    with TestClient(app) as client:
        resp = client.get("/statut/wf-123")
    assert resp.status_code == 200
    assert resp.json() == {"workflow_id": "wf-123", "statut": "A_VALIDER"}


def test_statut_workflow_inconnu() -> None:
    async def reader(workflow_id: str) -> str:
        raise RuntimeError("not found")

    app.dependency_overrides[get_statut_reader] = lambda: reader
    with TestClient(app) as client:
        resp = client.get("/statut/wf-xxx")
    assert resp.status_code == 404
