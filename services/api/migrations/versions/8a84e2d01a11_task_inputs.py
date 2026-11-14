"""Record task input file names.

Revision ID: 8a84e2d01a11
Revises: 9b4d321a7c10
"""
from alembic import op
import sqlalchemy as sa

revision = "8a84e2d01a11"
down_revision = "9b4d321a7c10"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("task", sa.Column("input_files_json", sa.Text(), nullable=False, server_default="[]"))


def downgrade() -> None:
    op.drop_column("task", "input_files_json")
