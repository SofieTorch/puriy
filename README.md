# CBBA Mobility

## PostGIS Setup (Linux)

The Alembic migration now creates PostGIS extensions automatically, but PostgreSQL must have the PostGIS packages installed first.

Install packages (example for PostgreSQL 16):

```bash
sudo apt update
sudo apt install -y postgis postgresql-16-postgis-3 postgresql-16-postgis-3-scripts
```

If you use another PostgreSQL major version, replace `16` with your version (for example `15`).

Then run the database migrations:

```bash
cd packages/database
uv run alembic upgrade head
```

Verify PostGIS is enabled:

```bash
psql -d cbba_mobility -c "SELECT postgis_full_version();"
```