"""add match_attributes to trips

Persists the raw Valhalla trace_attributes (shape, edges with shape indices,
matched points) on each cleaned trip, so route reconstruction can rebuild the
exact routebuilder MatchedTrace — including per-edge corner refinement — without
re-querying Valhalla.

Revision ID: e3f4a5b6c7d8
Revises: d2e3f4a5b6c7
Create Date: 2026-06-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'e3f4a5b6c7d8'
down_revision: Union[str, None] = 'd2e3f4a5b6c7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'trips',
        sa.Column('match_attributes', postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('trips', 'match_attributes')
