"""Add scoring persistence fields (scored_at, participant counters)."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260731_1545_scoring"
down_revision: Union[str, Sequence[str], None] = "20260731_1536_response_submit"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("responses") as batch:
        batch.add_column(sa.Column("scored_at", sa.DateTime(timezone=True), nullable=True))

    with op.batch_alter_table("participants") as batch:
        batch.add_column(
            sa.Column("total_correct", sa.Integer(), nullable=False, server_default="0")
        )
        batch.add_column(
            sa.Column("total_incorrect", sa.Integer(), nullable=False, server_default="0")
        )
        batch.add_column(
            sa.Column("unanswered_count", sa.Integer(), nullable=False, server_default="0")
        )


def downgrade() -> None:
    with op.batch_alter_table("participants") as batch:
        batch.drop_column("unanswered_count")
        batch.drop_column("total_incorrect")
        batch.drop_column("total_correct")

    with op.batch_alter_table("responses") as batch:
        batch.drop_column("scored_at")
