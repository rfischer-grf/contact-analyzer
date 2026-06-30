#!/usr/bin/env bash
# Provisionne le cluster Garage de DEV (cf. docs/architecture.md §2.1, README #4) :
#   1. layout mono-nœud,
#   2. bucket `contrats`,
#   3. une clé d'accès S3 DÉTERMINISTE (importée), autorisée read/write/owner,
#   4. CORS du bucket (PUT direct navigateur depuis l'origine de la SPA).
#
# Idempotent : ré-exécutable sans effet de bord. Les identifiants ci-dessous sont
# des valeurs de DÉVELOPPEMENT (cf. infra/.env.example) — sans portée hors de ce
# cluster jetable. Ne JAMAIS les réutiliser en production.
set -euo pipefail
cd "$(dirname "$0")"

# Doivent coïncider avec les valeurs par défaut de docker-compose.yml / .env.example.
ACCESS_KEY="${CI_S3_ACCESS_KEY:-GK31c1d34dd99c7b8e51c52940}"
SECRET_KEY="${CI_S3_SECRET_KEY:-1c1d34dd99c7b8e51c1d34dd99c7b8e51c1d34dd99c7b8e51c1d34dd99c7b8e5}"
# Origine(s) autorisée(s) pour le PUT présigné direct navigateur→Garage (CORS).
CORS_ORIGINS="${CLM_CORS_ORIGINS:-http://localhost:5173}"

COMPOSE=(docker compose -f docker-compose.yml --env-file .env)
COMPOSE_APP=(docker compose -f docker-compose.yml --env-file .env --profile app)
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

echo "→ Autorisation read/write/owner sur 'contrats'…"
# owner requis pour PutBucketCors (opération administrative côté Garage).
g bucket allow --read --write --owner contrats --key "$ACCESS_KEY" >/dev/null 2>&1 || true

echo "→ CORS du bucket (origine SPA : $CORS_ORIGINS)…"
# Garage ne configure pas le CORS via la CLI → on passe par l'API S3 (boto3),
# exécutée dans un conteneur jetable de l'image applicative (clés déjà en env).
PYCORS='import os,boto3
from botocore.config import Config
s3=boto3.client("s3",endpoint_url=os.environ["CI_S3_ENDPOINT_URL"],region_name=os.environ.get("CI_S3_REGION","garage"),aws_access_key_id=os.environ["CI_S3_ACCESS_KEY"],aws_secret_access_key=os.environ["CI_S3_SECRET_KEY"],config=Config(signature_version="s3v4",s3={"addressing_style":"path"}))
o=os.environ.get("CLM_CORS_ORIGINS","http://localhost:5173").split(",")
s3.put_bucket_cors(Bucket=os.environ.get("CI_S3_BUCKET","contrats"),CORSConfiguration={"CORSRules":[{"AllowedOrigins":o,"AllowedMethods":["PUT","GET","HEAD"],"AllowedHeaders":["*"],"ExposeHeaders":["ETag"],"MaxAgeSeconds":3600}]})'
CLM_CORS_ORIGINS="$CORS_ORIGINS" "${COMPOSE_APP[@]}" run --rm --no-deps -T \
  -e CLM_CORS_ORIGINS="$CORS_ORIGINS" api python -c "$PYCORS" >/dev/null 2>&1 \
  && echo "  CORS OK" || echo "  ⚠ CORS non configuré (image app indisponible ?) — relancer après \`make up\`."

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
