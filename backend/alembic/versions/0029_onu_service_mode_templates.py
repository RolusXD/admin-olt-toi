"""onu service mode templates

Revision ID: 0029_onu_service_modes
Revises: 0028_preserve_onu_description
Create Date: 2026-06-18
"""

from alembic import op
import sqlalchemy as sa


revision = "0029_onu_service_modes"
down_revision = "0028_preserve_onu_description"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "onu_service_mode_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("olt_id", sa.Integer(), sa.ForeignKey("olts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("vendor", sa.String(length=40), nullable=False, server_default="ZTE"),
        sa.Column("model", sa.String(length=80), nullable=False, server_default="C300"),
        sa.Column("firmware", sa.String(length=80), nullable=False, server_default="V1.2.5P3"),
        sa.Column("mode_code", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("vlan_mode", sa.String(length=30), nullable=False, server_default="tag"),
        sa.Column("dhcp_source", sa.String(length=40), nullable=False, server_default="from-internet"),
        sa.Column("use_iphost", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("use_veip", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("use_vlan_filter", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("use_loop_detect", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("disable_wifi", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("default_for_provisioning", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("template_body", sa.Text(), nullable=False),
        sa.Column("source", sa.String(length=40), nullable=False, server_default="imported"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("olt_id", "mode_code", name="uq_onu_service_modes_olt_code"),
    )
    op.add_column(
        "provisioning_plans",
        sa.Column("service_mode_template_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_provisioning_plan_service_mode",
        "provisioning_plans",
        "onu_service_mode_templates",
        ["service_mode_template_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column(
        "provisioning_plans",
        sa.Column("service_mode_code", sa.String(length=80), nullable=False, server_default="bridge_tag_internet"),
    )
    op.add_column("onus", sa.Column("service_mode_code", sa.String(length=80), nullable=True))


def downgrade() -> None:
    op.drop_column("onus", "service_mode_code")
    op.drop_column("provisioning_plans", "service_mode_code")
    op.drop_constraint("fk_provisioning_plan_service_mode", "provisioning_plans", type_="foreignkey")
    op.drop_column("provisioning_plans", "service_mode_template_id")
    op.drop_table("onu_service_mode_templates")
