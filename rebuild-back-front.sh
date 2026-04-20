#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

git pull

# Force-remove old containers by name regardless of which compose project started them.
# This handles the case where containers were started from a different directory
# and carry stale labels / missing volume mounts.
docker rm -f report-checker-backend report-checker-frontend report-checker-docling 2>/dev/null || true

docker compose build --no-cache backend frontend
docker compose up -d --force-recreate
docker compose ps
