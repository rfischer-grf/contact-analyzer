# Contract Intelligence (CLM souverain)

Plateforme souveraine (EU) de gestion intelligente des contrats fournisseurs.

Upload d'un contrat → extraction structurée par LLM (avec provenance page/bbox) →
**validation humaine (gate HITL)** → alertes d'échéance et de date limite de
dénonciation + projection tarifaire pour les contrats indexés (Syntec, ILAT, ILC,
ICC, INSEE). Pattern transverse : **qualification → résolution → traçabilité**.

## Architecture

La conception est documentée dans **[`docs/architecture.md`](docs/architecture.md)** —
source de vérité des décisions d'architecture. Le pipeline nominal :

```
upload (presigned)  →  contrôle + AV  →  Docling (parse/OCR)  →  extraction LLM
   →  rapprochement (avenant?)  →  [GATE HITL]  →  commit (état effectif)
   →  projection Weaviate  →  alertes (job quotidien) + feed ICS
```

## Stack (dev)

| Domaine            | Choix                                                        |
| ------------------ | ------------------------------------------------------------ |
| Source de vérité   | PostgreSQL (RLS multi-tenant)                                |
| Stockage S3        | Garage                                                       |
| Auth               | Keycloak (OIDC)                                              |
| Orchestration      | Temporal (saga d'ingestion)                                  |
| Parsing            | Docling (CPU, RapidOCR)                                      |
| Antivirus          | ClamAV                                                       |
| Extraction LLM     | Mistral Small 3.x (Scaleway Generative APIs ou vLLM local)   |
| Vector store / RAG | Weaviate (index dérivé)                                      |
| API                | FastAPI                                                      |
| Front              | React (Vite)                                                 |
| Mail (dev)         | Mailpit                                                      |

Voir `docs/architecture.md` §5 pour le détail et §7 pour les garde-fous explicites.

## Structure du dépôt

```
docs/architecture.md          # source de vérité des décisions d'architecture
src/contract_intelligence/
  config.py                   # settings (pydantic-settings, préfixe CI_)
  domain/                     # modèles §3 (Champ/Provenance + entités) + calculs
  api/                        # FastAPI : auth OIDC (tenant), routers presign/hitl/…
  worker/                     # saga Temporal : états, workflows, activities
infra/                        # docker-compose, Keycloak (realm), Garage (config), .env
tests/                        # pytest (domaine, calculs, API, états saga)
```

## Développement

Pré-requis : Docker (+ Compose), Python 3.11, [`uv`](https://docs.astral.sh/uv/).

```bash
# 1) Stack de dev
cd infra && cp .env.example .env && docker compose up -d

# 2) Environnement Python + dépendances
uv venv --python 3.11 .venv
uv pip install -e ".[api,worker,dev]"

# 3) Qualité (= CI)
.venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/mypy src && .venv/bin/pytest

# 4) Lancer l'API et le worker
.venv/bin/uvicorn contract_intelligence.api.app:app --reload   # http://localhost:8000/health
.venv/bin/python -m contract_intelligence.worker.bootstrap
```

UIs de dev : Keycloak `:8080`, Temporal `:8233`, Mailpit `:8025`, garage-webui `:3909`,
Weaviate `:8081`. Utilisateurs Keycloak de test : `alice`/`alice` (tenant `acme`),
`bob`/`bob` (tenant `globex`).

> **Provisioning Garage (#4)** : après le premier démarrage, créer le layout, le bucket
> et une clé d'accès (`garage layout assign…`, `garage bucket create contrats`,
> `garage key create`), puis renseigner `CI_S3_ACCESS_KEY` / `CI_S3_SECRET_KEY`.

## Statut

Spécification d'architecture posée comme source de vérité ; backlog décomposé en
**epics + tickets** (GitHub Issues). Socle livré : stack docker-compose, squelette API
(auth OIDC multi-tenant), modèles du domaine §3 + calcul de la date limite de
dénonciation, squelette de la saga Temporal, CI (ruff + mypy + pytest). Les services
métier suivent les tickets, dans le respect des garde-fous §7.
