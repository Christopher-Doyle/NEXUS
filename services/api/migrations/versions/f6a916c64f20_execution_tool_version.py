"""Persist the registered tool version in execution receipts.

Revision ID: f6a916c64f20
Revises: a721d11d5509
"""

import sqlalchemy as sa
from alembic import op

revision = "f6a916c64f20"
down_revision = "a721d11d5509"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("execution", sa.Column("tool_version", sa.String(length=32), nullable=False, server_default="1"))


def downgrade() -> None:
    op.drop_column("execution", "tool_version")
