"""Bound task wall-clock execution.

Revision ID: e480fbe981af
Revises: c97e418f36d2
"""

import sqlalchemy as sa
from alembic import op

revision = "e480fbe981af"
down_revision = "c97e418f36d2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("task", sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("task", "deadline_at")
