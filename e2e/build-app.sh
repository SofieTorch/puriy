#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Load test env
set -a; source "$SCRIPT_DIR/.env.test"; set +a

echo "=== Building app for E2E tests ==="

cd "$PROJECT_ROOT/app"

EXPO_PUBLIC_E2E=true \
EXPO_PUBLIC_E2E_DEVICE_ID="$E2E_DEVICE_ID" \
API_BASE_URL="http://localhost:$TEST_SERVER_PORT" \
npx expo run:ios --no-bundler

echo "=== App built and installed for E2E ==="
