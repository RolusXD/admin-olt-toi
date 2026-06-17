"""add olt connection type

Revision ID: 0008_olt_conn_type
Revises: 0007_command_read_logs
Create Date: 2026-06-16
"""

from alembic import op
import sqlalchemy as sa


revision = "0008_olt_conn_type"
down_revision = "0007_command_read_logs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "olts",
        sa.Column("connection_type", sa.String(length=30), nullable=False, server_default="telnet"),
    )


def downgrade() -> None:
    op.drop_column("olts", "connection_type")
