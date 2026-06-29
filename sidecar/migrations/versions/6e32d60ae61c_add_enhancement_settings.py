"""add enhancement settings

Revision ID: 6e32d60ae61c
Revises: 0eaa9e275559
Create Date: 2026-06-29 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "6e32d60ae61c"
down_revision: str | Sequence[str] | None = "0eaa9e275559"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("settings", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("local_contrast", sa.Float(), nullable=False, server_default="0")
        )
        batch_op.add_column(sa.Column("sharpness", sa.Float(), nullable=False, server_default="0"))
        batch_op.add_column(
            sa.Column("grayscale", sa.Boolean(), nullable=False, server_default=sa.false())
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("settings", schema=None) as batch_op:
        batch_op.drop_column("grayscale")
        batch_op.drop_column("sharpness")
        batch_op.drop_column("local_contrast")
