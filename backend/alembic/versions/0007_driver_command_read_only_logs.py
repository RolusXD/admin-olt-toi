"""add read only command log metadata

Revision ID: 0007_command_read_logs
Revises: 0006_onu_monitoring_fields
Create Date: 2026-06-16
"""

from alembic import op
import sqlalchemy as sa

revision = "0007_command_read_logs"
down_revision = "0006_onu_monitoring_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("driver_command_logs", sa.Column("read_only", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("driver_command_logs", sa.Column("duration_ms", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("driver_command_logs", "duration_ms")
    op.drop_column("driver_command_logs", "read_only")
