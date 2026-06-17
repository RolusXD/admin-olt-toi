"""master catalogs

Revision ID: 0019_master_catalogs
Revises: 0018_prov_adv_validation
Create Date: 2026-06-17
"""

from alembic import op
import sqlalchemy as sa


revision = "0019_master_catalogs"
down_revision = "0018_prov_adv_validation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("onu_types", sa.Column("olt_code_snapshot", sa.String(length=80), nullable=True))
    op.add_column("onu_types", sa.Column("model_detected", sa.String(length=80), nullable=True))
    op.add_column("onu_types", sa.Column("technology", sa.String(length=30), nullable=False, server_default="GPON"))
    op.add_column("onu_types", sa.Column("ethernet_ports", sa.Integer(), nullable=True))
    op.add_column("onu_types", sa.Column("wifi_ports", sa.Integer(), nullable=True))
    op.add_column("onu_types", sa.Column("pots_ports", sa.Integer(), nullable=True))
    op.add_column("onu_types", sa.Column("rf_ports", sa.Integer(), nullable=True))
    op.add_column("onu_types", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("onu_types", sa.Column("source", sa.String(length=40), nullable=False, server_default="imported"))
    op.add_column("onu_types", sa.Column("notes", sa.Text(), nullable=True))

    op.add_column("vlans", sa.Column("olt_code_snapshot", sa.String(length=80), nullable=True))
    op.add_column("vlans", sa.Column("service_type", sa.String(length=40), nullable=False, server_default="internet"))
    op.add_column("vlans", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("vlans", sa.Column("source", sa.String(length=40), nullable=False, server_default="imported"))
    op.add_column("vlans", sa.Column("notes", sa.Text(), nullable=True))

    op.add_column("zones", sa.Column("code", sa.String(length=80), nullable=True))
    op.add_column("zones", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("zones", sa.Column("source", sa.String(length=40), nullable=False, server_default="imported"))
    op.add_column("zones", sa.Column("notes", sa.Text(), nullable=True))

    op.add_column("naps", sa.Column("code", sa.String(length=80), nullable=True))
    op.add_column("naps", sa.Column("nap_type", sa.String(length=40), nullable=False, server_default="NAP"))
    op.add_column("naps", sa.Column("address_reference", sa.Text(), nullable=True))
    op.add_column("naps", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("naps", sa.Column("source", sa.String(length=40), nullable=False, server_default="imported"))
    op.add_column("naps", sa.Column("notes", sa.Text(), nullable=True))

    op.add_column("provisioning_templates", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("provisioning_templates", sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))

    op.create_table(
        "speed_profiles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("olt_id", sa.Integer(), nullable=False),
        sa.Column("olt_code_snapshot", sa.String(length=80), nullable=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("profile_code", sa.String(length=120), nullable=False),
        sa.Column("upstream_profile_name", sa.String(length=120), nullable=False),
        sa.Column("downstream_profile_name", sa.String(length=120), nullable=False),
        sa.Column("upstream_kbps", sa.Integer(), nullable=True),
        sa.Column("downstream_kbps", sa.Integer(), nullable=True),
        sa.Column("technology", sa.String(length=30), nullable=False, server_default="GPON"),
        sa.Column("source", sa.String(length=40), nullable=False, server_default="imported"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["olt_id"], ["olts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("olt_id", "profile_code", name="uq_speed_profiles_olt_code"),
    )

    op.add_column("provisioning_plans", sa.Column("speed_profile_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_provisioning_plans_speed_profile",
        "provisioning_plans",
        "speed_profiles",
        ["speed_profile_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "nap_ports",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nap_id", sa.Integer(), nullable=False),
        sa.Column("port_number", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(length=80), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="free"),
        sa.Column("onu_id", sa.Integer(), nullable=True),
        sa.Column("customer_name_snapshot", sa.String(length=160), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["nap_id"], ["naps.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["onu_id"], ["onus.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("nap_id", "port_number", name="uq_nap_ports_nap_port"),
    )

    op.execute(
        """
        update onu_types set olt_code_snapshot = olts.olt_code
        from olts where onu_types.olt_id = olts.id and onu_types.olt_code_snapshot is null
        """
    )
    op.execute(
        """
        update vlans set olt_code_snapshot = olts.olt_code
        from olts where vlans.olt_id = olts.id and vlans.olt_code_snapshot is null
        """
    )


def downgrade() -> None:
    op.drop_table("nap_ports")
    op.drop_constraint("fk_provisioning_plans_speed_profile", "provisioning_plans", type_="foreignkey")
    op.drop_column("provisioning_plans", "speed_profile_id")
    op.drop_table("speed_profiles")
    op.drop_column("provisioning_templates", "updated_at")
    op.drop_column("provisioning_templates", "is_active")
    op.drop_column("naps", "notes")
    op.drop_column("naps", "source")
    op.drop_column("naps", "is_active")
    op.drop_column("naps", "address_reference")
    op.drop_column("naps", "nap_type")
    op.drop_column("naps", "code")
    op.drop_column("zones", "notes")
    op.drop_column("zones", "source")
    op.drop_column("zones", "is_active")
    op.drop_column("zones", "code")
    op.drop_column("vlans", "notes")
    op.drop_column("vlans", "source")
    op.drop_column("vlans", "is_active")
    op.drop_column("vlans", "service_type")
    op.drop_column("vlans", "olt_code_snapshot")
    op.drop_column("onu_types", "notes")
    op.drop_column("onu_types", "source")
    op.drop_column("onu_types", "is_active")
    op.drop_column("onu_types", "rf_ports")
    op.drop_column("onu_types", "pots_ports")
    op.drop_column("onu_types", "wifi_ports")
    op.drop_column("onu_types", "ethernet_ports")
    op.drop_column("onu_types", "technology")
    op.drop_column("onu_types", "model_detected")
    op.drop_column("onu_types", "olt_code_snapshot")
