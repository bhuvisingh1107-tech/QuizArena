"""Add response_time_ms and status to responses (answer submission module)."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260731_1536_response_submit"
down_revision: Union[str, Sequence[str], None] = "de7d957eccec"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("responses") as batch:
        batch.add_column(sa.Column("response_time_ms", sa.Integer(), nullable=True))
        batch.add_column(
            sa.Column(
                "status",
                sa.String(length=32),
                nullable=False,
                server_default="submitted",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("responses") as batch:
        batch.drop_column("status")
        batch.drop_column("response_time_ms")
