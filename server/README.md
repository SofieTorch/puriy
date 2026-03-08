## Getting started

1. Start the services:

```bash
cd /server
docker compose up -d
```

2. Run migrations:

```bash
docker compose exec server bash
uv run alembic -c ../packages/database/alembic.ini upgrade head
```

3. API is available at (http://localhost:8000)[http://localhost:8000]

4. To access the container and run commands inside the server environment:

```bash
docker compose exec server bash
```

## Creating migrations

To create a new migration with Alembic:

1. Auto-generate from model changes:

```bash
docker compose exec server alembic -c ../packages/database/alembic.ini revision --autogenerate -m "add stops table"
```

2. The migration file will be created in `packages/database/alembic/versions`. Then apply it with:

```bash
docker compose exec server alembic -c ../packages/database/alembic.ini upgrade head
```

Other useful commands:

```bash
# Check current migration status
docker compose exec server alembic -c ../packages/database/alembic.ini current

# See migration history
docker compose exec server alembic -c ../packages/database/alembic.ini history

# Rollback one migration
docker compose exec server alembic -c ../packages/database/alembic.ini downgrade -1

# Rollback to specific revision
docker compose exec server alembic -c ../packages/database/alembic.ini downgrade 001
```

## Running tests

First, install test dependencies:

```bash
uv pip install -e ".[test]"
```

Then enter the container and run:

```bash
# Run tests
uv run pytest

# With coverage
uv run pytest --cov=. --cov-report=html
```