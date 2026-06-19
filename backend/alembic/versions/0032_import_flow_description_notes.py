"""import lifecycle and ONU technician notes

Revision ID: 0032_import_flow_notes
Revises: 0031_olt_owned_ftth
Create Date: 2026-06-19
"""

from alembic import op
import sqlalchemy as sa


revision = "0032_import_flow_notes"
down_revision = "0031_olt_owned_ftth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("onus", sa.Column("technician_notes", sa.Text(), nullable=True))
    op.execute("UPDATE olts SET initial_import_status = 'draft' WHERE initial_import_status = 'pending'")
    op.execute(
        "UPDATE olts SET initial_import_status = 'cancelled' "
        "WHERE id = 7 AND initial_import_status <> 'confirmed' AND (olt_code = 'PCM-1' OR name = 'PCM-1')"
    )


def downgrade() -> None:
    op.execute("UPDATE olts SET initial_import_status = 'pending' WHERE initial_import_status = 'draft'")
    op.drop_column("onus", "technician_notes")
