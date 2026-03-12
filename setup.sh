#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

PROJECTS=(
  "packages/database"
  "packages/geodata"
  "server"
  "transit-lab"
)

# Fallback Python versions when a project has no .python-version file.
# All subprojects are normalized to Python 3.14.
declare -A DEFAULT_PYTHON=(
  ["packages/database"]="3.14"
  ["packages/geodata"]="3.14"
  ["server"]="3.14"
  ["transit-lab"]="3.14"
)

# Load local environment values if present (e.g. database URLs).
if [[ -f "$ROOT_DIR/.env" ]]; then
  # Export all variables declared in .env to child processes.
  set -a
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.env"
  set +a
fi

# ------------------------------------------------------------
# uv installation
# ------------------------------------------------------------

echo "==> Checking uv"
if ! command -v uv >/dev/null 2>&1; then
  echo "uv not found. Installing..."
  case "$(uname -s)" in
    Darwin)
      if ! command -v brew >/dev/null 2>&1; then
        echo "ERROR: Homebrew is required on macOS to install uv."
        echo "Install Homebrew first: https://brew.sh"
        exit 1
      fi
      brew install uv
      ;;
    Linux)
      curl -LsSf https://astral.sh/uv/install.sh | sh
      export PATH="$HOME/.local/bin:$PATH"
      ;;
    *)
      echo "ERROR: Unsupported OS for automatic uv install: $(uname -s)"
      exit 1
      ;;
  esac
fi

# ------------------------------------------------------------
# Python runtimes and dependencies
# ------------------------------------------------------------

if ! command -v uv >/dev/null 2>&1; then
  echo "ERROR: uv is still not available in PATH."
  echo "Try: export PATH=\"\$HOME/.local/bin:\$PATH\""
  exit 1
fi

echo "==> Installing required Python runtime (3.14)"
uv python install 3.14

for rel in "${PROJECTS[@]}"; do
  dir="$ROOT_DIR/$rel"

  if [[ ! -d "$dir" ]]; then
    echo "==> Skipping missing directory: $rel"
    continue
  fi

  py="${DEFAULT_PYTHON[$rel]}"
  if [[ -f "$dir/.python-version" ]]; then
    py="$(tr -d '[:space:]' < "$dir/.python-version")"
  fi

  echo "==> Setting up $rel (Python $py)"
  (
    cd "$dir"
    uv venv --python "$py" .venv
    uv sync --frozen
  )
done

# ------------------------------------------------------------
# Mobile app dependencies
# ------------------------------------------------------------

APP_DIR="$ROOT_DIR/app"
if [[ -d "$APP_DIR" ]]; then
  if ! command -v npm >/dev/null 2>&1; then
    echo "ERROR: npm is required to install app dependencies in app/."
    exit 1
  fi

  echo "==> Installing app dependencies (app/)"
  (
    cd "$APP_DIR"
    if [[ -f package-lock.json ]]; then
      npm ci
    else
      npm install
    fi
  )
else
  echo "==> Skipping missing directory: app"
fi

# ------------------------------------------------------------
# Database migrations
# ------------------------------------------------------------

DB_DIR="$ROOT_DIR/packages/database"
if [[ -d "$DB_DIR" ]]; then
  echo "==> Running database migrations (packages/database)"
  (
    cd "$DB_DIR"
    if [[ -z "${DATABASE_URL:-}" ]]; then
      echo "Skipping migrations: set DATABASE_URL in .env"
      exit 0
    fi

    echo "==> Checking database connectivity"
    uv run python src/database/check_connection.py

    echo "==> Running migrations"
    uv run alembic upgrade head
  )
else
  echo "==> Skipping missing directory: packages/database"
fi

# ------------------------------------------------------------
# Summary
# ------------------------------------------------------------

echo ""
echo "Setup complete."
echo "Activate an env with:"
echo "  source <project>/.venv/bin/activate"
echo "Examples:"
echo "  source server/.venv/bin/activate"
echo "  source transit-lab/.venv/bin/activate"
echo "  source packages/database/.venv/bin/activate"
echo "  source packages/geodata/.venv/bin/activate"