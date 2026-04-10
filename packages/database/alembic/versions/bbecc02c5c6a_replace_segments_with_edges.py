"""replace segments with edges

Revision ID: bbecc02c5c6a
Revises: 39de34d1ee2a
Create Date: 2026-04-07 20:16:20.802033

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import sqlmodel.sql.sqltypes
import geoalchemy2
from geoalchemy2 import Geometry

# revision identifiers, used by Alembic.
revision: str = 'bbecc02c5c6a'
down_revision: Union[str, None] = '39de34d1ee2a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop old segment-based tables first (they reference the votechoice enum we want to reuse)
    op.drop_table('segment_votes')
    op.drop_table('travel_time_samples')
    op.drop_geospatial_index('idx_route_segments_path', table_name='route_segments', postgresql_using='gist', column_name='path')
    op.drop_table('route_segments')

    # Drop old enums no longer needed
    sa.Enum(name='segmentstatus').drop(op.get_bind())

    # Create new edge-based tables
    op.create_geospatial_table('route_edges',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('estimation_id', sa.Uuid(), nullable=False),
        sa.Column('sequence', sa.Integer(), nullable=False),
        sa.Column('valhalla_edge_id', sa.BigInteger(), nullable=True),
        sa.Column('forward', sa.Boolean(), nullable=False),
        sa.Column('path', Geometry(geometry_type='LINESTRING', srid=4326, dimension=2, spatial_index=False, from_text='ST_GeomFromEWKT', name='geometry'), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=False),
        sa.Column('status', sa.Enum('PENDING', 'CONFIRMED', name='edgestatus'), nullable=False),
        sa.Column('votes_for', sa.Integer(), nullable=False),
        sa.Column('votes_against', sa.Integer(), nullable=False),
        sa.Column('confirmed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['estimation_id'], ['route_estimations.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_geospatial_index('idx_route_edges_path', 'route_edges', ['path'], unique=False, postgresql_using='gist', postgresql_ops={})
    op.create_index(op.f('ix_route_edges_estimation_id'), 'route_edges', ['estimation_id'], unique=False)

    # Reuse existing votechoice enum
    votechoice = postgresql.ENUM('APPROVE', 'REJECT', name='votechoice', create_type=False)
    op.create_table('edge_votes',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('edge_id', sa.Uuid(), nullable=False),
        sa.Column('device_id', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.Column('vote', votechoice, nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['edge_id'], ['route_edges.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('edge_id', 'device_id', name='uq_edge_vote_device'),
    )
    op.create_index(op.f('ix_edge_votes_device_id'), 'edge_votes', ['device_id'], unique=False)
    op.create_index(op.f('ix_edge_votes_edge_id'), 'edge_votes', ['edge_id'], unique=False)

    # Re-create travel_time_samples with edge_id FK
    op.create_table('travel_time_samples',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('trip_id', sa.Uuid(), nullable=False),
        sa.Column('edge_id', sa.Uuid(), nullable=False),
        sa.Column('duration_seconds', sa.Float(), nullable=False),
        sa.Column('day_of_week', sa.Integer(), nullable=False),
        sa.Column('hour_of_day', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['trip_id'], ['trips.id']),
        sa.ForeignKeyConstraint(['edge_id'], ['route_edges.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_travel_time_samples_trip_id'), 'travel_time_samples', ['trip_id'], unique=False)
    op.create_index(op.f('ix_travel_time_samples_edge_id'), 'travel_time_samples', ['edge_id'], unique=False)

    # Add source column to route_estimations
    estimationsource = sa.Enum('COMPUTED', 'IMPORTED', name='estimationsource')
    estimationsource.create(op.get_bind())
    op.add_column('route_estimations', sa.Column('source', estimationsource, server_default='COMPUTED', nullable=False))
    # ### end Alembic commands ###


def downgrade() -> None:
    # Drop new tables
    op.drop_table('travel_time_samples')
    op.drop_index(op.f('ix_edge_votes_edge_id'), table_name='edge_votes')
    op.drop_index(op.f('ix_edge_votes_device_id'), table_name='edge_votes')
    op.drop_table('edge_votes')
    op.drop_index(op.f('ix_route_edges_estimation_id'), table_name='route_edges')
    op.drop_geospatial_index('idx_route_edges_path', table_name='route_edges', postgresql_using='gist', column_name='path')
    op.drop_geospatial_table('route_edges')

    op.drop_column('route_estimations', 'source')
    sa.Enum(name='estimationsource').drop(op.get_bind())

    # Recreate old segment tables
    segmentstatus = sa.Enum('PENDING', 'CONFIRMED', name='segmentstatus')
    segmentstatus.create(op.get_bind())

    op.create_geospatial_table('route_segments',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('estimation_id', sa.Uuid(), nullable=False),
        sa.Column('sequence', sa.Integer(), nullable=False),
        sa.Column('path', Geometry(geometry_type='LINESTRING', srid=4326, spatial_index=False, from_text='ST_GeomFromEWKT', name='geometry'), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=False),
        sa.Column('status', segmentstatus, nullable=False),
        sa.Column('votes_for', sa.Integer(), nullable=False),
        sa.Column('votes_against', sa.Integer(), nullable=False),
        sa.Column('confirmed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['estimation_id'], ['route_estimations.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_geospatial_index('idx_route_segments_path', 'route_segments', ['path'], unique=False, postgresql_using='gist')
    op.create_index(op.f('ix_route_segments_estimation_id'), 'route_segments', ['estimation_id'], unique=False)

    op.create_table('segment_votes',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('segment_id', sa.Uuid(), nullable=False),
        sa.Column('trip_id', sa.Uuid(), nullable=False),
        sa.Column('vote', sa.Enum('APPROVE', 'REJECT', name='votechoice'), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['segment_id'], ['route_segments.id']),
        sa.ForeignKeyConstraint(['trip_id'], ['trips.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_segment_votes_segment_id'), 'segment_votes', ['segment_id'], unique=False)
    op.create_index(op.f('ix_segment_votes_trip_id'), 'segment_votes', ['trip_id'], unique=False)

    op.create_table('travel_time_samples',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('trip_id', sa.Uuid(), nullable=False),
        sa.Column('segment_id', sa.Uuid(), nullable=False),
        sa.Column('duration_seconds', sa.Float(), nullable=False),
        sa.Column('day_of_week', sa.Integer(), nullable=False),
        sa.Column('hour_of_day', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['trip_id'], ['trips.id']),
        sa.ForeignKeyConstraint(['segment_id'], ['route_segments.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_travel_time_samples_trip_id'), 'travel_time_samples', ['trip_id'], unique=False)
    op.create_index(op.f('ix_travel_time_samples_segment_id'), 'travel_time_samples', ['segment_id'], unique=False)

    sa.Enum(name='edgestatus').drop(op.get_bind())
