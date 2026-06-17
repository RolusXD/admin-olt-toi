"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-16
"""

from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "olts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False, unique=True),
        sa.Column("vendor", sa.String(40), nullable=False, server_default="ZTE"),
        sa.Column("model", sa.String(80), nullable=False, server_default="C300"),
        sa.Column("firmware", sa.String(80), nullable=False, server_default="V1.2.5P3"),
        sa.Column("ip_address", sa.String(64), nullable=False),
        sa.Column("telnet_port", sa.Integer(), nullable=False, server_default="23"),
        sa.Column("username", sa.String(120), nullable=False),
        sa.Column("password_encrypted", sa.Text(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="unknown"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "zones",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
    )
    op.create_table(
        "naps",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("zone_id", sa.Integer(), sa.ForeignKey("zones.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("capacity", sa.Integer(), nullable=False, server_default="8"),
        sa.Column("description", sa.Text(), nullable=True),
    )
    op.create_table(
        "pon_ports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("olt_id", sa.Integer(), sa.ForeignKey("olts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("slot", sa.Integer(), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
    )
    op.create_table(
        "onus",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("olt_id", sa.Integer(), sa.ForeignKey("olts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("pon_port_id", sa.Integer(), sa.ForeignKey("pon_ports.id", ondelete="SET NULL"), nullable=True),
        sa.Column("zone_id", sa.Integer(), sa.ForeignKey("zones.id", ondelete="SET NULL"), nullable=True),
        sa.Column("nap_id", sa.Integer(), sa.ForeignKey("naps.id", ondelete="SET NULL"), nullable=True),
        sa.Column("customer_name", sa.String(160), nullable=False),
        sa.Column("serial_number", sa.String(80), nullable=False, unique=True),
        sa.Column("onu_interface", sa.String(80), nullable=False),
        sa.Column("onu_type", sa.String(80), nullable=False),
        sa.Column("vlan", sa.Integer(), nullable=False),
        sa.Column("speed_profile", sa.String(80), nullable=False),
        sa.Column("nap_port", sa.Integer(), nullable=True),
        sa.Column("distance_m", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="unknown"),
        sa.Column("last_down_cause", sa.String(80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "onu_power_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("onu_id", sa.Integer(), sa.ForeignKey("onus.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rx_power", sa.Float(), nullable=False),
        sa.Column("tx_power", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "event_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("entity_type", sa.String(80), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "backup_files",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("olt_id", sa.Integer(), sa.ForeignKey("olts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("backup_files")
    op.drop_table("event_logs")
    op.drop_table("onu_power_history")
    op.drop_table("onus")
    op.drop_table("pon_ports")
    op.drop_table("naps")
    op.drop_table("zones")
    op.drop_table("olts")
