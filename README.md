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
  domain/                     # modèles §3 (Champ/Provenance + entités) + état effectif (fold)
  db/                         # ORM (document/contrat/audit/séries), session tenant, committer()
  api/                        # FastAPI : auth OIDC (tenant), routers presign/hitl/…
  worker/                     # saga Temporal : états, workflows, activities
migrations/                   # Alembic : schéma initial + RLS multi-tenant + audit append-only
infra/                        # docker-compose (infra + app), Keycloak (realm), Garage (config + provisioning), .env
Dockerfile                    # image applicative de dev (API + worker + migrate)
Makefile                      # pilotage de la stack : make up / down / logs / ...
tests/                        # pytest (domaine, calculs, fold, committer, API, RLS)
```

## Démarrage rapide (tout-en-un)

Pré-requis : Docker (+ Compose) et `make`. **Une seule commande** lance toute la stack —
infra, migrations, API et worker — puis provisionne Garage :

```bash
make up        # infra + migrate + API + worker, puis provisioning Garage
make ps        # état des services
make logs      # logs API + worker
make health    # GET http://localhost:8000/health
make down      # tout arrêter (volumes conservés ; `make down-v` pour la RAZ)
make help      # toutes les cibles
```

L'API et le worker tournent dans des conteneurs (image `clm-app:dev`, cf. `Dockerfile`) ;
le code `src/` est monté en lecture seule → l'API recharge à chaud (`uvicorn --reload`).
Les services applicatifs sont sous le profil compose `app` : `docker compose up` sans
profil (ou `make up-infra`) ne lance que l'infra, pour développer l'app sur l'hôte.

## Développement sur l'hôte (alternative)

Pré-requis : Docker (+ Compose), Python 3.11, [`uv`](https://docs.astral.sh/uv/).

```bash
# 1) Infra seule (sans API/worker)
make up-infra        # ≡ cd infra && cp .env.example .env && docker compose up -d

# 2) Environnement Python + dépendances
uv venv --python 3.11 .venv
uv pip install -e ".[api,worker,db,dev]"

# 3) Migrations (PostgreSQL : schéma + RLS multi-tenant + audit append-only)
export CI_DATABASE_URL=postgresql+psycopg://clm:clm@localhost:5432/clm
.venv/bin/alembic upgrade head

# 4) Qualité (= CI)
.venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/mypy src && .venv/bin/pytest

# 5) Lancer l'API et le worker
.venv/bin/uvicorn contract_intelligence.api.app:app --reload   # http://localhost:8000/health
.venv/bin/python -m contract_intelligence.worker.bootstrap
```

> Tests : `pytest` exécute la suite hors-DB ; les tests RLS/migrations (marqueur
> `db`) tournent en CI avec un service PostgreSQL, ou en local via
> `CI_TEST_DATABASE_URL=… .venv/bin/pytest -m db`.

UIs de dev : Keycloak `:8080`, Temporal `:8233`, Mailpit `:8025`, garage-webui `:3909`,
Weaviate `:8081`. Utilisateurs Keycloak de test : `alice`/`alice` (tenant `acme`),
`bob`/`bob` (tenant `globex`).

> **Provisioning Garage** : `make up` l'exécute automatiquement (`make provision-garage` /
> `infra/provision-garage.sh`, idempotent) — layout mono-nœud, bucket `contrats` et clé
> d'accès S3 de dev **déterministe** (cf. `infra/.env.example`), autorisée en lecture/écriture.
> Pour un déploiement réel, générer la clé via `garage key create` et renseigner
> `CI_S3_ACCESS_KEY` / `CI_S3_SECRET_KEY` sans jamais la commiter.

## Statut

Spécification d'architecture posée comme source de vérité ; backlog décomposé en
**epics + tickets** (GitHub Issues). Socle livré : stack docker-compose, squelette API
(auth OIDC multi-tenant), modèles du domaine §3 + calcul de la date limite de
dénonciation, squelette de la saga Temporal, CI (ruff + mypy + pytest). Les services
métier suivent les tickets, dans le respect des garde-fous §7.
