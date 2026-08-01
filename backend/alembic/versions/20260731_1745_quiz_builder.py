"""Add question explanation + support quiz builder workflow."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260731_1745_quiz_builder"
down_revision: Union[str, Sequence[str], None] = "20260731_1545_scoring"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("questions") as batch:
        batch.add_column(sa.Column("explanation", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("questions") as batch:
        batch.drop_column("explanation")
