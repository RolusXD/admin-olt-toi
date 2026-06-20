"""complete running config snapshot lifecycle

Revision ID: 0033_complete_snapshots
Revises: 0032_import_flow_notes
Create Date: 2026-06-20
"""

from alembic import op
import sqlalchemy as sa


revision = "0033_complete_snapshots"
down_revision = "0032_import_flow_notes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("config_snapshots", sa.Column("status", sa.String(length=30), nullable=False, server_default="captured"))
    op.add_column("config_snapshots", sa.Column("checksum", sa.String(length=64), nullable=True))
    op.add_column("config_snapshots", sa.Column("warnings", sa.Text(), nullable=True))
    op.add_column("config_snapshots", sa.Column("parser_result", sa.Text(), nullable=True))
    op.execute(
        """
        UPDATE config_snapshots AS snapshot
        SET status = CASE
            WHEN job.status = 'confirmed' THEN 'confirmed'
            WHEN job.status IN ('failed', 'cancelled') THEN job.status
            WHEN job.status IN ('preview', 'preview_created') THEN 'parsed'
            ELSE snapshot.status
        END
        FROM import_jobs AS job
        WHERE job.raw_config_snapshot_id = snapshot.id
        """
    )


def downgrade() -> None:
    op.drop_column("config_snapshots", "parser_result")
    op.drop_column("config_snapshots", "warnings")
    op.drop_column("config_snapshots", "checksum")
    op.drop_column("config_snapshots", "status")
