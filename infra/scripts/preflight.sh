#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="${APP_ROOT:-/opt/homestead/runtime}"
ENV_FILE="${ENV_FILE:-/opt/homestead/secrets/runtime.env}"

fail() {
  echo "preflight failed: $*" >&2
  exit 1
}

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "missing command: $1"
}

need_cmd git
need_cmd docker

docker compose version >/dev/null 2>&1 || fail "Docker Compose plugin is unavailable"
[ -d "$APP_ROOT" ] || fail "APP_ROOT does not exist: $APP_ROOT"
[ -f "$APP_ROOT/infra/docker-compose.yml" ] || fail "missing compose file: $APP_ROOT/infra/docker-compose.yml"
[ -f "$ENV_FILE" ] || fail "missing env file: $ENV_FILE"

if command -v stat >/dev/null 2>&1; then
  env_mode="$(stat -c "%a" "$ENV_FILE" 2>/dev/null || true)"
  if [ -n "$env_mode" ] && [ "$env_mode" != "600" ]; then
    echo "preflight warning: $ENV_FILE mode is $env_mode; recommended mode is 600"
  fi
fi

set -a
# shellcheck disable=SC1090
. "$ENV_FILE"
set +a

KEEP_REPO_HOST_PATH="${KEEP_REPO_HOST_PATH:-/opt/homestead/the-keep}"
HOMESTEAD_DATA_PATH="${HOMESTEAD_DATA_PATH:-/opt/homestead/data}"
HOMESTEAD_REPO_PATH="${HOMESTEAD_REPO_PATH:-/workspace/keep}"
RECEIPTS_DIR="${RECEIPTS_DIR:-/data/receipts}"
CADDY_HTTP_BIND="${CADDY_HTTP_BIND:-127.0.0.1}"
CADDY_HTTPS_BIND="${CADDY_HTTPS_BIND:-127.0.0.1}"

[ "$HOMESTEAD_REPO_PATH" = "/workspace/keep" ] || fail "HOMESTEAD_REPO_PATH should be /workspace/keep for v0 container mounts"
[ "$RECEIPTS_DIR" = "/data/receipts" ] || fail "RECEIPTS_DIR should be /data/receipts for v0 container mounts"
[ -d "$KEEP_REPO_HOST_PATH" ] || fail "Keep path does not exist: $KEEP_REPO_HOST_PATH"
git -C "$KEEP_REPO_HOST_PATH" rev-parse --is-inside-work-tree >/dev/null 2>&1 || fail "Keep path is not a git work tree: $KEEP_REPO_HOST_PATH"

if [ -n "$(git -C "$KEEP_REPO_HOST_PATH" status --porcelain)" ]; then
  echo "preflight warning: Keep work tree has uncommitted changes"
fi

if [ -n "$(git -C "$APP_ROOT" status --porcelain)" ]; then
  echo "preflight warning: runtime repo has uncommitted changes"
fi

mkdir -p "$HOMESTEAD_DATA_PATH" "$HOMESTEAD_DATA_PATH/receipts" "$HOMESTEAD_DATA_PATH/logs"
[ -w "$HOMESTEAD_DATA_PATH" ] || fail "data path is not writable: $HOMESTEAD_DATA_PATH"

cd "$APP_ROOT"
HOMESTEAD_ENV_FILE="$ENV_FILE" docker compose --env-file "$ENV_FILE" -f infra/docker-compose.yml config >/dev/null

docker run --rm -v "$APP_ROOT/infra/caddy/Caddyfile:/etc/caddy/Caddyfile:ro" caddy:2-alpine caddy validate --config /etc/caddy/Caddyfile >/dev/null

if [ "$CADDY_HTTP_BIND" = "0.0.0.0" ] || [ "$CADDY_HTTPS_BIND" = "0.0.0.0" ]; then
  echo "preflight warning: Caddy is configured for public bind. v0 API/MCP are unauthenticated."
fi

if command -v tailscale >/dev/null 2>&1; then
  tailscale status >/dev/null 2>&1 || echo "preflight warning: tailscale command exists but tailnet status is unavailable"
else
  echo "preflight note: tailscale command not found; use SSH tunnel, loopback, or public DNS mode intentionally"
fi

echo "preflight ok"
echo "  APP_ROOT=$APP_ROOT"
echo "  ENV_FILE=$ENV_FILE"
echo "  KEEP_REPO_HOST_PATH=$KEEP_REPO_HOST_PATH"
echo "  HOMESTEAD_DATA_PATH=$HOMESTEAD_DATA_PATH"
echo "  CADDY_HTTP_BIND=$CADDY_HTTP_BIND"
echo "  CADDY_HTTPS_BIND=$CADDY_HTTPS_BIND"
