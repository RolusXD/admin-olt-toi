"""backfill import sources

Revision ID: 0012_backfill_import_sources
Revises: 0011_backfill_import_status
Create Date: 2026-06-17
"""

from alembic import op
import sqlalchemy as sa


revision = "0012_backfill_import_sources"
down_revision = "0011_backfill_import_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            update import_jobs
            set source = 'telnet'
            where exists (
                select 1
                from driver_command_logs
                where driver_command_logs.olt_id = import_jobs.olt_id
                  and driver_command_logs.command = 'show running-config'
                  and driver_command_logs.read_only = true
                  and driver_command_logs.success = true
            )
            """
        )
    )
    op.execute(
        sa.text(
            """
            update onus
            set import_source = 'telnet_running_config'
            where imported_from_config = true
              and exists (
                select 1
                from driver_command_logs
                where driver_command_logs.olt_id = onus.olt_id
                  and driver_command_logs.command = 'show running-config'
                  and driver_command_logs.read_only = true
                  and driver_command_logs.success = true
              )
            """
        )
    )
    op.execute(
        sa.text(
            """
            update onus
            set import_source = 'text_input'
            where imported_from_config = true
              and import_source = 'manual'
            """
        )
    )


def downgrade() -> None:
    op.execute(sa.text("update onus set import_source = 'manual' where imported_from_config = true"))
