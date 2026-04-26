"""add line_type, route fragments, and fare tables

Revision ID: a2f3b8c1d4e5
Revises: 1a0e9e4ac5e0
Create Date: 2026-04-26 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import geoalchemy2
from geoalchemy2 import Geometry
import sqlmodel

# revision identifiers, used by Alembic.
revision: str = 'a2f3b8c1d4e5'
down_revision: Union[str, None] = '1a0e9e4ac5e0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Line type ---
    op.execute("CREATE TYPE linetype AS ENUM ('micro', 'trufi', 'taxi_trufi')")
    op.add_column('lines', sa.Column('line_type', sa.Enum('MICRO', 'TRUFI', 'TAXI_TRUFI', name='linetype', create_type=False), nullable=True))

    # --- Route fragment fields ---
    op.add_column('routes', sa.Column('fragment_index', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('routes', sa.Column('fragment_count', sa.Integer(), nullable=False, server_default='1'))

    # --- Fare zones ---
    op.create_table('fare_zones',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('name', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.Column('boundary', Geometry(geometry_type='MULTIPOLYGON', srid=4326, from_text='ST_GeomFromEWKT', name='geometry'), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name', name='uq_fare_zones_name'),
    )
    op.create_index(op.f('ix_fare_zones_name'), 'fare_zones', ['name'], unique=False)
    # Note: GeoAlchemy2 auto-creates a GiST spatial index on the boundary column

    # --- Fare reports ---
    op.create_table('fare_reports',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('line_id', sa.Uuid(), nullable=False),
        sa.Column('device_id', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.Column('session_id', sa.Uuid(), nullable=True),
        sa.Column('amount_bob', sa.Numeric(precision=6, scale=2), nullable=False),
        sa.Column('boarding_latitude', sa.Float(), nullable=False),
        sa.Column('boarding_longitude', sa.Float(), nullable=False),
        sa.Column('alighting_latitude', sa.Float(), nullable=False),
        sa.Column('alighting_longitude', sa.Float(), nullable=False),
        sa.Column('boarding_zone_id', sa.Uuid(), nullable=True),
        sa.Column('alighting_zone_id', sa.Uuid(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['line_id'], ['lines.id']),
        sa.ForeignKeyConstraint(['session_id'], ['trip_sessions.id']),
        sa.ForeignKeyConstraint(['boarding_zone_id'], ['fare_zones.id']),
        sa.ForeignKeyConstraint(['alighting_zone_id'], ['fare_zones.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_fare_reports_line_id'), 'fare_reports', ['line_id'], unique=False)
    op.create_index(op.f('ix_fare_reports_device_id'), 'fare_reports', ['device_id'], unique=False)
    op.create_index(op.f('ix_fare_reports_boarding_zone_id'), 'fare_reports', ['boarding_zone_id'], unique=False)
    op.create_index(op.f('ix_fare_reports_alighting_zone_id'), 'fare_reports', ['alighting_zone_id'], unique=False)


def downgrade() -> None:
    op.drop_table('fare_reports')
    op.drop_index(op.f('ix_fare_zones_name'), table_name='fare_zones')
    op.drop_table('fare_zones')
    op.drop_column('routes', 'fragment_count')
    op.drop_column('routes', 'fragment_index')
    op.drop_column('lines', 'line_type')
    op.execute("DROP TYPE linetype")
