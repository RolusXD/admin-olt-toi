"""sync uplinks from show interface

Revision ID: 0025_sync_uplinks_show_interface
Revises: 0024_real_technical_sync
Create Date: 2026-06-18 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0025_sync_uplinks_show_interface"
down_revision = "0024_real_technical_sync"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("olt_uplinks", sa.Column("line_protocol", sa.String(length=30), nullable=False, server_default="unknown"))
    op.add_column("olt_uplinks", sa.Column("speed_kbps", sa.Integer(), nullable=True))
    op.add_column("olt_uplinks", sa.Column("raw_output", sa.Text(), nullable=True))
    op.add_column("olt_uplinks", sa.Column("sync_source", sa.String(length=80), nullable=True))


def downgrade() -> None:
    op.drop_column("olt_uplinks", "sync_source")
    op.drop_column("olt_uplinks", "raw_output")
    op.drop_column("olt_uplinks", "speed_kbps")
    op.drop_column("olt_uplinks", "line_protocol")
