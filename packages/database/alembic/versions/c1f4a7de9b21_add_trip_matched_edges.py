"""add trip matched edges

Revision ID: c1f4a7de9b21
Revises: b26a3efa8d68
Create Date: 2026-04-15 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "c1f4a7de9b21"
down_revision: Union[str, None] = "b26a3efa8d68"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "trip_matched_edges",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("trip_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("valhalla_edge_id", sa.BigInteger(), nullable=False),
        sa.Column("forward", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["trip_id"], ["trips.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("trip_id", "sequence", name="uq_trip_matched_edges_trip_sequence"),
    )
    op.create_index(op.f("ix_trip_matched_edges_trip_id"), "trip_matched_edges", ["trip_id"], unique=False)
    op.create_index(
        "ix_trip_matched_edges_valhalla_edge_id_forward",
        "trip_matched_edges",
        ["valhalla_edge_id", "forward"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_trip_matched_edges_valhalla_edge_id_forward", table_name="trip_matched_edges")
    op.drop_index(op.f("ix_trip_matched_edges_trip_id"), table_name="trip_matched_edges")
    op.drop_table("trip_matched_edges")
