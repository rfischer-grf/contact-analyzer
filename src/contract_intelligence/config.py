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
    # Origines autorisées pour le front (CORS) — SPA Vite en dev.
    cors_origins: list[str] = ["http://localhost:5173"]

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
    # Endpoint INTERNE : utilisé côté serveur (HEAD au confirm). En conteneur =
    # http://garage:3900 ; sur l'hôte = http://localhost:3900.
    s3_endpoint_url: str = "http://localhost:3900"
    # Endpoint PUBLIC (vu par le NAVIGATEUR) pour signer les URLs présignées : le
    # navigateur ne résout pas `garage`, il faut un hôte publié. L'hôte fait partie
    # de la signature SigV4 → on signe donc l'URL avec l'endpoint que le navigateur
    # utilisera. None → retombe sur s3_endpoint_url (dev sur l'hôte = déjà localhost).
    s3_public_endpoint_url: str | None = None
    s3_region: str = "garage"
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_bucket: str = "contrats"
    presign_ttl_seconds: int = 900  # PUT présigné de courte durée

    @property
    def s3_presign_endpoint(self) -> str:
        """Endpoint utilisé pour signer les URLs présignées (public si défini)."""
        return self.s3_public_endpoint_url or self.s3_endpoint_url

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
