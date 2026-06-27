#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="${APP_ROOT:-/opt/homestead/private-os-infra}"
ENV_FILE="${ENV_FILE:-$APP_ROOT/infra/.env}"

cd "$APP_ROOT"

if [ ! -f "$ENV_FILE" ]; then
  echo "Missing env file: $ENV_FILE"
  echo "Copy infra/.env.example to infra/.env and fill placeholders before deploying."
  exit 1
fi

git fetch --all --prune
git status --short --branch

docker compose --env-file "$ENV_FILE" -f infra/docker-compose.yml up -d --build
docker compose --env-file "$ENV_FILE" -f infra/docker-compose.yml ps

