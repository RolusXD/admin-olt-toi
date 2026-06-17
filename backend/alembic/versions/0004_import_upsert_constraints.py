"""align initial import upsert constraints

Revision ID: 0004_import_upsert_constraints
Revises: 0003_initial_import
Create Date: 2026-06-16
"""

from alembic import op

revision = "0004_import_upsert_constraints"
down_revision = "0003_initial_import"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("onus_serial_number_key", "onus", type_="unique")
    op.create_unique_constraint("uq_onus_olt_serial", "onus", ["olt_id", "serial_number"])
    op.drop_index("ix_pon_ports_olt_interface", table_name="pon_ports")
    op.create_unique_constraint("uq_pon_ports_olt_interface", "pon_ports", ["olt_id", "interface_name"])
    op.create_unique_constraint("uq_naps_zone_name", "naps", ["zone_id", "name"])


def downgrade() -> None:
    op.drop_constraint("uq_naps_zone_name", "naps", type_="unique")
    op.drop_constraint("uq_pon_ports_olt_interface", "pon_ports", type_="unique")
    op.create_index("ix_pon_ports_olt_interface", "pon_ports", ["olt_id", "interface_name"], unique=False)
    op.drop_constraint("uq_onus_olt_serial", "onus", type_="unique")
    op.create_unique_constraint("onus_serial_number_key", "onus", ["serial_number"])
