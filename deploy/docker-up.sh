#!/usr/bin/env bash
# Start the Docker stack from the backend (poll) folder.
# Usage: cd /home/USER/edumatrix/poll && bash deploy/docker-up.sh

set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$APP_DIR"

if [[ ! -f .env ]]; then
  cp deploy/env.docker.example .env
  echo "Created .env — set MONGODB_URI (Atlas), SUPER_ADMIN_PASSWORD, and CORS_ORIGINS."
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is not installed. Install Docker Engine first."
  exit 1
fi

docker compose up -d --build

echo ""
echo "API listening on http://127.0.0.1:8000 (use nginx + SSL for public HTTPS)."
echo "Logs: docker compose logs -f api"
