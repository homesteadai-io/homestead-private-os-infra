#!/usr/bin/env sh
set -eu

REPO="${HOMESTEAD_REPO_PATH:-/workspace/keep}"
INTERVAL="${REPO_SYNC_INTERVAL_SECONDS:-600}"

while true; do
  if [ -d "$REPO/.git" ]; then
    echo "repo-sync: fetching $REPO"
    git -C "$REPO" fetch --all --prune || true
  else
    echo "repo-sync: no git repo at $REPO"
  fi
  sleep "$INTERVAL"
done

