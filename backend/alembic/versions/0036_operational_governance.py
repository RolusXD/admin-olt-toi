"""operational governance: users, roles, permissions, operation ids

Revision ID: 0036_operational_governance
Revises: 0035_dq_missing_fields
Create Date: 2026-06-25
"""

from alembic import op
import sqlalchemy as sa


revision = "0036_operational_governance"
down_revision = "0035_dq_missing_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Usuarios operativos
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(length=80), nullable=False, unique=True, index=True),
        sa.Column("full_name", sa.String(length=160), nullable=False),
        sa.Column("email", sa.String(length=160), nullable=True, unique=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="active"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_by_username_snapshot", sa.String(length=160), nullable=True),
        sa.Column("updated_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("updated_by_username_snapshot", sa.String(length=160), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
    )

    # Roles base
    op.create_table(
        "roles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=40), nullable=False, unique=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # Permisos desacoplados
    op.create_table(
        "permissions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=80), nullable=False, unique=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(length=40), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # Asignación de roles a usuarios
    op.create_table(
        "user_roles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role_id", sa.Integer(), sa.ForeignKey("roles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("assigned_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "role_id", name="uq_user_roles_user_role"),
    )

    # Asignación de permisos a roles con Execution Policy
    op.create_table(
        "role_permissions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("role_id", sa.Integer(), sa.ForeignKey("roles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("permission_id", sa.Integer(), sa.ForeignKey("permissions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("execution_policy", sa.String(length=20), nullable=False, server_default="FULL"),
        sa.Column("requires_supervisor_approval", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("role_id", "permission_id", name="uq_role_permissions_role_permission"),
    )

    # Secuencia global de Operation IDs
    op.create_table(
        "operation_ids",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=32), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # Extensión de event_logs para Audit Trail / Bitácora operativa
    op.add_column("event_logs", sa.Column("operation_id", sa.String(length=32), nullable=True))
    op.add_column("event_logs", sa.Column("user_id", sa.Integer(), nullable=True))
    op.add_column("event_logs", sa.Column("user_name", sa.String(length=160), nullable=True))
    op.add_column("event_logs", sa.Column("role_code", sa.String(length=80), nullable=True))
    op.add_column("event_logs", sa.Column("origin", sa.String(length=40), nullable=True))
    op.add_column("event_logs", sa.Column("result", sa.String(length=30), nullable=True))
    op.add_column("event_logs", sa.Column("action", sa.String(length=80), nullable=True))
    op.add_column("event_logs", sa.Column("duration_ms", sa.Integer(), nullable=True))
    op.add_column("event_logs", sa.Column("reason", sa.Text(), nullable=True))
    op.add_column("event_logs", sa.Column("error", sa.Text(), nullable=True))
    op.create_foreign_key(
        "fk_event_logs_user_id",
        "event_logs",
        "users",
        ["user_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # Semillas mínimas de roles
    op.execute(
        """
        INSERT INTO roles (code, name, description, is_active)
        VALUES
            ('ADMIN', 'Administrador', 'Rol administrador del sistema', TRUE),
            ('TECNICO', 'Tecnico', 'Rol tecnico de operaciones', TRUE),
            ('MONITOR', 'Monitor', 'Rol de monitoreo y NOC', TRUE),
            ('AUDITOR', 'Auditor', 'Rol de auditoria y revision', TRUE)
        """
    )

    # Semillas mínimas de permisos (estructura base; no exhaustivo)
    op.execute(
        """
        INSERT INTO permissions (code, name, category, is_active)
        VALUES
            ('OLT.READ', 'Ver detalle de OLT', 'OLT', TRUE),
            ('OLT.ADOPT', 'Adoptar OLT', 'OLT', TRUE),
            ('ONU.READ', 'Ver detalle de ONU', 'ONU', TRUE),
            ('ONU.UPDATE', 'Actualizar ONU', 'ONU', TRUE),
            ('AUDIT.READ', 'Ver auditoria y bitacora', 'AUDIT', TRUE),
            ('USER.READ', 'Ver usuarios', 'USER', TRUE),
            ('USER.UPDATE', 'Actualizar usuarios', 'USER', TRUE)
        """
    )

    # Asignaciones base de permisos a roles
    # ADMIN: FULL en todos los permisos sembrados
    op.execute(
        """
        INSERT INTO role_permissions (role_id, permission_id, execution_policy, requires_supervisor_approval, is_active)
        SELECT r.id, p.id, 'FULL', FALSE, TRUE
        FROM roles r
        JOIN permissions p ON TRUE
        WHERE r.code = 'ADMIN'
        """
    )

    # TECNICO: FULL en ONU/OLT, REVIEW en OLT.ADOPT
    op.execute(
        """
        INSERT INTO role_permissions (role_id, permission_id, execution_policy, requires_supervisor_approval, is_active)
        SELECT r.id,
               p.id,
               CASE
                   WHEN p.code = 'OLT.ADOPT' THEN 'REVIEW'
                   ELSE 'FULL'
               END AS execution_policy,
               CASE
                   WHEN p.code = 'OLT.ADOPT' THEN FALSE
                   ELSE FALSE
               END AS requires_supervisor_approval,
               TRUE
        FROM roles r
        JOIN permissions p ON p.code IN ('OLT.READ', 'OLT.ADOPT', 'ONU.READ', 'ONU.UPDATE')
        WHERE r.code = 'TECNICO'
        """
    )

    # MONITOR: READ_ONLY en lecturas (OLT.READ, ONU.READ, AUDIT.READ)
    op.execute(
        """
        INSERT INTO role_permissions (role_id, permission_id, execution_policy, requires_supervisor_approval, is_active)
        SELECT r.id, p.id, 'READ_ONLY', FALSE, TRUE
        FROM roles r
        JOIN permissions p ON p.code IN ('OLT.READ', 'ONU.READ', 'AUDIT.READ')
        WHERE r.code = 'MONITOR'
        """
    )

    # AUDITOR: READ_ONLY en lecturas y usuarios
    op.execute(
        """
        INSERT INTO role_permissions (role_id, permission_id, execution_policy, requires_supervisor_approval, is_active)
        SELECT r.id, p.id, 'READ_ONLY', FALSE, TRUE
        FROM roles r
        JOIN permissions p ON p.code IN ('OLT.READ', 'ONU.READ', 'AUDIT.READ', 'USER.READ')
        WHERE r.code = 'AUDITOR'
        """
    )


def downgrade() -> None:
    # Revertir extensiones en event_logs
    op.drop_constraint("fk_event_logs_user_id", "event_logs", type_="foreignkey")
    op.drop_column("event_logs", "error")
    op.drop_column("event_logs", "reason")
    op.drop_column("event_logs", "duration_ms")
    op.drop_column("event_logs", "action")
    op.drop_column("event_logs", "result")
    op.drop_column("event_logs", "origin")
    op.drop_column("event_logs", "role_code")
    op.drop_column("event_logs", "user_name")
    op.drop_column("event_logs", "user_id")
    op.drop_column("event_logs", "operation_id")

    # Tablas nuevas
    op.drop_table("operation_ids")
    op.drop_table("role_permissions")
    op.drop_table("user_roles")
    op.drop_table("permissions")
    op.drop_table("roles")
    op.drop_table("users")
