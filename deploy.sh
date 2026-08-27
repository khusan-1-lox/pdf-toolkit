#!/bin/bash
set -e

# PDF Toolkit — one-command deploy for Ubuntu 22.04 VPS
# Usage:  cp .env.example .env  -> fill DOMAIN, EMAIL, GOOGLE_* -> ./deploy.sh
# Requires: docker + docker compose plugin on host

# Load .env if present (for DOMAIN / EMAIL)
if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

if [ -z "${DOMAIN:-}" ] || [ -z "${EMAIL:-}" ]; then
  echo "ERROR: DOMAIN and EMAIL must be set in .env (see .env.example)"
  echo "  DOMAIN=yourdomain.com"
  echo "  EMAIL=you@example.com"
  exit 1
fi

echo "==> Building and starting containers ..."
docker compose up -d --build

echo "==> Waiting for nginx to be ready ..."
sleep 5

# Ensure certbot webroot exists
mkdir -p certbot/conf certbot/www

# Try nginx certbot plugin if certbot is inside nginx image;
# fallback to standalone certbot/certbot container via webroot.
echo "==> Obtaining TLS certificate for ${DOMAIN} ..."
if docker compose exec nginx sh -c "command -v certbot >/dev/null 2>&1"; then
  # certbot is inside nginx image (custom build)
  docker compose exec nginx certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos -m "$EMAIL" || true
else
  # Use official certbot image with webroot (works with stock nginx:alpine)
  docker run --rm \
    -v "$(pwd)/certbot/conf:/etc/letsencrypt" \
    -v "$(pwd)/certbot/www:/var/www/certbot" \
    certbot/certbot certonly --webroot -w /var/www/certbot -d "$DOMAIN" --non-interactive --agree-tos -m "$EMAIL" --expand || true

  # If cert was issued, inject real domain into nginx.conf if placeholder still present
  if [ -f "certbot/conf/live/${DOMAIN}/fullchain.pem" ]; then
    echo "==> Patching nginx.conf with real domain ${DOMAIN} ..."
    # Replace placeholder YOUR_DOMAIN with real domain (idempotent)
    sed -i "s|YOUR_DOMAIN|${DOMAIN}|g" nginx.conf || true
    echo "==> Reloading nginx ..."
    docker compose exec nginx nginx -s reload || docker compose restart nginx || true
  else
    echo "WARN: Certificate not yet issued (DNS may not point to this host yet). HTTP will work; HTTPS will activate after DNS propagates — re-run ./deploy.sh"
  fi
fi

echo "==> Setting up auto-renew cron (host) ..."
# Add cron to renew certs daily at 03:00 and reload nginx
CRON_CMD="0 3 * * * cd $(pwd) && docker run --rm -v $(pwd)/certbot/conf:/etc/letsencrypt -v $(pwd)/certbot/www:/var/www/certbot certbot/certbot renew --quiet && docker compose exec nginx nginx -s reload"
( crontab -l 2>/dev/null | grep -v "certbot renew" ; echo "$CRON_CMD" ) | crontab - 2>/dev/null || echo "  (crontab not available — add manually: $CRON_CMD)"

echo ""
echo "Deploy complete."
echo "  HTTP : http://${DOMAIN}"
echo "  HTTPS: https://${DOMAIN} (after cert issuance)"
echo "  Health: https://${DOMAIN}/api/health  or http://<VPS_IP>/health"
echo ""
echo "Notes:"
echo "  - On Windows, deploy.sh is not executable via chmod; run with: bash deploy.sh"
echo "  - First boot without DNS will stay HTTP-only until cert succeeds."
