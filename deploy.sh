#!/usr/bin/env bash
set -euo pipefail
# Run from the directory this script lives in (works on any host).
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Create .env from example on first deploy only.
if [ ! -f .env ]; then
  cp .env.example .env
fi

# Ensure a host port is set, but never override one you already chose.
if ! grep -qE '^WPUPDATER_PORT=' .env; then
  echo "WPUPDATER_PORT=8090" >> .env
fi

# Generate a session secret only once, so redeploys don't invalidate sessions.
if grep -qE '^WPUPDATER_SECRET_KEY=(replace-with-a-long-random-string|change-me)?$' .env || ! grep -qE '^WPUPDATER_SECRET_KEY=' .env; then
  SECRET=$(openssl rand -hex 32)
  if grep -qE '^WPUPDATER_SECRET_KEY=' .env; then
    sed -i "s|^WPUPDATER_SECRET_KEY=.*|WPUPDATER_SECRET_KEY=${SECRET}|" .env
  else
    echo "WPUPDATER_SECRET_KEY=${SECRET}" >> .env
  fi
fi

# The container runs as uid 10001 (non-root); the bind-mounted data dir must be
# writable by it or SQLite cannot create its database.
mkdir -p data
chown -R 10001:10001 data

echo "--- effective .env (secrets hidden) ---"
grep -vE 'SECRET_KEY|PASSWORD' .env | grep -vE '^\s*#|^\s*$' || true

echo "--- building + starting ---"
docker compose up -d --build

echo "--- container status ---"
docker compose ps
