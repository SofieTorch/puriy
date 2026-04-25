#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Load test env
set -a; source "$SCRIPT_DIR/.env.test"; set +a

echo "=== Setting up E2E test environment ==="

# Kill any existing test server
if [ -f "$SCRIPT_DIR/.server.pid" ]; then
  kill "$(cat "$SCRIPT_DIR/.server.pid")" 2>/dev/null || true
  rm -f "$SCRIPT_DIR/.server.pid"
fi

# 1. Create test database (terminate existing connections first)
echo "Creating test database..."
psql -d postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'open_transit_e2e' AND pid != pg_backend_pid();" > /dev/null 2>&1 || true
psql -d postgres -c "DROP DATABASE IF EXISTS open_transit_e2e;" 2>/dev/null || true
psql -d postgres -c "CREATE DATABASE open_transit_e2e;"
psql -d open_transit_e2e -c "CREATE EXTENSION IF NOT EXISTS postgis;"

# 2. Run Alembic migrations
echo "Running migrations..."
cd "$PROJECT_ROOT/packages/database"
DATABASE_URL="$DATABASE_URL" uv run alembic upgrade head

# 3. Seed test data
echo "Seeding test data..."
DATABASE_URL="$DATABASE_URL" VALHALLA_URL="$VALHALLA_URL" uv run --directory "$PROJECT_ROOT/server" python "$PROJECT_ROOT/e2e/seed.py"

# 4. Start test server in background
echo "Starting test server on port $TEST_SERVER_PORT..."
cd "$PROJECT_ROOT/server"
DATABASE_URL="$DATABASE_URL" uv run uvicorn main:app --port "$TEST_SERVER_PORT" --log-level warning > "$SCRIPT_DIR/.server.log" 2>&1 &
echo $! > "$SCRIPT_DIR/.server.pid"

# Wait for server to be ready
for i in $(seq 1 30); do
  if curl -s "http://localhost:$TEST_SERVER_PORT/health" > /dev/null 2>&1; then
    echo "Server ready!"
    break
  fi
  if [ "$i" -eq 30 ]; then
    echo "ERROR: Server failed to start within 30 seconds" >&2
    exit 1
  fi
  sleep 1
done

# 5. Rebuild transit graph for directions
echo "Rebuilding transit graph..."
curl -s -X POST "http://localhost:$TEST_SERVER_PORT/directions/graph/rebuild" > /dev/null
echo "Transit graph ready."

echo "=== E2E environment ready ==="
