"""initial import

Revision ID: 0003_initial_import
Revises: 0002_driver_sync_models
Create Date: 2026-06-16
"""

from alembic import op
import sqlalchemy as sa

revision = "0003_initial_import"
down_revision = "0002_driver_sync_models"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "config_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("olt_id", sa.Integer(), sa.ForeignKey("olts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("raw_config", sa.Text(), nullable=False),
        sa.Column("source_command", sa.String(120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "import_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("olt_id", sa.Integer(), sa.ForeignKey("olts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(40), nullable=False, server_default="preview"),
        sa.Column("raw_config_snapshot_id", sa.Integer(), sa.ForeignKey("config_snapshots.id", ondelete="CASCADE"), nullable=False),
        sa.Column("parsed_summary_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "vlans",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("olt_id", sa.Integer(), sa.ForeignKey("olts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("vlan_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(120), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.UniqueConstraint("olt_id", "vlan_id", name="uq_vlans_olt_vlan"),
    )
    op.create_table(
        "gpon_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("olt_id", sa.Integer(), sa.ForeignKey("olts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("profile_type", sa.String(40), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("upstream_rate", sa.Integer(), nullable=True),
        sa.Column("downstream_rate", sa.Integer(), nullable=True),
        sa.UniqueConstraint("olt_id", "profile_type", "name", name="uq_gpon_profiles_olt_type_name"),
    )
    op.create_table(
        "onu_types",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("olt_id", sa.Integer(), sa.ForeignKey("olts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("vendor_detected", sa.String(80), nullable=True),
        sa.Column("max_tcont", sa.Integer(), nullable=True),
        sa.Column("max_gemport", sa.Integer(), nullable=True),
        sa.Column("max_ports", sa.Integer(), nullable=True),
        sa.UniqueConstraint("olt_id", "name", name="uq_onu_types_olt_name"),
    )
    op.add_column("pon_ports", sa.Column("rack", sa.Integer(), nullable=True))
    op.add_column("pon_ports", sa.Column("shelf", sa.Integer(), nullable=True))
    op.add_column("pon_ports", sa.Column("interface_name", sa.String(80), nullable=True))
    op.create_index("ix_pon_ports_olt_interface", "pon_ports", ["olt_id", "interface_name"], unique=False)
    op.add_column("onus", sa.Column("imported_from_config", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("onus", sa.Column("auth_date", sa.DateTime(timezone=True), nullable=True))
    op.add_column("onus", sa.Column("raw_description", sa.Text(), nullable=True))
    op.add_column("onus", sa.Column("parsed_zone_name", sa.String(120), nullable=True))
    op.add_column("onus", sa.Column("parsed_nap_name", sa.String(120), nullable=True))
    op.add_column("onus", sa.Column("parsed_nap_port", sa.Integer(), nullable=True))
    op.add_column("onus", sa.Column("parsed_odn", sa.String(120), nullable=True))
    op.add_column("onus", sa.Column("source", sa.String(40), nullable=False, server_default="manual"))


def downgrade() -> None:
    op.drop_column("onus", "source")
    op.drop_column("onus", "parsed_odn")
    op.drop_column("onus", "parsed_nap_port")
    op.drop_column("onus", "parsed_nap_name")
    op.drop_column("onus", "parsed_zone_name")
    op.drop_column("onus", "raw_description")
    op.drop_column("onus", "auth_date")
    op.drop_column("onus", "imported_from_config")
    op.drop_index("ix_pon_ports_olt_interface", table_name="pon_ports")
    op.drop_column("pon_ports", "interface_name")
    op.drop_column("pon_ports", "shelf")
    op.drop_column("pon_ports", "rack")
    op.drop_table("onu_types")
    op.drop_table("gpon_profiles")
    op.drop_table("vlans")
    op.drop_table("import_jobs")
    op.drop_table("config_snapshots")
