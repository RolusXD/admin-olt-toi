"""technical catalogs and olt management

Revision ID: 0023_technical_catalogs
Revises: 0022_onu_type_alias
Create Date: 2026-06-18 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0023_technical_catalogs"
down_revision = "0022_onu_type_alias"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("olts", sa.Column("hardware_version", sa.String(length=120), nullable=True))
    op.add_column("olts", sa.Column("software_version", sa.String(length=120), nullable=True))
    op.add_column("olts", sa.Column("pon_supported_types", sa.String(length=40), nullable=False, server_default="GPON"))
    op.add_column("olts", sa.Column("snmp_ro_community_encrypted", sa.Text(), nullable=True))
    op.add_column("olts", sa.Column("snmp_rw_community_encrypted", sa.Text(), nullable=True))
    op.add_column("olts", sa.Column("snmp_udp_port", sa.Integer(), nullable=False, server_default="161"))

    op.add_column("onu_types", sa.Column("pon_type", sa.String(length=30), nullable=False, server_default="GPON"))
    op.add_column("onu_types", sa.Column("channel_gpon", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("onu_types", sa.Column("channel_xgpon", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("onu_types", sa.Column("channel_xgspon", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("onu_types", sa.Column("allow_custom_profiles", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("onu_types", sa.Column("default_custom_profile_id", sa.Integer(), nullable=True))
    op.add_column("onu_types", sa.Column("capability_mode", sa.String(length=40), nullable=False, server_default="bridging"))
    op.create_foreign_key(
        "fk_onu_types_default_custom_profile",
        "onu_types",
        "profile_catalogs",
        ["default_custom_profile_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column("profile_catalogs", sa.Column("service_type", sa.String(length=40), nullable=False, server_default="internet"))
    op.add_column("profile_catalogs", sa.Column("speed_kbps", sa.Integer(), nullable=True))
    op.add_column("profile_catalogs", sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.execute("UPDATE profile_catalogs SET speed_kbps = COALESCE(maximum_kbps, pir_kbps)")

    op.add_column("pon_ports", sa.Column("pon_type", sa.String(length=30), nullable=False, server_default="GPON"))
    op.add_column("pon_ports", sa.Column("admin_status", sa.String(length=30), nullable=False, server_default="unknown"))
    op.add_column("pon_ports", sa.Column("oper_status", sa.String(length=30), nullable=False, server_default="unknown"))
    op.add_column("pon_ports", sa.Column("tx_power", sa.Float(), nullable=True))
    op.add_column("pon_ports", sa.Column("range_label", sa.String(length=80), nullable=True))

    op.create_table(
        "olt_cards",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("olt_id", sa.Integer(), nullable=False),
        sa.Column("slot_number", sa.String(length=40), nullable=False),
        sa.Column("card_type", sa.String(length=80), nullable=True),
        sa.Column("real_type", sa.String(length=80), nullable=True),
        sa.Column("port_count", sa.Integer(), nullable=True),
        sa.Column("firmware", sa.String(length=120), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="unknown"),
        sa.Column("role", sa.String(length=80), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["olt_id"], ["olts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("olt_id", "slot_number", name="uq_olt_cards_olt_slot"),
    )
    op.create_table(
        "olt_uplinks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("olt_id", sa.Integer(), nullable=False),
        sa.Column("interface_name", sa.String(length=80), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("interface_type", sa.String(length=40), nullable=True),
        sa.Column("admin_status", sa.String(length=30), nullable=False, server_default="unknown"),
        sa.Column("oper_status", sa.String(length=30), nullable=False, server_default="unknown"),
        sa.Column("negotiation", sa.String(length=80), nullable=True),
        sa.Column("mtu", sa.Integer(), nullable=True),
        sa.Column("mode", sa.String(length=40), nullable=True),
        sa.Column("allowed_vlans", sa.Text(), nullable=True),
        sa.Column("pvid_untag", sa.Integer(), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["olt_id"], ["olts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("olt_id", "interface_name", name="uq_olt_uplinks_olt_interface"),
    )
    op.create_table(
        "olt_technical_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("olt_id", sa.Integer(), nullable=False),
        sa.Column("show_disabled_onus", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("send_onu_description_to_olt", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("dhcp_option82_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("pppoe_plus_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("dhcp_snooping_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("ip_source_protection_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("max_mac_per_onu", sa.Integer(), nullable=False, server_default="8"),
        sa.Column("rx_warning_dbm", sa.Float(), nullable=False, server_default="-24"),
        sa.Column("rx_critical_dbm", sa.Float(), nullable=False, server_default="-27"),
        sa.Column("temperature_warning_c", sa.Float(), nullable=False, server_default="70"),
        sa.Column("temperature_critical_c", sa.Float(), nullable=False, server_default="80"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["olt_id"], ["olts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("olt_id", name="uq_olt_technical_settings_olt"),
    )


def downgrade() -> None:
    op.drop_table("olt_technical_settings")
    op.drop_table("olt_uplinks")
    op.drop_table("olt_cards")
    op.drop_column("pon_ports", "range_label")
    op.drop_column("pon_ports", "tx_power")
    op.drop_column("pon_ports", "oper_status")
    op.drop_column("pon_ports", "admin_status")
    op.drop_column("pon_ports", "pon_type")
    op.drop_column("profile_catalogs", "is_default")
    op.drop_column("profile_catalogs", "speed_kbps")
    op.drop_column("profile_catalogs", "service_type")
    op.drop_constraint("fk_onu_types_default_custom_profile", "onu_types", type_="foreignkey")
    op.drop_column("onu_types", "capability_mode")
    op.drop_column("onu_types", "default_custom_profile_id")
    op.drop_column("onu_types", "allow_custom_profiles")
    op.drop_column("onu_types", "channel_xgspon")
    op.drop_column("onu_types", "channel_xgpon")
    op.drop_column("onu_types", "channel_gpon")
    op.drop_column("onu_types", "pon_type")
    op.drop_column("olts", "snmp_udp_port")
    op.drop_column("olts", "snmp_rw_community_encrypted")
    op.drop_column("olts", "snmp_ro_community_encrypted")
    op.drop_column("olts", "pon_supported_types")
    op.drop_column("olts", "software_version")
    op.drop_column("olts", "hardware_version")
