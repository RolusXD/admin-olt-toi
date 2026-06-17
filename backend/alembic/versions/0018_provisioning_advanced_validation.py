"""provisioning advanced validation

Revision ID: 0018_prov_adv_validation
Revises: 0017_provisioning_dry_run
Create Date: 2026-06-17
"""

from alembic import op
import sqlalchemy as sa


revision = "0018_prov_adv_validation"
down_revision = "0017_provisioning_dry_run"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("provisioning_plans", sa.Column("selected_onu_id", sa.Integer(), nullable=True))
    op.add_column("provisioning_plans", sa.Column("suggested_onu_id", sa.Integer(), nullable=True))
    op.add_column("provisioning_plans", sa.Column("validation_result_json", sa.Text(), nullable=True))
    op.add_column("provisioning_plans", sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "provisioning_validation_results",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provisioning_plan_id", sa.Integer(), nullable=False),
        sa.Column("is_valid", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("warnings_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("errors_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("suggested_onu_id", sa.Integer(), nullable=True),
        sa.Column("selected_onu_id", sa.Integer(), nullable=True),
        sa.Column("occupied_onu_ids_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("cli_preview", sa.Text(), nullable=True),
        sa.Column("validated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["provisioning_plan_id"], ["provisioning_plans.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provisioning_plan_id", name="uq_provisioning_validation_plan"),
    )


def downgrade() -> None:
    op.drop_table("provisioning_validation_results")
    op.drop_column("provisioning_plans", "validated_at")
    op.drop_column("provisioning_plans", "validation_result_json")
    op.drop_column("provisioning_plans", "suggested_onu_id")
    op.drop_column("provisioning_plans", "selected_onu_id")
