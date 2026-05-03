"""add line_schedules table for inferred service hours and headway

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
Create Date: 2026-05-02 18:00:00.000000

One row per (line, day_bucket) — at most three buckets per line:
weekday, saturday, sunday. All schedule fields are nullable so a row
can carry only `service_start_at` / `service_end_at` when headway is
deemed unreliable (RF-24).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = 'e6f7a8b9c0d1'
down_revision: Union[str, None] = 'd5e6f7a8b9c0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'line_schedules',
        sa.Column('line_id', sa.Uuid(), nullable=False),
        sa.Column(
            'day_bucket',
            sa.Enum('WEEKDAY', 'SATURDAY', 'SUNDAY', name='daybucket'),
            nullable=False,
        ),
        sa.Column('service_start_at', sa.Time(), nullable=True),
        sa.Column('service_end_at', sa.Time(), nullable=True),
        sa.Column('headway_min', sa.Integer(), nullable=True),
        sa.Column('inferred_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['line_id'], ['lines.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('line_id', 'day_bucket'),
    )


def downgrade() -> None:
    op.drop_table('line_schedules')
    op.execute("DROP TYPE IF EXISTS daybucket")
