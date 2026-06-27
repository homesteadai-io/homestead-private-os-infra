#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="${APP_ROOT:-/opt/homestead/private-os-infra}"
DATA_ROOT="${DATA_ROOT:-/opt/homestead/data}"
KEEP_ROOT="${KEEP_ROOT:-/opt/homestead/the-keep}"

echo "Bootstrapping Homestead Private OS v0 on this node..."

sudo apt-get update
sudo apt-get install -y ca-certificates curl git ufw

if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sudo sh
fi

sudo install -d -m 0755 "$APP_ROOT" "$DATA_ROOT" "$KEEP_ROOT"
sudo usermod -aG docker "$USER" || true

echo "Created:"
echo "  APP_ROOT=$APP_ROOT"
echo "  DATA_ROOT=$DATA_ROOT"
echo "  KEEP_ROOT=$KEEP_ROOT"
echo
echo "Next: clone this repo into $APP_ROOT, clone The Keep into $KEEP_ROOT, then run infra/scripts/deploy.sh."

