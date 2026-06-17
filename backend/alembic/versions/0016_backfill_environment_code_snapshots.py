"""backfill environment code snapshots

Revision ID: 0016_backfill_env_snapshots
Revises: 0015_olt_environment
Create Date: 2026-06-17
"""

from alembic import op
import sqlalchemy as sa


revision = "0016_backfill_env_snapshots"
down_revision = "0015_olt_environment"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            update onus
            set olt_code_snapshot = olts.olt_code
            from olts
            where onus.olt_id = olts.id
              and onus.olt_id in (1, 3)
            """
        )
    )
    op.execute(
        sa.text(
            """
            update unauthorized_onus
            set olt_code_snapshot = olts.olt_code
            from olts
            where unauthorized_onus.olt_id = olts.id
              and unauthorized_onus.olt_id in (1, 3)
            """
        )
    )


def downgrade() -> None:
    pass
