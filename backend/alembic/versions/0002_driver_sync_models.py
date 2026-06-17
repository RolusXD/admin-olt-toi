"""driver sync models

Revision ID: 0002_driver_sync_models
Revises: 0001_initial
Create Date: 2026-06-16
"""

from alembic import op
import sqlalchemy as sa

revision = "0002_driver_sync_models"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "unauthorized_onus",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("olt_id", sa.Integer(), sa.ForeignKey("olts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("interface", sa.String(80), nullable=False),
        sa.Column("serial_number", sa.String(80), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="detected"),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "onu_event_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("onu_id", sa.Integer(), sa.ForeignKey("onus.id", ondelete="SET NULL"), nullable=True),
        sa.Column("olt_id", sa.Integer(), sa.ForeignKey("olts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("onu_interface", sa.String(80), nullable=False),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "provisioning_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False, unique=True),
        sa.Column("vendor", sa.String(40), nullable=False, server_default="ZTE"),
        sa.Column("model", sa.String(80), nullable=False, server_default="C300"),
        sa.Column("commands", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "driver_command_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("olt_id", sa.Integer(), sa.ForeignKey("olts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("command", sa.Text(), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("output_excerpt", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_unauthorized_onus_olt_serial", "unauthorized_onus", ["olt_id", "serial_number"])
    op.create_index("ix_onu_event_history_olt_interface", "onu_event_history", ["olt_id", "onu_interface"])


def downgrade() -> None:
    op.drop_index("ix_onu_event_history_olt_interface", table_name="onu_event_history")
    op.drop_index("ix_unauthorized_onus_olt_serial", table_name="unauthorized_onus")
    op.drop_table("driver_command_logs")
    op.drop_table("provisioning_templates")
    op.drop_table("onu_event_history")
    op.drop_table("unauthorized_onus")
