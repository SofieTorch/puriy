"""add reduced_points to recording_sessions

Revision ID: add_reduced_points
Revises: 0775b27e0935
Create Date: 2026-03-11

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "add_reduced_points"
down_revision: Union[str, None] = "remove_users_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "recording_sessions",
        sa.Column("reduced_points", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("recording_sessions", "reduced_points")
