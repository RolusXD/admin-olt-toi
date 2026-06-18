"""onu type operational alias

Revision ID: 0022_onu_type_alias
Revises: 0021_zte_catalogs
Create Date: 2026-06-18
"""

from alembic import op
import sqlalchemy as sa


revision = "0022_onu_type_alias"
down_revision = "0021_zte_catalogs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("onu_types", sa.Column("display_name", sa.String(length=160), nullable=True))
    op.add_column("onu_types", sa.Column("operational_alias", sa.String(length=120), nullable=True))
    op.add_column("onu_types", sa.Column("is_provisioning_allowed", sa.Boolean(), nullable=False, server_default=sa.false()))

    op.execute(
        """
        update onu_types
        set operational_alias = 'VSOL',
            display_name = 'VSOL / 2 LAN + WiFi',
            is_provisioning_allowed = true
        from olts
        where onu_types.olt_id = olts.id
          and olts.olt_code = 'OLT-PCM-ZTE-01'
          and onu_types.name = 'Prueba-vSol-no-usar'
        """
    )


def downgrade() -> None:
    op.drop_column("onu_types", "is_provisioning_allowed")
    op.drop_column("onu_types", "operational_alias")
    op.drop_column("onu_types", "display_name")
