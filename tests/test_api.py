"""Tests du squelette API (auth tenant, /health, presign)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from contract_intelligence.api.app import app
from contract_intelligence.api.auth import Principal, get_principal
from contract_intelligence.config import Settings, get_settings


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_health_sans_auth(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_presign_exige_authentification(client: TestClient) -> None:
    resp = client.post("/uploads/presign", json={"sha256": "a" * 64})
    assert resp.status_code == 401


def test_presign_derive_la_cle_du_tenant() -> None:
    # Le tenant vient du token (principal injecté), jamais du corps de requête.
    app.dependency_overrides[get_principal] = lambda: Principal(
        sujet="u1", tenant="acme", claims={}
    )
    app.dependency_overrides[get_settings] = lambda: Settings(
        s3_access_key="test", s3_secret_key="test", s3_bucket="contrats"
    )
    try:
        with TestClient(app) as c:
            sha = "b" * 64
            resp = c.post("/uploads/presign", json={"sha256": sha})
        assert resp.status_code == 200
        body = resp.json()
        assert body["cle"] == f"acme/{sha}"
        assert body["bucket"] == "contrats"
        assert body["url"].startswith("http")
    finally:
        app.dependency_overrides.clear()
