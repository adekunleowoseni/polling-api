#!/usr/bin/env bash
# Run on the VPS inside the poll folder after uploading backend files.
# Usage: cd /home/USER/edumatrix/poll && bash deploy/install-vps.sh

set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$APP_DIR"

echo "==> Creating virtualenv"
python3 -m venv .venv
source .venv/bin/activate

echo "==> Installing Python dependencies"
pip install --upgrade pip
pip install -r requirements.txt

echo "==> Ensuring storage directory"
mkdir -p storage/snaps

if [[ ! -f .env ]]; then
  cp deploy/env.production.example .env
  echo "Created .env from template — edit it before starting the service."
fi

echo ""
echo "Done. Next steps:"
echo "  1. Edit $APP_DIR/.env (MongoDB, CORS_ORIGINS, admin password, Google AI)"
echo "  2. Copy deploy/lado-poll.service to /etc/systemd/system/ and fix paths"
echo "  3. sudo systemctl enable --now lado-poll"
echo "  4. Configure nginx (deploy/nginx-poll.conf or nginx-poll-subpath.conf)"
echo "  5. sudo certbot --nginx -d your-api-domain"
