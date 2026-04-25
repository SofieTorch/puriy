#!/bin/bash
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Load test env
set -a; source "$SCRIPT_DIR/.env.test"; set +a

cleanup() {
  echo ""
  echo ">>> Cleaning up..."
  lsof -ti:8081 | xargs kill -9 2>/dev/null || true
  "$SCRIPT_DIR/teardown.sh"
}
trap cleanup EXIT

echo "========================================="
echo "  CBBA Mobility E2E Tests"
echo "========================================="

# 1. Setup test environment (DB + test server)
echo ""
echo ">>> Setting up test environment..."
"$SCRIPT_DIR/setup.sh"

# 2. Run server-side detour lifecycle tests
echo ""
echo ">>> Running detour lifecycle tests..."
cp "$SCRIPT_DIR/test_detour_lifecycle.py" "$PROJECT_ROOT/server/tests/_e2e_test_detour_lifecycle.py"
DATABASE_URL="$DATABASE_URL" \
TEST_DATABASE_URL="$DATABASE_URL" \
TEST_SERVER_URL="http://localhost:$TEST_SERVER_PORT" \
uv run --directory "$PROJECT_ROOT/server" --extra test pytest tests/_e2e_test_detour_lifecycle.py -v
PYTEST_EXIT=$?
rm -f "$PROJECT_ROOT/server/tests/_e2e_test_detour_lifecycle.py"

if [ $PYTEST_EXIT -ne 0 ]; then
  echo "❌ Server-side tests failed"
  exit $PYTEST_EXIT
fi
echo "✅ Server-side tests passed"

# 3. Build and install app with test env vars (no Metro)
echo ""
echo ">>> Building app for E2E..."
cd "$PROJECT_ROOT/app"
EXPO_PUBLIC_E2E=true \
EXPO_PUBLIC_E2E_DEVICE_ID="$E2E_DEVICE_ID" \
API_BASE_URL="http://localhost:$TEST_SERVER_PORT" \
npx expo run:ios --no-bundler

# 4. Start Metro bundler with test API URL
echo ""
echo ">>> Starting Metro bundler..."
lsof -ti:8081 | xargs kill -9 2>/dev/null || true
sleep 1
cd "$PROJECT_ROOT/app"
EXPO_PUBLIC_E2E=true EXPO_PUBLIC_E2E_DEVICE_ID="$E2E_DEVICE_ID" API_BASE_URL="http://localhost:$TEST_SERVER_PORT" npx expo start --no-dev --clear > /dev/null 2>&1 &

echo "Waiting for Metro bundler..."
for i in $(seq 1 60); do
  if curl -s http://localhost:8081/status 2>/dev/null | grep -q "packager-status:running"; then
    echo "Metro bundler ready!"
    break
  fi
  if [ "$i" -eq 60 ]; then
    echo "ERROR: Metro bundler not ready after 60s"
    exit 1
  fi
  sleep 1
done

# 5. Grant permissions and set location on simulator
echo "Configuring simulator..."
xcrun simctl privacy booted grant location com.cbba.mobility 2>/dev/null || true
xcrun simctl privacy booted grant location-always com.cbba.mobility 2>/dev/null || true
xcrun simctl location booted set -- -17.394 -66.182 2>/dev/null || true

# 6. Launch app on simulator
echo "Launching app..."
xcrun simctl launch booted com.cbba.mobility 2>/dev/null || true
sleep 5

# 7. Run Maestro flows
echo ""
echo ">>> Running Maestro E2E flows..."
maestro test "$SCRIPT_DIR/flows/"
MAESTRO_EXIT=$?

echo ""
if [ $MAESTRO_EXIT -eq 0 ]; then
  echo "✅ All E2E tests passed!"
else
  echo "❌ Some Maestro tests failed (exit code: $MAESTRO_EXIT)"
fi
exit $MAESTRO_EXIT
