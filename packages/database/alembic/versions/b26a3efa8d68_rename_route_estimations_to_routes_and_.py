"""rename route_estimations to routes and drop line path

Revision ID: b26a3efa8d68
Revises: bbecc02c5c6a
Create Date: 2026-04-07 23:18:31.695431

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from geoalchemy2 import Geometry

# revision identifiers, used by Alembic.
revision: str = 'b26a3efa8d68'
down_revision: Union[str, None] = 'bbecc02c5c6a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Rename route_estimations → routes
    op.rename_table('route_estimations', 'routes')

    # 2. Rename enums: estimationstatus → routestatus, estimationsource → routesource
    op.execute("ALTER TYPE estimationstatus RENAME TO routestatus")
    op.execute("ALTER TYPE estimationsource RENAME TO routesource")

    # 3. Rename estimation_id → route_id in route_edges
    op.drop_constraint('route_edges_estimation_id_fkey', 'route_edges', type_='foreignkey')
    op.drop_index('ix_route_edges_estimation_id', table_name='route_edges')
    op.alter_column('route_edges', 'estimation_id', new_column_name='route_id')
    op.create_foreign_key(None, 'route_edges', 'routes', ['route_id'], ['id'])
    op.create_index(op.f('ix_route_edges_route_id'), 'route_edges', ['route_id'], unique=False)

    # 4. Rename the old index on routes.line_id
    op.drop_index('ix_route_estimations_line_id', table_name='routes')
    op.create_index(op.f('ix_routes_line_id'), 'routes', ['line_id'], unique=False)

    # 5. Drop lines.path column
    op.drop_geospatial_index('idx_lines_path', table_name='lines', postgresql_using='gist', column_name='path')
    op.drop_column('lines', 'path')


def downgrade() -> None:
    # 1. Re-add lines.path
    op.add_geospatial_column(
        'lines',
        sa.Column(
            'path',
            Geometry(geometry_type='LINESTRING', srid=4326, spatial_index=False,
                     from_text='ST_GeomFromEWKT', name='geometry'),
            nullable=True,
        ),
    )
    op.create_geospatial_index('idx_lines_path', 'lines', ['path'], unique=False, postgresql_using='gist')

    # 2. Rename route_id → estimation_id in route_edges
    op.drop_constraint(None, 'route_edges', type_='foreignkey')
    op.drop_index(op.f('ix_route_edges_route_id'), table_name='route_edges')
    op.alter_column('route_edges', 'route_id', new_column_name='estimation_id')
    op.create_foreign_key('route_edges_estimation_id_fkey', 'route_edges', 'route_estimations', ['estimation_id'], ['id'])
    op.create_index('ix_route_edges_estimation_id', 'route_edges', ['estimation_id'], unique=False)

    # 3. Rename enums back
    op.execute("ALTER TYPE routestatus RENAME TO estimationstatus")
    op.execute("ALTER TYPE routesource RENAME TO estimationsource")

    # 4. Rename routes → route_estimations
    op.rename_table('routes', 'route_estimations')
