#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

# Fix restrictive host permissions (root:root / 1750) that prevent non-root
# container users from reading files copied into the image build context.
echo "[rebuild] fixing file ownership and permissions..."
sudo chown -R "$USER":"$USER" .
find . -type d -exec chmod 755 {} \;
find . -type f -exec chmod 644 {} \;
chmod +x rebuild-back-front.sh

git pull
docker compose build --no-cache backend frontend
docker compose up -d
docker compose ps
