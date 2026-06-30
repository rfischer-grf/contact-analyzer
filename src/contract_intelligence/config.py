"""Configuration centralisée (pydantic-settings).

Toutes les valeurs sont surchargeables par variables d'environnement préfixées
`CI_` (cf. `infra/.env.example`). Les secrets ne sont jamais commités.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CI_", env_file=".env", extra="ignore")

    # --- Application ---
    app_name: str = "Contract Intelligence (CLM souverain)"
    environment: str = "dev"

    # --- Base de données (PostgreSQL, source de vérité unique) ---
    database_url: str = "postgresql+psycopg://clm:clm@localhost:5432/clm"

    # --- Keycloak / OIDC ---
    oidc_issuer: str = "http://localhost:8080/realms/clm"
    oidc_jwks_url: str | None = None  # dérivé de l'issuer si absent
    oidc_audience: str = "clm-api"
    tenant_claim: str = "tenant"
    # Échappatoire de dev UNIQUEMENT : ne pas vérifier la signature du JWT.
    # NE JAMAIS activer en production. Le tenant reste lu dans le token.
    auth_dev_insecure: bool = False

    # --- Stockage S3 (Garage, jamais MinIO) ---
    s3_endpoint_url: str = "http://localhost:3900"
    s3_region: str = "garage"
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_bucket: str = "contrats"
    presign_ttl_seconds: int = 900  # PUT présigné de courte durée

    # --- Temporal ---
    temporal_target: str = "localhost:7233"
    temporal_namespace: str = "default"
    temporal_task_queue: str = "ingestion"

    @property
    def jwks_url(self) -> str:
        return self.oidc_jwks_url or f"{self.oidc_issuer}/protocol/openid-connect/certs"


@lru_cache
def get_settings() -> Settings:
    return Settings()
