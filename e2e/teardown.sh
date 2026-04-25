#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== Tearing down E2E test environment ==="

# Kill test server
if [ -f "$SCRIPT_DIR/.server.pid" ]; then
  PID=$(cat "$SCRIPT_DIR/.server.pid")
  kill "$PID" 2>/dev/null || true
  rm "$SCRIPT_DIR/.server.pid"
  echo "Stopped test server (PID $PID)"
fi

# Optionally drop test database
# psql -U transit -h localhost -d postgres -c "DROP DATABASE IF EXISTS open_transit_e2e;"

echo "=== Teardown complete ==="
