"""add ramal_label to routes (gap #7 — ramales)

Revision ID: c0d1e2f3a4b5
Revises: b9c0d1e2f3a4
Create Date: 2026-05-03 17:00:00.000000

Internal grouping key on `routes` so the pipeline can distinguish
ramales (variants) of the same line. The first ramal a line gets is
"main"; any additional ramales detected by the clustering step get
"r2", "r3", … The label is never shown to users — the UI identifies
ramales by geometry + endpoint zones + street summary.

The partial unique index `(line_id, ramal_label) WHERE status !=
'superseded'` upgrades the previous "one active Route per line"
invariant (RF-19, see migration b9c0d1e2f3a4) to "one active Route per
(line, ramal)". Version chains continue to grow within the same
ramal_label slot via supersede.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = 'c0d1e2f3a4b5'
down_revision: Union[str, None] = 'b9c0d1e2f3a4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'routes',
        sa.Column(
            'ramal_label',
            sa.String(length=64),
            nullable=False,
            server_default='main',
        ),
    )
    op.create_index(
        'ix_routes_ramal_label',
        'routes',
        ['ramal_label'],
    )
    op.create_index(
        'uq_route_active_per_ramal',
        'routes',
        ['line_id', 'ramal_label'],
        unique=True,
        postgresql_where=sa.text("status != 'SUPERSEDED'"),
    )


def downgrade() -> None:
    op.drop_index('uq_route_active_per_ramal', table_name='routes')
    op.drop_index('ix_routes_ramal_label', table_name='routes')
    op.drop_column('routes', 'ramal_label')
