"""add onu monitoring fields

Revision ID: 0006_onu_monitoring_fields
Revises: 0005_onu_speed_profiles
Create Date: 2026-06-16
"""

from alembic import op
import sqlalchemy as sa

revision = "0006_onu_monitoring_fields"
down_revision = "0005_onu_speed_profiles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("onus", sa.Column("rx_power", sa.Float(), nullable=True))
    op.add_column("onus", sa.Column("tx_power", sa.Float(), nullable=True))
    op.add_column("onus", sa.Column("signal_status", sa.String(30), nullable=True))
    op.add_column("onus", sa.Column("last_monitored_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("onus", "last_monitored_at")
    op.drop_column("onus", "signal_status")
    op.drop_column("onus", "tx_power")
    op.drop_column("onus", "rx_power")
