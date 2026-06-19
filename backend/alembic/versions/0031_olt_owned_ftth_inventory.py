"""associate zones, naps and nap ports with an OLT

Revision ID: 0031_olt_owned_ftth
Revises: 0030_unauthorized_mode
Create Date: 2026-06-19
"""

from alembic import op
import sqlalchemy as sa


revision = "0031_olt_owned_ftth"
down_revision = "0030_unauthorized_mode"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("zones", "naps", "nap_ports"):
        op.add_column(table, sa.Column("olt_id", sa.Integer(), nullable=True))
        op.add_column(table, sa.Column("olt_code_snapshot", sa.String(length=80), nullable=True))
        op.create_foreign_key(f"fk_{table}_olt_id", table, "olts", ["olt_id"], ["id"], ondelete="CASCADE")
        op.create_index(f"ix_{table}_olt_id", table, ["olt_id"])

    op.execute(
        """
        UPDATE zones z
        SET olt_id = source.olt_id, olt_code_snapshot = o.olt_code
        FROM (SELECT zone_id, MIN(olt_id) AS olt_id FROM onus WHERE zone_id IS NOT NULL GROUP BY zone_id) source
        JOIN olts o ON o.id = source.olt_id
        WHERE z.id = source.zone_id
        """
    )
    op.execute(
        """
        UPDATE naps n SET olt_id = z.olt_id, olt_code_snapshot = z.olt_code_snapshot
        FROM zones z WHERE n.zone_id = z.id
        """
    )
    op.execute(
        """
        UPDATE nap_ports p SET olt_id = n.olt_id, olt_code_snapshot = n.olt_code_snapshot
        FROM naps n WHERE p.nap_id = n.id
        """
    )

    op.drop_constraint("zones_name_key", "zones", type_="unique")
    op.create_unique_constraint("uq_zones_olt_name", "zones", ["olt_id", "name"])
    op.drop_constraint("uq_naps_zone_name", "naps", type_="unique")
    op.create_unique_constraint("uq_naps_olt_zone_name", "naps", ["olt_id", "zone_id", "name"])


def downgrade() -> None:
    op.drop_constraint("uq_naps_olt_zone_name", "naps", type_="unique")
    op.create_unique_constraint("uq_naps_zone_name", "naps", ["zone_id", "name"])
    op.drop_constraint("uq_zones_olt_name", "zones", type_="unique")
    op.create_unique_constraint("zones_name_key", "zones", ["name"])
    for table in ("nap_ports", "naps", "zones"):
        op.drop_index(f"ix_{table}_olt_id", table_name=table)
        op.drop_constraint(f"fk_{table}_olt_id", table, type_="foreignkey")
        op.drop_column(table, "olt_code_snapshot")
        op.drop_column(table, "olt_id")
