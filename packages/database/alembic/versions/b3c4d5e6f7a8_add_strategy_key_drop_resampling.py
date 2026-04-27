"""add strategy_key to routes, drop resampling tables

Revision ID: b3c4d5e6f7a8
Revises: a2f3b8c1d4e5
Create Date: 2026-04-26 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b3c4d5e6f7a8'
down_revision: Union[str, None] = 'a2f3b8c1d4e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('routes', sa.Column('strategy_key', sa.String(length=100), nullable=True))
    op.drop_table('resampled_trip_points')
    op.drop_table('resampled_trips')


def downgrade() -> None:
    op.create_table('resampled_trips',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('trip_id', sa.Uuid(), nullable=False),
        sa.Column('interval_meters', sa.Float(), nullable=False),
        sa.Column('match_score', sa.Float(), nullable=True),
        sa.Column('point_count', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['trip_id'], ['trips.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_resampled_trips_trip_id'), 'resampled_trips', ['trip_id'], unique=False)
    op.create_table('resampled_trip_points',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('resampled_trip_id', sa.Uuid(), nullable=False),
        sa.Column('point_index', sa.Integer(), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('latitude', sa.Float(), nullable=False),
        sa.Column('longitude', sa.Float(), nullable=False),
        sa.Column('point', sa.Column(sa.LargeBinary()), nullable=True),
        sa.ForeignKeyConstraint(['resampled_trip_id'], ['resampled_trips.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_resampled_trip_points_resampled_trip_id'), 'resampled_trip_points', ['resampled_trip_id'], unique=False)
    op.drop_column('routes', 'strategy_key')
