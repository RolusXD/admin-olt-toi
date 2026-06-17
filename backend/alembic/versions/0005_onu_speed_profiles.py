"""add onu upstream and downstream profiles

Revision ID: 0005_onu_speed_profiles
Revises: 0004_import_upsert_constraints
Create Date: 2026-06-16
"""

from alembic import op
import sqlalchemy as sa

revision = "0005_onu_speed_profiles"
down_revision = "0004_import_upsert_constraints"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("onus", sa.Column("speed_profile_up", sa.String(80), nullable=True))
    op.add_column("onus", sa.Column("speed_profile_down", sa.String(80), nullable=True))
    op.execute("UPDATE onus SET speed_profile_down = speed_profile WHERE speed_profile_down IS NULL")


def downgrade() -> None:
    op.drop_column("onus", "speed_profile_down")
    op.drop_column("onus", "speed_profile_up")
