"""add last_compared_at to routes (RF-19 significant change detection)

Revision ID: a8b9c0d1e2f3
Revises: f7a8b9c0d1e2
Create Date: 2026-05-03 14:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = 'a8b9c0d1e2f3'
down_revision: Union[str, None] = 'f7a8b9c0d1e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'routes',
        sa.Column('last_compared_at', sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('routes', 'last_compared_at')
