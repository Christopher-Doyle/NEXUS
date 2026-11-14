"""Persist per-task capabilities and network choice.

Revision ID: 9b4d321a7c10
Revises: 3a09b76f3488
"""
from alembic import op
import sqlalchemy as sa

revision = "9b4d321a7c10"
down_revision = "3a09b76f3488"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("task", sa.Column("capabilities_json", sa.Text(), nullable=False, server_default="[]"))
    op.add_column("task", sa.Column("network_access", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column("task", "network_access")
    op.drop_column("task", "capabilities_json")
