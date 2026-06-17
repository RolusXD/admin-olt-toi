"""add multi olt import identity

Revision ID: 0010_multi_olt_identity
Revises: 0009_monitoring_exec
Create Date: 2026-06-17
"""

from alembic import op
import sqlalchemy as sa


revision = "0010_multi_olt_identity"
down_revision = "0009_monitoring_exec"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("olts", sa.Column("olt_code", sa.String(length=80), nullable=True))
    op.add_column("olts", sa.Column("display_name", sa.String(length=160), nullable=True))
    op.add_column("olts", sa.Column("initial_import_status", sa.String(length=40), nullable=False, server_default="pending"))
    op.add_column("olts", sa.Column("last_import_job_id", sa.Integer(), nullable=True))
    op.add_column("olts", sa.Column("last_import_confirmed_at", sa.DateTime(timezone=True), nullable=True))

    conn = op.get_bind()
    rows = conn.execute(sa.text("select id from olts order by id")).fetchall()
    for index, row in enumerate(rows, start=1):
        conn.execute(sa.text("update olts set olt_code = :code where id = :id"), {"code": f"OLT-{index:04d}", "id": row.id})

    op.alter_column("olts", "olt_code", existing_type=sa.String(length=80), nullable=False)
    op.create_unique_constraint("uq_olts_olt_code", "olts", ["olt_code"])
    op.create_foreign_key(
        "fk_olts_last_import_job_id",
        "olts",
        "import_jobs",
        ["last_import_job_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column("import_jobs", sa.Column("source", sa.String(length=30), nullable=False, server_default="text"))
    op.add_column("onus", sa.Column("olt_code_snapshot", sa.String(length=80), nullable=True))
    op.add_column("onus", sa.Column("customer_reference", sa.String(length=160), nullable=True))
    op.add_column("onus", sa.Column("external_customer_id", sa.String(length=160), nullable=True))
    op.add_column("onus", sa.Column("import_source", sa.String(length=40), nullable=False, server_default="manual"))

    conn.execute(
        sa.text(
            """
            update onus
            set olt_code_snapshot = olts.olt_code
            from olts
            where onus.olt_id = olts.id and onus.olt_code_snapshot is null
            """
        )
    )


def downgrade() -> None:
    op.drop_column("onus", "import_source")
    op.drop_column("onus", "external_customer_id")
    op.drop_column("onus", "customer_reference")
    op.drop_column("onus", "olt_code_snapshot")
    op.drop_column("import_jobs", "source")
    op.drop_constraint("fk_olts_last_import_job_id", "olts", type_="foreignkey")
    op.drop_constraint("uq_olts_olt_code", "olts", type_="unique")
    op.drop_column("olts", "last_import_confirmed_at")
    op.drop_column("olts", "last_import_job_id")
    op.drop_column("olts", "initial_import_status")
    op.drop_column("olts", "display_name")
    op.drop_column("olts", "olt_code")
