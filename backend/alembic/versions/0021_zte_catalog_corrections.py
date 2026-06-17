"""zte catalog corrections

Revision ID: 0021_zte_catalogs
Revises: 0020_backfill_masters
Create Date: 2026-06-17
"""

from alembic import op
import sqlalchemy as sa


revision = "0021_zte_catalogs"
down_revision = "0020_backfill_masters"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("onu_types", "speed_profiles"):
        op.add_column(table, sa.Column("vendor", sa.String(length=40), nullable=False, server_default="ZTE"))
        op.add_column(table, sa.Column("model", sa.String(length=80), nullable=False, server_default="C300"))
        op.add_column(table, sa.Column("firmware", sa.String(length=80), nullable=False, server_default="V1.2.5P3"))

    op.add_column("onu_types", sa.Column("max_switch_perslot", sa.Integer(), nullable=True))
    op.add_column("onu_types", sa.Column("max_flow_perswitch", sa.Integer(), nullable=True))
    op.add_column("onu_types", sa.Column("max_iphost", sa.Integer(), nullable=True))

    op.create_table(
        "profile_catalogs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("olt_id", sa.Integer(), nullable=False),
        sa.Column("olt_code_snapshot", sa.String(length=80), nullable=True),
        sa.Column("vendor", sa.String(length=40), nullable=False, server_default="ZTE"),
        sa.Column("model", sa.String(length=80), nullable=False, server_default="C300"),
        sa.Column("firmware", sa.String(length=80), nullable=False, server_default="V1.2.5P3"),
        sa.Column("direction", sa.String(length=30), nullable=False),
        sa.Column("profile_kind", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("type_value", sa.Integer(), nullable=True),
        sa.Column("fixed_kbps", sa.Integer(), nullable=True),
        sa.Column("assured_kbps", sa.Integer(), nullable=True),
        sa.Column("maximum_kbps", sa.Integer(), nullable=True),
        sa.Column("sir_kbps", sa.Integer(), nullable=True),
        sa.Column("pir_kbps", sa.Integer(), nullable=True),
        sa.Column("source", sa.String(length=40), nullable=False, server_default="imported"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["olt_id"], ["olts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("olt_id", "profile_kind", "name", name="uq_profile_catalogs_olt_kind_name"),
    )

    op.add_column("speed_profiles", sa.Column("upload_profile_id", sa.Integer(), nullable=True))
    op.add_column("speed_profiles", sa.Column("download_profile_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_speed_profiles_upload_catalog", "speed_profiles", "profile_catalogs", ["upload_profile_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_speed_profiles_download_catalog", "speed_profiles", "profile_catalogs", ["download_profile_id"], ["id"], ondelete="SET NULL")

    op.add_column("provisioning_plans", sa.Column("upload_profile_id", sa.Integer(), nullable=True))
    op.add_column("provisioning_plans", sa.Column("download_profile_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_provisioning_plans_upload_catalog", "provisioning_plans", "profile_catalogs", ["upload_profile_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_provisioning_plans_download_catalog", "provisioning_plans", "profile_catalogs", ["download_profile_id"], ["id"], ondelete="SET NULL")

    op.execute(
        """
        update onu_types
        set vendor = olts.vendor, model = olts.model, firmware = olts.firmware,
            max_switch_perslot = coalesce(max_switch_perslot, max_ports)
        from olts
        where onu_types.olt_id = olts.id
        """
    )
    op.execute(
        """
        update speed_profiles
        set vendor = olts.vendor, model = olts.model, firmware = olts.firmware
        from olts
        where speed_profiles.olt_id = olts.id
        """
    )
    op.execute(
        """
        insert into profile_catalogs
            (olt_id, olt_code_snapshot, vendor, model, firmware, direction, profile_kind, name,
             maximum_kbps, sir_kbps, pir_kbps, source, is_active)
        select gp.olt_id, olts.olt_code, olts.vendor, olts.model, olts.firmware,
               case when gp.profile_type = 'tcont' then 'upload' else 'download' end,
               gp.profile_type,
               gp.name,
               case when gp.profile_type = 'tcont' then gp.upstream_rate else null end,
               case when gp.profile_type = 'traffic' then gp.downstream_rate else null end,
               case when gp.profile_type = 'traffic' then gp.downstream_rate else null end,
               'imported',
               true
        from gpon_profiles gp
        join olts on olts.id = gp.olt_id
        on conflict (olt_id, profile_kind, name) do nothing
        """
    )


def downgrade() -> None:
    op.drop_constraint("fk_provisioning_plans_download_catalog", "provisioning_plans", type_="foreignkey")
    op.drop_constraint("fk_provisioning_plans_upload_catalog", "provisioning_plans", type_="foreignkey")
    op.drop_column("provisioning_plans", "download_profile_id")
    op.drop_column("provisioning_plans", "upload_profile_id")
    op.drop_constraint("fk_speed_profiles_download_catalog", "speed_profiles", type_="foreignkey")
    op.drop_constraint("fk_speed_profiles_upload_catalog", "speed_profiles", type_="foreignkey")
    op.drop_column("speed_profiles", "download_profile_id")
    op.drop_column("speed_profiles", "upload_profile_id")
    op.drop_table("profile_catalogs")
    op.drop_column("onu_types", "max_iphost")
    op.drop_column("onu_types", "max_flow_perswitch")
    op.drop_column("onu_types", "max_switch_perslot")
    for table in ("speed_profiles", "onu_types"):
        op.drop_column(table, "firmware")
        op.drop_column(table, "model")
        op.drop_column(table, "vendor")
