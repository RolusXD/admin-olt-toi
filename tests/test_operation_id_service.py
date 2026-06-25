from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.entities import OperationId
from app.services.operation_id_service import OperationIdService


def _setup_db() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return SessionLocal()


def test_operation_id_format_and_persistence():
    """El Operation ID debe seguir el formato OP-YYYYMMDD-HHMMSS-XXXX y persistirse."""

    session = _setup_db()
    with session:
        service = OperationIdService(session)

        op = service.generate()

        assert op.id is not None
        assert isinstance(op.code, str)
        assert op.code.startswith("OP-")

        # Estructura esperada: OP-YYYYMMDD-HHMMSS-XXXX
        parts = op.code.split("-")
        assert len(parts) == 4
        _prefix, date_str, time_str, suffix = parts
        assert len(date_str) == 8
        assert len(time_str) == 6
        assert len(suffix) == 4

        # Debe existir exactamente un registro en la tabla.
        db_op = session.get(OperationId, op.id)
        assert db_op is not None
        assert db_op.code == op.code



