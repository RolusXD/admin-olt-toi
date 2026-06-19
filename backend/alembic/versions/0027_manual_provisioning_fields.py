"""manual provisioning fields

Revision ID: 0027_manual_provisioning_fields
Revises: 0026_provisioning_preflight
Create Date: 2026-06-18 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0027_manual_provisioning_fields"
down_revision = "0026_provisioning_preflight"
branch_labels = None
depends_on = None

REAL_ZTE_TEMPLATE = """interface {pon_port_interface}
onu {onu_index} type {onu_type} sn {serial_number}
exit
interface {onu_interface}
name {onu_name_cli}
description {onu_description}
tcont 1 profile {speed_profile_up}
gemport 1 unicast tcont 1 dir both
gemport 1 traffic-limit downstream {speed_profile_down}
switchport mode hybrid vport 1
switchport vlan {vlan} tag vport 1
exit"""


def upgrade() -> None:
    op.add_column("provisioning_plans", sa.Column("onu_name", sa.String(length=160), nullable=True))
    op.add_column("provisioning_plans", sa.Column("onu_description", sa.Text(), nullable=True))
    op.execute(
        sa.text(
            """
            UPDATE provisioning_templates
            SET template_body = :template_body,
                commands = CASE WHEN commands IS NULL OR commands = '' THEN :template_body ELSE commands END
            WHERE vendor = 'ZTE'
              AND model = 'C300'
              AND (firmware = 'V1.2.5P3' OR firmware IS NULL)
              AND is_default = true
            """
        ).bindparams(template_body=REAL_ZTE_TEMPLATE)
    )


def downgrade() -> None:
    op.drop_column("provisioning_plans", "onu_description")
    op.drop_column("provisioning_plans", "onu_name")
