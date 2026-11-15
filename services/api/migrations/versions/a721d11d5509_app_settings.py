"""Store local model and deadline preferences.

Revision ID: a721d11d5509
Revises: e480fbe981af
"""

import sqlalchemy as sa
from alembic import op

revision = "a721d11d5509"
down_revision = "e480fbe981af"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "app_setting",
        sa.Column("key", sa.String(length=64), primary_key=True),
        sa.Column("value", sa.String(length=256), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("app_setting")
