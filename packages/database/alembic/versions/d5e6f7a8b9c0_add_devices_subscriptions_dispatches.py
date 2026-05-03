"""add devices, line_subscriptions, notification_dispatches; FK device_id

Revision ID: d5e6f7a8b9c0
Revises: 988b1f509901
Create Date: 2026-05-02 17:00:00.000000

Centralizes device metadata in a new `devices` table. Backfills it from
every distinct `device_id` previously seen in trip_sessions / edge_votes /
line_votes / fare_reports, then adds foreign-key constraints on those
columns. Also adds line_subscriptions (commute → push targets) and
notification_dispatches (3-then-coalesce log).
"""
from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel
from alembic import op


revision: str = 'd5e6f7a8b9c0'
down_revision: Union[str, None] = '988b1f509901'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---- devices ----
    op.create_table(
        'devices',
        sa.Column('id', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.Column('expo_push_token', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
        sa.Column(
            'platform',
            sa.Enum('IOS', 'ANDROID', name='platform'),
            nullable=True,
        ),
        sa.Column('locale', sqlmodel.sql.sqltypes.AutoString(length=16), nullable=True),
        sa.Column('last_seen_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )

    # ---- backfill devices from existing device_id columns ----
    # Each distinct device_id seen in any of the four tables gets a row with
    # platform / token NULL. NOW() is used for last_seen_at and created_at —
    # we have no better timestamp for legacy rows.
    op.execute("""
        INSERT INTO devices (id, last_seen_at, created_at)
        SELECT DISTINCT device_id, NOW(), NOW()
        FROM (
            SELECT device_id FROM trip_sessions WHERE device_id IS NOT NULL
            UNION
            SELECT device_id FROM edge_votes
            UNION
            SELECT device_id FROM line_votes
            UNION
            SELECT device_id FROM fare_reports
        ) AS all_device_ids
        ON CONFLICT (id) DO NOTHING
    """)

    # ---- FK constraints on existing tables ----
    op.create_foreign_key(
        'fk_trip_sessions_device_id_devices',
        'trip_sessions', 'devices', ['device_id'], ['id'],
        ondelete='RESTRICT',
    )
    op.create_foreign_key(
        'fk_edge_votes_device_id_devices',
        'edge_votes', 'devices', ['device_id'], ['id'],
        ondelete='RESTRICT',
    )
    op.create_foreign_key(
        'fk_line_votes_device_id_devices',
        'line_votes', 'devices', ['device_id'], ['id'],
        ondelete='RESTRICT',
    )
    op.create_foreign_key(
        'fk_fare_reports_device_id_devices',
        'fare_reports', 'devices', ['device_id'], ['id'],
        ondelete='RESTRICT',
    )

    # ---- line_subscriptions ----
    op.create_table(
        'line_subscriptions',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('device_id', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.Column('line_id', sa.Uuid(), nullable=False),
        sa.Column(
            'kind',
            sa.Enum('COMMUTE', name='subscriptionkind'),
            nullable=False,
        ),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['device_id'], ['devices.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['line_id'], ['lines.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'device_id', 'line_id', 'kind',
            name='uq_line_subscription_device_line_kind',
        ),
    )
    op.create_index(
        op.f('ix_line_subscriptions_device_id'),
        'line_subscriptions', ['device_id'], unique=False,
    )
    op.create_index(
        op.f('ix_line_subscriptions_line_id'),
        'line_subscriptions', ['line_id'], unique=False,
    )

    # ---- notification_dispatches ----
    op.create_table(
        'notification_dispatches',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('device_id', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.Column('line_id', sa.Uuid(), nullable=False),
        sa.Column('detour_id', sa.Uuid(), nullable=True),
        sa.Column(
            'kind',
            sa.Enum('DETOUR_INDIVIDUAL', 'DETOUR_COALESCED', name='notificationkind'),
            nullable=False,
        ),
        sa.Column('sent_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['device_id'], ['devices.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['line_id'], ['lines.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['detour_id'], ['detours.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_notification_dispatches_device_id'),
        'notification_dispatches', ['device_id'], unique=False,
    )
    op.create_index(
        op.f('ix_notification_dispatches_line_id'),
        'notification_dispatches', ['line_id'], unique=False,
    )
    op.create_index(
        op.f('ix_notification_dispatches_detour_id'),
        'notification_dispatches', ['detour_id'], unique=False,
    )
    op.create_index(
        op.f('ix_notification_dispatches_sent_at'),
        'notification_dispatches', ['sent_at'], unique=False,
    )


def downgrade() -> None:
    # Drop new tables (which also drops their FKs)
    op.drop_index(op.f('ix_notification_dispatches_sent_at'), table_name='notification_dispatches')
    op.drop_index(op.f('ix_notification_dispatches_detour_id'), table_name='notification_dispatches')
    op.drop_index(op.f('ix_notification_dispatches_line_id'), table_name='notification_dispatches')
    op.drop_index(op.f('ix_notification_dispatches_device_id'), table_name='notification_dispatches')
    op.drop_table('notification_dispatches')

    op.drop_index(op.f('ix_line_subscriptions_line_id'), table_name='line_subscriptions')
    op.drop_index(op.f('ix_line_subscriptions_device_id'), table_name='line_subscriptions')
    op.drop_table('line_subscriptions')

    # Drop FK constraints on existing tables
    op.drop_constraint('fk_fare_reports_device_id_devices', 'fare_reports', type_='foreignkey')
    op.drop_constraint('fk_line_votes_device_id_devices', 'line_votes', type_='foreignkey')
    op.drop_constraint('fk_edge_votes_device_id_devices', 'edge_votes', type_='foreignkey')
    op.drop_constraint('fk_trip_sessions_device_id_devices', 'trip_sessions', type_='foreignkey')

    op.drop_table('devices')

    # Drop the enum types we created
    op.execute("DROP TYPE IF EXISTS notificationkind")
    op.execute("DROP TYPE IF EXISTS subscriptionkind")
    op.execute("DROP TYPE IF EXISTS platform")
