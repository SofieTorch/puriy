"""add source enum to fare_reports (registration vs confirmation)

Revision ID: f7a8b9c0d1e2
Revises: e6f7a8b9c0d1
Create Date: 2026-05-03 12:00:00.000000

Lets the API distinguish a fare amount the user typed (REGISTRATION)
from one they picked among already-reported options (CONFIRMATION).
The semantic difference is interesting for downstream analysis: a
confirmation carries more signal that the amount is "the going rate"
than a fresh registration does.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = 'f7a8b9c0d1e2'
down_revision: Union[str, None] = 'e6f7a8b9c0d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE TYPE faresource AS ENUM ('REGISTRATION', 'CONFIRMATION')")
    op.add_column(
        'fare_reports',
        sa.Column(
            'source',
            sa.Enum(
                'REGISTRATION', 'CONFIRMATION',
                name='faresource', create_type=False,
            ),
            nullable=False,
            server_default='REGISTRATION',
        ),
    )


def downgrade() -> None:
    op.drop_column('fare_reports', 'source')
    op.execute("DROP TYPE IF EXISTS faresource")
