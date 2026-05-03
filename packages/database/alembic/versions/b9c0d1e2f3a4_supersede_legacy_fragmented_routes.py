"""supersede legacy multi-fragment active routes

Revision ID: b9c0d1e2f3a4
Revises: a8b9c0d1e2f3
Create Date: 2026-05-03 16:00:00.000000

Going forward the pipeline rejects any reconstruction that produces more
than one fragment (RF-19 / change detection design): the system only
publishes routes that fit in a single continuous polyline. This
migration enforces that invariant retroactively by marking any
pre-existing active route whose `fragment_count > 1` as SUPERSEDED, so
the reconstruction step can re-publish them as single-fragment when the
data supports it.
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'b9c0d1e2f3a4'
down_revision: Union[str, None] = 'a8b9c0d1e2f3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE routes
        SET status = 'SUPERSEDED'
        WHERE status != 'SUPERSEDED'
          AND fragment_count > 1
        """
    )


def downgrade() -> None:
    # No-op: we can't reliably distinguish routes superseded by this
    # migration from routes superseded organically.
    pass
