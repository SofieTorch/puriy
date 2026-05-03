"""add draft status to linestatus enum

Revision ID: 988b1f509901
Revises: 5dbc73772968
Create Date: 2026-05-01 15:51:11.871490

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '988b1f509901'
down_revision: Union[str, None] = '5dbc73772968'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE linestatus ADD VALUE IF NOT EXISTS 'DRAFT' BEFORE 'PENDING'")


def downgrade() -> None:
    # PostgreSQL doesn't support removing enum values; this is a one-way migration.
    pass
