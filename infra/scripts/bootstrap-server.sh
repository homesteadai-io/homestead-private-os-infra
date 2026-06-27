#!/usr/bin/env bash
set -euo pipefail

BASE_ROOT="${BASE_ROOT:-/opt/homestead}"
APP_ROOT="${APP_ROOT:-$BASE_ROOT/runtime}"
DATA_ROOT="${DATA_ROOT:-/opt/homestead/data}"
KEEP_ROOT="${KEEP_ROOT:-/opt/homestead/the-keep}"
BACKUP_ROOT="${BACKUP_ROOT:-/opt/homestead/backups}"
SECRETS_ROOT="${SECRETS_ROOT:-/opt/homestead/secrets}"

echo "Bootstrapping Homestead Private OS v0 on this node..."

sudo apt-get update
sudo apt-get install -y ca-certificates curl git ufw

if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sudo sh
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "Docker is installed, but Docker Compose is not available."
  echo "Re-run after Docker finishes installing, or install the Docker Compose plugin."
  exit 1
fi

sudo install -d -m 0755 "$BASE_ROOT" "$APP_ROOT" "$DATA_ROOT" "$KEEP_ROOT" "$BACKUP_ROOT"
sudo install -d -m 0700 "$SECRETS_ROOT"
sudo usermod -aG docker "$USER" || true

echo "Created:"
echo "  BASE_ROOT=$BASE_ROOT"
echo "  APP_ROOT=$APP_ROOT"
echo "  DATA_ROOT=$DATA_ROOT"
echo "  KEEP_ROOT=$KEEP_ROOT"
echo "  BACKUP_ROOT=$BACKUP_ROOT"
echo "  SECRETS_ROOT=$SECRETS_ROOT"
echo
echo "Next:"
echo "  1. Clone homesteadai-io/homestead-private-os-infra into $APP_ROOT"
echo "  2. Clone The Keep / OKF context graph into $KEEP_ROOT"
echo "  3. Copy $APP_ROOT/infra/.env.example to $SECRETS_ROOT/runtime.env"
echo "  4. Edit $SECRETS_ROOT/runtime.env"
echo "  5. Run $APP_ROOT/infra/scripts/deploy.sh"
