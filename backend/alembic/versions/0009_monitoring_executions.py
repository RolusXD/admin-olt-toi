"""add monitoring executions

Revision ID: 0009_monitoring_exec
Revises: 0008_olt_conn_type
Create Date: 2026-06-17
"""

from alembic import op
import sqlalchemy as sa


revision = "0009_monitoring_exec"
down_revision = "0008_olt_conn_type"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "monitoring_executions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("olt_id", sa.Integer(), nullable=False),
        sa.Column("task_type", sa.String(length=40), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("processed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("success_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("details_json", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["olt_id"], ["olts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("monitoring_executions")
