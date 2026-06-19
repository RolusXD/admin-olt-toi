"""unauthorized onu mode suggestion

Revision ID: 0030_unauthorized_mode
Revises: 0029_onu_service_modes
Create Date: 2026-06-18
"""

from alembic import op
import sqlalchemy as sa


revision = "0030_unauthorized_mode"
down_revision = "0029_onu_service_modes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("unauthorized_onus", sa.Column("suggested_service_mode_code", sa.String(length=80), nullable=True))


def downgrade() -> None:
    op.drop_column("unauthorized_onus", "suggested_service_mode_code")
