"""remove users

Revision ID: remove_users_001
Revises: 0775b27e0935
Create Date: 2026-02-22

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "remove_users_001"
down_revision: Union[str, None] = "0775b27e0935"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index("ix_recording_sessions_user_id", table_name="recording_sessions")
    op.drop_column("recording_sessions", "user_id")

    op.drop_index("ix_lines_submitted_by_id", table_name="lines")
    op.drop_column("lines", "submitted_by_id")

    op.drop_index("ix_users_username", table_name="users")
    op.drop_table("users")


def downgrade() -> None:
    op.create_table(
        "users",
        sa.Column("username", sa.String(length=100), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)

    op.add_column("lines", sa.Column("submitted_by_id", sa.Integer(), nullable=True))
    op.create_index("ix_lines_submitted_by_id", "lines", ["submitted_by_id"])
    op.create_foreign_key(None, "lines", "users", ["submitted_by_id"], ["id"])

    op.add_column("recording_sessions", sa.Column("user_id", sa.Integer(), nullable=True))
    op.create_index("ix_recording_sessions_user_id", "recording_sessions", ["user_id"])
    op.create_foreign_key(None, "recording_sessions", "users", ["user_id"], ["id"])
