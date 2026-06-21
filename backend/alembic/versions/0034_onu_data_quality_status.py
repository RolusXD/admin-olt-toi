"""add data quality status to onus

Revision ID: 0034_onu_data_quality_status
Revises: 0033_complete_snapshots
Create Date: 2026-06-21
"""

from alembic import op
import sqlalchemy as sa


revision = "0034_onu_data_quality_status"
down_revision = "0033_complete_snapshots"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("onus", sa.Column("data_quality_status", sa.String(length=30), nullable=True))
    # Mark imported ONUs as legacy_incomplete by default; manual ONUs will be
    # classified on demand or in future phases.
    op.execute(
        """
        UPDATE onus
        SET data_quality_status = 'legacy_incomplete'
        WHERE imported_from_config IS TRUE AND data_quality_status IS NULL
        """
    )


def downgrade() -> None:
    op.drop_column("onus", "data_quality_status")
