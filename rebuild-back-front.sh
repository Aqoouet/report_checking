#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Docker daemon runs as root and can access root-owned files.
# Use it to fix ownership/permissions without needing sudo.
echo "[rebuild] fixing file ownership and permissions via docker..."
docker run --rm \
  -v "${SCRIPT_DIR}:/workdir" \
  alpine sh -c "
    chown -R $(id -u):$(id -g) /workdir
    find /workdir -type d -exec chmod 755 {} \;
    find /workdir -type f -exec chmod 644 {} \;
    chmod +x /workdir/rebuild-back-front.sh
  "

cd "${SCRIPT_DIR}"
git pull
docker compose build --no-cache backend frontend
docker compose up -d
docker compose ps
