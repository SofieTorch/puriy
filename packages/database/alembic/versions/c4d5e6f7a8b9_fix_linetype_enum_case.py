"""rename linetype enum values to uppercase

The previous migration created the PG enum with lowercase values
('micro', 'trufi', 'taxi_trufi') but SQLAlchemy stores Python enums by
their *name* (uppercase), so every insert failed with
``invalid input value for enum linetype: "TRUFI"``. This brings the enum
into line with how ``linestatus`` was created.

Revision ID: c4d5e6f7a8b9
Revises: b3c4d5e6f7a8
Create Date: 2026-04-27 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = 'c4d5e6f7a8b9'
down_revision: Union[str, None] = 'b3c4d5e6f7a8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE linetype RENAME VALUE 'micro' TO 'MICRO'")
    op.execute("ALTER TYPE linetype RENAME VALUE 'trufi' TO 'TRUFI'")
    op.execute("ALTER TYPE linetype RENAME VALUE 'taxi_trufi' TO 'TAXI_TRUFI'")


def downgrade() -> None:
    op.execute("ALTER TYPE linetype RENAME VALUE 'MICRO' TO 'micro'")
    op.execute("ALTER TYPE linetype RENAME VALUE 'TRUFI' TO 'trufi'")
    op.execute("ALTER TYPE linetype RENAME VALUE 'TAXI_TRUFI' TO 'taxi_trufi'")
