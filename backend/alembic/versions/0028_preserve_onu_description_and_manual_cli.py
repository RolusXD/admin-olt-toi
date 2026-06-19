"""preserve onu description and manual zte cli

Revision ID: 0028_preserve_onu_description
Revises: 0027_manual_provisioning_fields
Create Date: 2026-06-18
"""

from alembic import op
import sqlalchemy as sa


revision = "0028_preserve_onu_description"
down_revision = "0027_manual_provisioning_fields"
branch_labels = None
depends_on = None


ZTE_TEMPLATE = """interface {pon_port_interface}
onu {onu_index} type {onu_type} sn {serial_number}
exit
interface {onu_interface}
name {customer_name_cli}
description {description_generated}
tcont 1 profile {speed_profile_up}
gemport 1 unicast tcont 1 dir both
gemport 1 traffic-limit downstream {speed_profile_down}
switchport mode hybrid vport 1
switchport vlan {vlan} tag vport 1
exit
pon-onu-mng {onu_interface}
loop-detect ethuni {ethernet_port} enable
flow mode 1 tag-filter vid-filter untag-filter discard
flow 1 priority 0 vid {vlan}
gemport 1 flow 1
switchport-bind switch_0/1 veip 1
vlan port {ethernet_port} mode {vlan_lan_mode} vlan {vlan}
dhcp-ip ethuni {ethernet_port} {dhcp_mode}
security-mng 998 state enable mode permit ingress-type lan protocol web https
security-mng 999 state enable ingress-type lan protocol ftp telnet ssh snmp tr069
exit"""


def upgrade() -> None:
    op.add_column("vlans", sa.Column("is_default_for_provisioning", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("onu_types", sa.Column("is_default_for_provisioning", sa.Boolean(), nullable=False, server_default=sa.false()))

    for table in ("onus", "provisioning_plans"):
        op.add_column(table, sa.Column("description_original", sa.Text(), nullable=True))
        op.add_column(table, sa.Column("description_generated", sa.Text(), nullable=True))
        op.add_column(table, sa.Column("zone_name", sa.String(length=120), nullable=True))
        op.add_column(table, sa.Column("address_reference", sa.Text(), nullable=True))
        op.add_column(table, sa.Column("nap_name", sa.String(length=120), nullable=True))
        op.add_column(table, sa.Column("nap_port_label", sa.String(length=40), nullable=True))
        op.add_column(table, sa.Column("odb_name", sa.String(length=160), nullable=True))
        op.add_column(table, sa.Column("external_id", sa.String(length=160), nullable=True))
        op.add_column(table, sa.Column("description_parse_status", sa.String(length=40), nullable=True))
        op.add_column(table, sa.Column("description_parse_warnings", sa.Text(), nullable=True))

    op.add_column("provisioning_plans", sa.Column("onu_mode", sa.String(length=30), nullable=False, server_default="router"))
    op.add_column("provisioning_plans", sa.Column("vlan_lan_mode", sa.String(length=30), nullable=False, server_default="tag"))
    op.add_column("provisioning_plans", sa.Column("ethernet_port", sa.String(length=40), nullable=False, server_default="eth_0/1"))
    op.add_column("provisioning_plans", sa.Column("dhcp_mode", sa.String(length=40), nullable=False, server_default="from-internet"))
    op.add_column("provisioning_plans", sa.Column("allow_manual_onu_id", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.alter_column("provisioning_plans", "nap_port", existing_type=sa.Integer(), nullable=True)

    op.execute("UPDATE onus SET description_original = raw_description WHERE description_original IS NULL")
    op.execute("UPDATE onus SET zone_name = parsed_zone_name WHERE zone_name IS NULL")
    op.execute("UPDATE onus SET nap_name = parsed_nap_name WHERE nap_name IS NULL")
    op.execute("UPDATE onus SET nap_port_label = CAST(parsed_nap_port AS TEXT) WHERE nap_port_label IS NULL AND parsed_nap_port IS NOT NULL")
    op.execute("UPDATE onus SET odb_name = parsed_odn WHERE odb_name IS NULL")

    escaped = ZTE_TEMPLATE.replace("'", "''")
    op.execute(
        f"UPDATE provisioning_templates SET template_body = '{escaped}', commands = '{escaped}' "
        "WHERE vendor = 'ZTE' AND model = 'C300' AND is_default = true"
    )


def downgrade() -> None:
    op.alter_column("provisioning_plans", "nap_port", existing_type=sa.Integer(), nullable=False)
    op.drop_column("provisioning_plans", "allow_manual_onu_id")
    op.drop_column("provisioning_plans", "dhcp_mode")
    op.drop_column("provisioning_plans", "ethernet_port")
    op.drop_column("provisioning_plans", "vlan_lan_mode")
    op.drop_column("provisioning_plans", "onu_mode")

    for table in ("provisioning_plans", "onus"):
        op.drop_column(table, "description_parse_warnings")
        op.drop_column(table, "description_parse_status")
        op.drop_column(table, "external_id")
        op.drop_column(table, "odb_name")
        op.drop_column(table, "nap_port_label")
        op.drop_column(table, "nap_name")
        op.drop_column(table, "address_reference")
        op.drop_column(table, "zone_name")
        op.drop_column(table, "description_generated")
        op.drop_column(table, "description_original")

    op.drop_column("onu_types", "is_default_for_provisioning")
    op.drop_column("vlans", "is_default_for_provisioning")
