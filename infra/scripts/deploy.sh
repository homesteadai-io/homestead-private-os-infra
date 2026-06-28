#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="${APP_ROOT:-/opt/homestead/runtime}"
ENV_FILE="${ENV_FILE:-/opt/homestead/secrets/runtime.env}"

cd "$APP_ROOT"

APP_ROOT="$APP_ROOT" ENV_FILE="$ENV_FILE" bash infra/scripts/preflight.sh

git fetch --all --prune
git status --short --branch

HOMESTEAD_ENV_FILE="$ENV_FILE" docker compose --env-file "$ENV_FILE" -f infra/docker-compose.yml up -d --build
HOMESTEAD_ENV_FILE="$ENV_FILE" docker compose --env-file "$ENV_FILE" -f infra/docker-compose.yml ps
