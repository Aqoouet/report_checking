#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
docker compose build backend frontend
docker compose up -d
