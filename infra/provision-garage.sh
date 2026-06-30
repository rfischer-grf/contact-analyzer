#!/usr/bin/env bash
# Provisionne le cluster Garage de DEV (cf. docs/architecture.md §2.1, README #4) :
#   1. layout mono-nœud,
#   2. bucket `contrats`,
#   3. une clé d'accès S3 DÉTERMINISTE (importée), autorisée en lecture/écriture.
#
# Idempotent : ré-exécutable sans effet de bord. Les identifiants ci-dessous sont
# des valeurs de DÉVELOPPEMENT (cf. infra/.env.example) — sans portée hors de ce
# cluster jetable. Ne JAMAIS les réutiliser en production.
set -euo pipefail
cd "$(dirname "$0")"

# Doivent coïncider avec les valeurs par défaut de docker-compose.yml / .env.example.
ACCESS_KEY="${CI_S3_ACCESS_KEY:-GK31c1d34dd99c7b8e51c52940}"
SECRET_KEY="${CI_S3_SECRET_KEY:-1c1d34dd99c7b8e51c1d34dd99c7b8e51c1d34dd99c7b8e51c1d34dd99c7b8e5}"

COMPOSE=(docker compose -f docker-compose.yml --env-file .env)
g() { "${COMPOSE[@]}" exec -T garage /garage "$@"; }

echo "→ Garage : attente du nœud…"
for _ in $(seq 1 30); do
  if NODE=$(g node id -q 2>/dev/null | cut -d@ -f1 | tr -d '\r\n '); [ -n "${NODE:-}" ]; then
    break
  fi
  sleep 1
done
[ -n "${NODE:-}" ] || { echo "✗ Garage injoignable (le service est-il démarré ?)" >&2; exit 1; }

echo "→ Layout mono-nœud (zone dc1, 1G)…"
g layout assign -z dc1 -c 1G "$NODE" >/dev/null 2>&1 || true
g layout apply --version 1 >/dev/null 2>&1 || true   # no-op si déjà appliqué

echo "→ Bucket 'contrats'…"
g bucket create contrats >/dev/null 2>&1 || true

echo "→ Clé d'accès déterministe (import)…"
g key import --yes -n clm-dev "$ACCESS_KEY" "$SECRET_KEY" >/dev/null 2>&1 || true

echo "→ Autorisation lecture/écriture sur 'contrats'…"
g bucket allow --read --write contrats --key "$ACCESS_KEY" >/dev/null 2>&1 || true

if g key info clm-dev >/dev/null 2>&1; then
  echo "✓ Garage provisionné. CI_S3_ACCESS_KEY=$ACCESS_KEY (cf. .env.example pour le secret)."
else
  cat >&2 <<EOF
✗ Provisioning incomplet. Provisionner manuellement (cf. README #4) :
    docker compose -f infra/docker-compose.yml exec garage /garage layout assign -z dc1 -c 1G <node-id>
    docker compose -f infra/docker-compose.yml exec garage /garage layout apply --version 1
    docker compose -f infra/docker-compose.yml exec garage /garage bucket create contrats
    docker compose -f infra/docker-compose.yml exec garage /garage key create clm-dev
  puis renseigner CI_S3_ACCESS_KEY / CI_S3_SECRET_KEY dans infra/.env.
EOF
  exit 1
fi
