#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

git pull
docker compose build --no-cache backend frontend
docker compose up -d
docker compose ps
