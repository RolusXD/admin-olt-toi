"""add onu discovery

Revision ID: 0013_onu_discovery
Revises: 0012_backfill_import_sources
Create Date: 2026-06-17
"""

from alembic import op
import sqlalchemy as sa


revision = "0013_onu_discovery"
down_revision = "0012_backfill_import_sources"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("unauthorized_onus", sa.Column("olt_code_snapshot", sa.String(length=80), nullable=True))
    op.add_column("unauthorized_onus", sa.Column("pon_type", sa.String(length=30), nullable=True))
    op.add_column("unauthorized_onus", sa.Column("slot", sa.Integer(), nullable=True))
    op.add_column("unauthorized_onus", sa.Column("port", sa.Integer(), nullable=True))
    op.add_column("unauthorized_onus", sa.Column("pon_port_interface", sa.String(length=80), nullable=True))
    op.add_column("unauthorized_onus", sa.Column("detected_type", sa.String(length=80), nullable=True))
    op.add_column("unauthorized_onus", sa.Column("detected_vendor", sa.String(length=80), nullable=True))
    op.add_column("unauthorized_onus", sa.Column("raw_output", sa.Text(), nullable=True))
    op.add_column("unauthorized_onus", sa.Column("times_detected", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("unauthorized_onus", sa.Column("notes", sa.Text(), nullable=True))
    op.add_column("unauthorized_onus", sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False))
    op.add_column("unauthorized_onus", sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False))

    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            update unauthorized_onus
            set
              olt_code_snapshot = olts.olt_code,
              pon_port_interface = coalesce(unauthorized_onus.interface, unauthorized_onus.pon_port_interface),
              status = case when unauthorized_onus.status = 'detected' then 'pending' else unauthorized_onus.status end
            from olts
            where unauthorized_onus.olt_id = olts.id
            """
        )
    )

    op.create_unique_constraint("uq_unauthorized_onus_olt_serial", "unauthorized_onus", ["olt_id", "serial_number"])
    op.create_table(
        "unauthorized_onu_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("unauthorized_onu_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["unauthorized_onu_id"], ["unauthorized_onus.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("unauthorized_onu_events")
    op.drop_constraint("uq_unauthorized_onus_olt_serial", "unauthorized_onus", type_="unique")
    op.drop_column("unauthorized_onus", "updated_at")
    op.drop_column("unauthorized_onus", "created_at")
    op.drop_column("unauthorized_onus", "notes")
    op.drop_column("unauthorized_onus", "times_detected")
    op.drop_column("unauthorized_onus", "raw_output")
    op.drop_column("unauthorized_onus", "detected_vendor")
    op.drop_column("unauthorized_onus", "detected_type")
    op.drop_column("unauthorized_onus", "pon_port_interface")
    op.drop_column("unauthorized_onus", "port")
    op.drop_column("unauthorized_onus", "slot")
    op.drop_column("unauthorized_onus", "pon_type")
    op.drop_column("unauthorized_onus", "olt_code_snapshot")
