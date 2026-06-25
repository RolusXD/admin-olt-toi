from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.entities import EventLog
from app.services.event_service import EventService


def _setup_db() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return SessionLocal()


def test_event_service_records_basic_event():
    """EventService debe seguir funcionando con la firma histórica mínima."""

    session = _setup_db()
    with session:
        service = EventService(session)

        event = service.record(
            event_type="TEST_EVENT",
            entity_type="test_entity",
            entity_id=123,
            description="Evento de prueba basico",
        )

        assert event.id is not None
        assert event.event_type == "TEST_EVENT"
        assert event.entity_type == "test_entity"
        assert event.entity_id == 123
        assert event.description == "Evento de prueba basico"

        # Campos extendidos deben permanecer opcionales.
        assert event.operation_id is None
        assert event.user_id is None
        assert event.user_name is None
        assert event.role_code is None
        assert event.origin is None
        assert event.result is None
        assert event.action is None
        assert event.duration_ms is None
        assert event.reason is None
        assert event.error is None


def test_event_service_records_extended_context():
    """EventService debe aceptar el contexto extendido de auditoria."""

    session = _setup_db()
    with session:
        service = EventService(session)

        event = service.record(
            event_type="OPERATION_EXECUTED",
            entity_type="olt",
            entity_id=3,
            description="Operacion de prueba con contexto completo",
            operation_id="OP-2026-ABCDEF01",
            user_id=None,
            user_name="raul",
            role_code="ADMIN",
            origin="api",
            result="success",
            action="OLT.TEST",
            duration_ms=1500,
            reason="prueba unitaria",
            error=None,
        )

        assert event.operation_id == "OP-2026-ABCDEF01"
        assert event.user_name == "raul"
        assert event.role_code == "ADMIN"
        assert event.origin == "api"
        assert event.result == "success"
        assert event.action == "OLT.TEST"
        assert event.duration_ms == 1500
        assert event.reason == "prueba unitaria"

        # Verificar que el registro existe en base de datos.
        db_event = session.get(EventLog, event.id)
        assert db_event is not None
        assert db_event.operation_id == event.operation_id


