from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.entities import Role, User, UserRole
from app.services.operator_context_service import OperatorContextService


def _setup_db() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return SessionLocal()


def test_operator_context_creates_admin_user_and_role_link_when_missing():
    session = _setup_db()
    with session:
        # Seed ADMIN role as in Alembic migration.
        admin_role = Role(code="ADMIN", name="Administrador")
        session.add(admin_role)
        session.commit()

        service = OperatorContextService(session)
        ctx = service.resolve("test-admin")

        assert ctx.user_id is not None
        assert ctx.user_name == "test-admin"
        assert ctx.role_code == "ADMIN"
        assert ctx.origin == "api"

        user = session.get(User, ctx.user_id)
        assert user is not None
        assert user.username == "test-admin"

        link = session.scalar(
            select(UserRole).where(UserRole.user_id == user.id, UserRole.role_id == admin_role.id)
        )
        assert link is not None


def test_operator_context_reuses_existing_user_without_duplicate_roles():
    session = _setup_db()
    with session:
        role = Role(code="ADMIN", name="Administrador")
        user = User(username="existing-admin", full_name="Existing Admin", is_active=True, status="active")
        session.add_all([role, user])
        session.flush()
        session.add(UserRole(user_id=user.id, role_id=role.id))
        session.commit()

        service = OperatorContextService(session)
        ctx = service.resolve("existing-admin")

        assert ctx.user_id == user.id
        assert ctx.user_name == "existing-admin"

        links = list(session.scalars(select(UserRole).where(UserRole.user_id == user.id, UserRole.role_id == role.id)))
        assert len(links) == 1
