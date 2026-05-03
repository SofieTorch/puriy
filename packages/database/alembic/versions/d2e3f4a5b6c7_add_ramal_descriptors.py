"""add ramal_descriptors + ramal_descriptor_votes (gap #7 — descriptors)

Revision ID: d2e3f4a5b6c7
Revises: c1d2e3f4a5b6
Create Date: 2026-05-03 19:00:00.000000

User-submitted descriptors per ramal (Route) — distinguishing features
like "lleva banderines naranjas en frente" or "letrero con logo de
Univalle". The unique constraint on `(route_id, text_normalized)` plus
the vote-on-existing-first UI flow handles deduplication; the votes
table enforces one upvote per device.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = 'd2e3f4a5b6c7'
down_revision: Union[str, None] = 'c1d2e3f4a5b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'ramal_descriptors',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('route_id', sa.Uuid(), nullable=False),
        sa.Column('text', sa.String(length=200), nullable=False),
        sa.Column('text_normalized', sa.String(length=200), nullable=False),
        sa.Column('votes_count', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_by_device_id', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['route_id'], ['routes.id']),
        sa.ForeignKeyConstraint(['created_by_device_id'], ['devices.id']),
        sa.UniqueConstraint(
            'route_id', 'text_normalized',
            name='uq_ramal_descriptor_route_text',
        ),
    )
    op.create_index(
        'ix_ramal_descriptors_route_id', 'ramal_descriptors', ['route_id'],
    )
    op.create_index(
        'ix_ramal_descriptors_created_by_device_id',
        'ramal_descriptors', ['created_by_device_id'],
    )

    op.create_table(
        'ramal_descriptor_votes',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('descriptor_id', sa.Uuid(), nullable=False),
        sa.Column('device_id', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['descriptor_id'], ['ramal_descriptors.id']),
        sa.ForeignKeyConstraint(['device_id'], ['devices.id']),
        sa.UniqueConstraint(
            'descriptor_id', 'device_id',
            name='uq_ramal_descriptor_vote_device',
        ),
    )
    op.create_index(
        'ix_ramal_descriptor_votes_descriptor_id',
        'ramal_descriptor_votes', ['descriptor_id'],
    )
    op.create_index(
        'ix_ramal_descriptor_votes_device_id',
        'ramal_descriptor_votes', ['device_id'],
    )


def downgrade() -> None:
    op.drop_index('ix_ramal_descriptor_votes_device_id', table_name='ramal_descriptor_votes')
    op.drop_index('ix_ramal_descriptor_votes_descriptor_id', table_name='ramal_descriptor_votes')
    op.drop_table('ramal_descriptor_votes')
    op.drop_index('ix_ramal_descriptors_created_by_device_id', table_name='ramal_descriptors')
    op.drop_index('ix_ramal_descriptors_route_id', table_name='ramal_descriptors')
    op.drop_table('ramal_descriptors')
