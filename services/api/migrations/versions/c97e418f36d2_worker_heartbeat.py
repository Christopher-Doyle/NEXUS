"""Track local worker liveness.

Revision ID: c97e418f36d2
Revises: 8a84e2d01a11
"""

import sqlalchemy as sa
from alembic import op

revision = "c97e418f36d2"
down_revision = "8a84e2d01a11"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "worker_heartbeat",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_worker_heartbeat_last_seen_at", "worker_heartbeat", ["last_seen_at"])


def downgrade() -> None:
    op.drop_index("ix_worker_heartbeat_last_seen_at", table_name="worker_heartbeat")
    op.drop_table("worker_heartbeat")
