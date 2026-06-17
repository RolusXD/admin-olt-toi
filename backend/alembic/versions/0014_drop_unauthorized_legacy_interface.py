"""drop unauthorized legacy interface

Revision ID: 0014_drop_unauth_interface
Revises: 0013_onu_discovery
Create Date: 2026-06-17
"""

from alembic import op
import sqlalchemy as sa


revision = "0014_drop_unauth_interface"
down_revision = "0013_onu_discovery"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    exists = conn.execute(
        sa.text(
            """
            select 1
            from information_schema.columns
            where table_name = 'unauthorized_onus'
              and column_name = 'interface'
            """
        )
    ).first()
    if exists:
        op.drop_column("unauthorized_onus", "interface")


def downgrade() -> None:
    op.add_column("unauthorized_onus", sa.Column("interface", sa.String(length=80), nullable=True))
