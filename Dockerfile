# Image applicative de DEV — l'API FastAPI et le worker Temporal partagent la même
# image ; c'est la commande du service compose qui choisit l'entrypoint
# (uvicorn / worker.bootstrap / alembic). Cf. docs/architecture.md §5.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# 1) Dépendances d'abord (couche mise en cache tant que les métadonnées ne changent pas).
#    `pip install -e` a besoin du paquet présent → on copie aussi src.
COPY pyproject.toml ./
COPY src ./src
RUN pip install -e ".[api,worker,db]"

# 2) Migrations + config Alembic (changent plus souvent que les dépendances).
COPY alembic.ini ./
COPY migrations ./migrations

# Défaut = API. Surchargé par `command:` pour le worker et le one-shot migrate.
EXPOSE 8000
CMD ["uvicorn", "contract_intelligence.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
