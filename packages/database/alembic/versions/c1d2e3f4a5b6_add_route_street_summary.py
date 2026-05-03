"""add street_summary + endpoint_zones to routes (gap #7 — ramales)

Revision ID: c1d2e3f4a5b6
Revises: c0d1e2f3a4b5
Create Date: 2026-05-03 18:00:00.000000

Two JSONB columns on `routes` populated by `_save_reconstruction`:

- `street_summary` — list of street/avenue names the route runs
  along, in order, derived from Valhalla `trace_match` edge names
  filtered by minimum run length.
- `endpoint_zones` — `[start_zone, end_zone]` neighbourhood names
  for the first/last polyline points, reverse-geocoded via Nominatim.

Both are nullable because they're populated lazily on the next
reconstruction run; existing routes from before this migration get
populated when the line is next reconstructed.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = 'c1d2e3f4a5b6'
down_revision: Union[str, None] = 'c0d1e2f3a4b5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'routes',
        sa.Column('street_summary', postgresql.JSONB(), nullable=True),
    )
    op.add_column(
        'routes',
        sa.Column('endpoint_zones', postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('routes', 'endpoint_zones')
    op.drop_column('routes', 'street_summary')
