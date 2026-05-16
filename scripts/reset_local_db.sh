#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOFTWARE_DIR="$REPO_ROOT/software"
DOCKER_COMPOSE_FILE="$SOFTWARE_DIR/docker-compose.yml"
VENV_PY="$SOFTWARE_DIR/.venv/bin/python"

# Detect docker-compose command (support Docker Compose v1 and v2)
if command -v docker-compose >/dev/null 2>&1; then
  COMPOSE_CMD="docker-compose"
elif command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  COMPOSE_CMD="docker compose"
else
  echo "ERROR: neither 'docker-compose' nor 'docker compose' is available on PATH. Install Docker Compose or enable the Docker CLI plugin."
  exit 2
fi

echo "[1/5] Stopping docker-compose services (if any)"
${COMPOSE_CMD} -f "$DOCKER_COMPOSE_FILE" down || true

echo "[2/5] Removing local DB data directories (reset)"
sudo rm -rf "$SOFTWARE_DIR/data/postgres" "$SOFTWARE_DIR/data/influx" || true

echo "[3/5] Starting docker-compose services"
${COMPOSE_CMD} -f "$DOCKER_COMPOSE_FILE" up -d

echo "[4/5] Waiting for Postgres to accept connections"
MAX_ATTEMPTS=30
SLEEP_SECONDS=2
attempt=0
while true; do
  attempt=$((attempt+1))
    if [ -x "$VENV_PY" ]; then
    PYTHONPATH="$REPO_ROOT" "$VENV_PY" - <<'PY'
  import sys
  sys.path.insert(0, "$REPO_ROOT")
  from software.db import postgres_manager as pm
  try:
    conn = pm.get_connection()
    conn.close()
    print('PG_OK')
  except Exception:
    raise SystemExit(1)
  PY
    status=$?
    else
    # Fall back to system python3
    PYTHONPATH="$REPO_ROOT" python3 - <<'PY'
  import sys
  sys.path.insert(0, "$REPO_ROOT")
  from software.db import postgres_manager as pm
  try:
    conn = pm.get_connection()
    conn.close()
    print('PG_OK')
  except Exception:
    raise SystemExit(1)
  PY
    status=$?
  fi

  if [ "$status" -eq 0 ]; then
    echo "Postgres is ready"
    break
  fi

  if [ "$attempt" -ge "$MAX_ATTEMPTS" ]; then
    echo "Timed out waiting for Postgres after $MAX_ATTEMPTS attempts"
    exit 1
  fi
  echo "Waiting for Postgres... (attempt $attempt/$MAX_ATTEMPTS)"
  sleep $SLEEP_SECONDS
done

echo "[5/5] Initializing DB schema via postgres_manager.init_db()"
if [ -x "$VENV_PY" ]; then
  "$VENV_PY" "$SOFTWARE_DIR/db/postgres_manager.py"
else
  python3 "$SOFTWARE_DIR/db/postgres_manager.py"
fi

echo "Done. DB reset and initialized."
