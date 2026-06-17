"""backfill olt import status

Revision ID: 0011_backfill_import_status
Revises: 0010_multi_olt_identity
Create Date: 2026-06-17
"""

from alembic import op
import sqlalchemy as sa


revision = "0011_backfill_import_status"
down_revision = "0010_multi_olt_identity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            update olts
            set
                initial_import_status = 'confirmed',
                last_import_job_id = latest.id,
                last_import_confirmed_at = latest.confirmed_at
            from (
                select distinct on (olt_id) id, olt_id, confirmed_at
                from import_jobs
                where status = 'confirmed' and confirmed_at is not null
                order by olt_id, confirmed_at desc
            ) latest
            where olts.id = latest.olt_id
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            update olts
            set
                initial_import_status = 'pending',
                last_import_job_id = null,
                last_import_confirmed_at = null
            """
        )
    )
