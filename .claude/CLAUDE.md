# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Crowdsourced public transit route reconstruction for Cochabamba, Bolivia. Users record GPS traces while riding buses; the system reconstructs routes via clustering and community voting.

## Monorepo Layout

- **`packages/database/`** — SQLModel ORM models, Alembic migrations, PostGIS (SRID 4326). Source in `src/database/`.
- **`packages/geodata/`** — Geospatial utilities (simplification, resampling, DBSCAN clustering, simulation). Source in `src/geodata/`. CLI entry: `geodata.cli:main`.
- **`server/`** — FastAPI REST API. Routes in `routes/`, Pydantic schemas in `schemas/`.
- **`app/`** — Expo 54 React Native mobile app (TypeScript). File-based routing via expo-router. Local SQLite via Drizzle ORM.
- **`transit-lab/`** — Marimo interactive notebooks for visualization and prototyping. Multi-page app via `run_app.py`.
- **`infra/local/`** — Docker Compose for observability stack (Grafana, Tempo, Loki, Prometheus) and Valhalla routing engine.

**Dependency graph:** `database` ← `geodata` ← `{server, transit-lab}`. Editable installs via `uv.sources` in each `pyproject.toml`.

## Common Commands

```bash
# Initial setup (installs uv, Python 3.14, creates venvs, runs migrations)
./setup.sh

# Server
cd server && uv run uvicorn main:app --reload --port 8000
# API docs at http://localhost:8000/docs

# Tests (server)
cd server && uv run pytest                     # all tests
cd server && uv run pytest tests/test_lines.py  # single file
cd server && uv run pytest -k test_create_line  # single test

# Tests (geodata)
cd packages/geodata && uv run pytest

# Lint (Python — all subprojects use ruff)
cd server && uv run ruff check . --fix
cd packages/geodata && uv run ruff check . --fix

# Lint (mobile app)
cd app && npm run lint

# Database migrations
cd packages/database && uv run alembic upgrade head
cd packages/database && uv run alembic revision --autogenerate -m "description"

# Mobile app
cd app && npx expo start

# Marimo notebooks
cd transit-lab && uv run python run_app.py          # multi-page app (port 2718)
cd transit-lab && uv run marimo edit 01_tracks.py    # single notebook

# Geodata CLI
cd packages/geodata && uv run geodata simplify input.geojson output.geojson --epsilon 0.001

# Observability stack
cd infra/local && docker compose up -d
# Grafana at http://localhost:3000, Valhalla at http://localhost:8002
```

## Architecture

### Pipeline
1. Mobile app records GPS points + accelerometer → local SQLite
2. Batch upload to API → `TripSession` + `TripSessionPoint` in PostGIS
3. Map-matching (HMM via Valhalla) snaps traces to road network → `Trip`
4. Resampling to uniform 10m intervals, DBSCAN clustering of clean trips
5. Segment-level consensus route with confidence scores → `RouteEstimation` + `RouteSegment`
6. Community voting on uncertain segments → `SegmentVote`

### Key Models (packages/database/src/database/models/)
- **Line** — transit line definition with path geometry
- **TripSession / TripSessionPoint / TripSensorReading** — raw recorded data
- **Trip / TripPoint** — processed/matched traces
- **RouteEstimation / RouteSegment / SegmentVote** — reconstruction output and voting

All models use UUID primary keys. All geometries are WGS84 (SRID 4326).

## Tech Stack

- **Python 3.14**, managed by **uv** (each subproject has its own `.venv/`)
- **PostgreSQL + PostGIS**, **SQLModel + GeoAlchemy2**, **Alembic**
- **FastAPI** with OpenTelemetry instrumentation
- **Shapely** (geometry ops), **scikit-learn** (DBSCAN)
- **React Native 0.81 / Expo 54**, **TypeScript 5.9**, **NativeWind**, **Gluestack UI**
- **Marimo** notebooks with **pydeck** for geospatial viz

## Environment

Copy `.env.example` to `.env`. Key variables:
- `DATABASE_URL` — PostgreSQL connection string (e.g. `postgresql+psycopg://user@localhost:5432/cbba_mobility`)
- `OTLP_ENDPOINT` — OpenTelemetry collector (optional, `http://localhost:4317`)
