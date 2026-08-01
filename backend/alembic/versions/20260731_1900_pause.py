"""Add pause tracking columns for live room timers."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260731_1900_pause"
down_revision: Union[str, Sequence[str], None] = "20260731_1845_opened_at"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("live_rooms") as batch:
        batch.add_column(sa.Column("paused_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(
            sa.Column("pause_accumulated_ms", sa.Integer(), nullable=False, server_default="0")
        )


def downgrade() -> None:
    with op.batch_alter_table("live_rooms") as batch:
        batch.drop_column("pause_accumulated_ms")
        batch.drop_column("paused_at")
