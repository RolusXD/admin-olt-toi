"""provisioning preflight checks

Revision ID: 0026_provisioning_preflight
Revises: 0025_sync_uplinks_show_interface
Create Date: 2026-06-18 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0026_provisioning_preflight"
down_revision = "0025_sync_uplinks_show_interface"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("provisioning_validation_results", sa.Column("preflight_checks_json", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("provisioning_validation_results", "preflight_checks_json")
