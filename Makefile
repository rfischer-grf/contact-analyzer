# Makefile — pilotage de la stack de DEV (Contract Intelligence / CLM souverain).
# Tout passe par docker-compose : infra + migrate + API + worker. Cf. docs/architecture.md §5.
#
#   make up      → lance TOUTE la stack (infra + migrations + API + worker)
#   make down    → arrête tout
#   make logs    → suit les logs de l'API et du worker
#   make help    → liste les cibles

COMPOSE_FILE := infra/docker-compose.yml
ENV_FILE     := infra/.env
COMPOSE      := docker compose -f $(COMPOSE_FILE) --env-file $(ENV_FILE)
# Inclut les services applicatifs (migrate/api/worker), derrière le profil `app`.
COMPOSE_APP  := $(COMPOSE) --profile app

.DEFAULT_GOAL := help
.PHONY: help env up up-infra build down down-v restart ps logs logs-all \
        migrate provision-garage health shell-api shell-db psql lint test clean urls

help: ## Affiche cette aide
	@grep -hE '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

env: $(ENV_FILE) ## Crée infra/.env depuis le modèle s'il manque
$(ENV_FILE):
	@cp infra/.env.example $(ENV_FILE) && echo "→ $(ENV_FILE) créé depuis .env.example"

up: env ## Lance TOUTE la stack (infra + migrations + API + worker) puis provisionne Garage
	$(COMPOSE_APP) up -d --build
	@$(MAKE) --no-print-directory provision-garage || \
		echo "⚠  Provisioning Garage à finaliser (cf. README #4)."
	@$(MAKE) --no-print-directory urls

up-infra: env ## Lance uniquement l'infra (sans API/worker) — dév app sur l'hôte
	$(COMPOSE) up -d

build: env ## (Re)construit l'image applicative (API/worker/migrate)
	$(COMPOSE_APP) build

down: ## Arrête la stack (conserve les volumes/données)
	$(COMPOSE_APP) down

down-v: ## Arrête la stack ET supprime les volumes (RAZ des données)
	$(COMPOSE_APP) down -v

restart: ## Redémarre API + worker (après changement de deps/config)
	$(COMPOSE_APP) up -d --build api worker

ps: ## État des services
	$(COMPOSE_APP) ps

logs: ## Suit les logs de l'API et du worker
	$(COMPOSE_APP) logs -f api worker

logs-all: ## Suit les logs de tous les services
	$(COMPOSE_APP) logs -f

migrate: env ## Applique les migrations Alembic (schéma + RLS + audit)
	$(COMPOSE_APP) run --rm migrate

provision-garage: ## Provisionne Garage (layout + bucket + clé S3 de dev)
	./infra/provision-garage.sh

health: ## Vérifie l'API (GET /health)
	@curl -fsS http://localhost:8000/health && echo

shell-api: ## Ouvre un shell dans le conteneur API
	$(COMPOSE_APP) exec api bash

shell-db: psql ## Alias de psql
psql: ## Ouvre psql sur la base clm
	$(COMPOSE) exec postgres psql -U $${POSTGRES_USER:-clm} -d $${POSTGRES_DB:-clm}

lint: ## Lint + format-check + types dans le conteneur (= CI)
	$(COMPOSE_APP) run --rm --no-deps api sh -c "ruff check . && ruff format --check . && mypy src"

test: ## Tests hors-DB dans le conteneur
	$(COMPOSE_APP) run --rm --no-deps api pytest -m "not db"

clean: down-v ## Arrêt + suppression des volumes (alias de down-v)

urls: ## Rappelle les URLs des services de dev
	@echo ""
	@echo "Stack prête :"
	@echo "  API        http://localhost:8000/health   (docs: /docs)"
	@echo "  Keycloak   http://localhost:8080           (admin/admin ; alice/alice, bob/bob)"
	@echo "  Temporal   http://localhost:8233"
	@echo "  Mailpit    http://localhost:8025"
	@echo "  Weaviate   http://localhost:8081"
	@echo "  Garage UI  http://localhost:3909"
	@echo ""
