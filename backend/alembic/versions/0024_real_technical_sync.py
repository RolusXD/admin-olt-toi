"""real technical read-only sync fields

Revision ID: 0024_real_technical_sync
Revises: 0023_technical_catalogs
Create Date: 2026-06-18 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0024_real_technical_sync"
down_revision = "0023_technical_catalogs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("pon_ports", sa.Column("online_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("pon_ports", sa.Column("offline_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("pon_ports", sa.Column("total_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("pon_ports", sa.Column("occupancy_percent", sa.Float(), nullable=False, server_default="0"))
    op.add_column("pon_ports", sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("pon_ports", sa.Column("sync_source", sa.String(length=80), nullable=True))
    op.add_column("olt_cards", sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("olt_cards", sa.Column("sync_source", sa.String(length=80), nullable=True))


def downgrade() -> None:
    op.drop_column("olt_cards", "sync_source")
    op.drop_column("olt_cards", "last_sync_at")
    op.drop_column("pon_ports", "sync_source")
    op.drop_column("pon_ports", "last_sync_at")
    op.drop_column("pon_ports", "occupancy_percent")
    op.drop_column("pon_ports", "total_count")
    op.drop_column("pon_ports", "offline_count")
    op.drop_column("pon_ports", "online_count")
