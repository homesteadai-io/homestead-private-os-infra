#!/usr/bin/env bash
set -euo pipefail

DATA_ROOT="${DATA_ROOT:-${HOMESTEAD_DATA_PATH:-/opt/homestead/data}}"
BACKUP_ROOT="${BACKUP_ROOT:-/opt/homestead/backups}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="$BACKUP_ROOT/homestead-data-$STAMP.tgz"

sudo install -d -m 0755 "$BACKUP_ROOT"
tar -czf "$OUT" -C "$DATA_ROOT" .

echo "$OUT"
