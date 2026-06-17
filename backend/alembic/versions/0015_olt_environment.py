"""add olt environment

Revision ID: 0015_olt_environment
Revises: 0014_drop_unauth_interface
Create Date: 2026-06-17
"""

from alembic import op
import sqlalchemy as sa


revision = "0015_olt_environment"
down_revision = "0014_drop_unauth_interface"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("olts", sa.Column("environment", sa.String(length=30), nullable=False, server_default="production"))
    op.execute(
        sa.text(
            """
            update olts
            set
                environment = 'lab',
                olt_code = 'OLT-LAB-ZTE-01'
            where id = 1
            """
        )
    )
    op.execute(
        sa.text(
            """
            update olts
            set
                environment = 'production',
                olt_code = 'OLT-PCM-ZTE-01',
                name = 'FTTH-PCM-ZTE1'
            where id = 3
            """
        )
    )
    op.execute(sa.text("update olts set environment = 'lab' where id <> 3 and lower(name) like '%test%'"))
    op.execute(sa.text("update olts set environment = 'lab' where id <> 3 and lower(name) like '%tets%'"))


def downgrade() -> None:
    op.drop_column("olts", "environment")
