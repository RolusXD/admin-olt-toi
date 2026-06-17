"""provisioning dry run

Revision ID: 0017_provisioning_dry_run
Revises: 0016_backfill_env_snapshots
Create Date: 2026-06-17
"""

from alembic import op
import sqlalchemy as sa


revision = "0017_provisioning_dry_run"
down_revision = "0016_backfill_env_snapshots"
branch_labels = None
depends_on = None


DEFAULT_TEMPLATE = """interface {pon_port_interface}
onu {onu_index} type {onu_type} sn {serial_number}
exit
interface {onu_interface}
name {customer_name_cli}
description zone_{zone_name}_descr_Nap_{nap_name}_Puerto_{nap_port}
tcont 1 profile {speed_profile_up}
gemport 1 traffic-limit downstream {speed_profile_down}
switchport vlan {vlan} tag vport 1
exit"""


def upgrade() -> None:
    op.add_column("provisioning_templates", sa.Column("firmware", sa.String(length=80), nullable=True))
    op.add_column("provisioning_templates", sa.Column("template_name", sa.String(length=120), nullable=True))
    op.add_column("provisioning_templates", sa.Column("template_body", sa.Text(), nullable=True))
    op.add_column("provisioning_templates", sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()))

    op.execute("update provisioning_templates set template_name = name where template_name is null")
    op.execute("update provisioning_templates set template_body = commands where template_body is null")

    op.create_table(
        "provisioning_plans",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("olt_id", sa.Integer(), nullable=False),
        sa.Column("olt_code", sa.String(length=80), nullable=True),
        sa.Column("unauthorized_onu_id", sa.Integer(), nullable=False),
        sa.Column("serial_number", sa.String(length=80), nullable=False),
        sa.Column("pon_port_interface", sa.String(length=80), nullable=True),
        sa.Column("customer_name", sa.String(length=160), nullable=False),
        sa.Column("customer_reference", sa.String(length=160), nullable=True),
        sa.Column("technical_comment", sa.Text(), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("zone_id", sa.Integer(), nullable=False),
        sa.Column("nap_id", sa.Integer(), nullable=False),
        sa.Column("nap_port", sa.Integer(), nullable=False),
        sa.Column("onu_type", sa.String(length=80), nullable=False),
        sa.Column("vlan", sa.Integer(), nullable=False),
        sa.Column("speed_profile_up", sa.String(length=120), nullable=False),
        sa.Column("speed_profile_down", sa.String(length=120), nullable=False),
        sa.Column("generated_cli", sa.Text(), nullable=True),
        sa.Column("validation_warnings_json", sa.Text(), nullable=True),
        sa.Column("validation_errors_json", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="draft"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["nap_id"], ["naps.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["olt_id"], ["olts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["unauthorized_onu_id"], ["unauthorized_onus.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["zone_id"], ["zones.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.execute(
        sa.text(
            """
            insert into provisioning_templates
                (name, vendor, model, firmware, commands, template_name, template_body, is_default, description)
            select
                'ZTE C300 V1.2.5P3 default dry-run',
                'ZTE',
                'C300',
                'V1.2.5P3',
                :template_body,
                'ZTE C300 V1.2.5P3 default dry-run',
                :template_body,
                true,
                'Plantilla dry-run para preview de aprovisionamiento. No ejecuta comandos.'
            where not exists (
                select 1 from provisioning_templates where name = 'ZTE C300 V1.2.5P3 default dry-run'
            )
            """
        ).bindparams(template_body=DEFAULT_TEMPLATE)
    )


def downgrade() -> None:
    op.drop_table("provisioning_plans")
    op.drop_column("provisioning_templates", "is_default")
    op.drop_column("provisioning_templates", "template_body")
    op.drop_column("provisioning_templates", "template_name")
    op.drop_column("provisioning_templates", "firmware")
