from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.base import Base
from app.models.entities import EventLog, OperationId
from app.services.operation_log_service import OperationLogService
from app.services.operator_context_service import OperatorContext


def _setup_db() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return SessionLocal()


def test_operation_log_service_records_started_and_success_events_with_context():
    session = _setup_db()
    with session:
        service = OperationLogService(session, origin="api")
        operator = OperatorContext(user_id=1, user_name="admin", role_code="ADMIN", origin="api")

        ctx = service.start(
            event_type="TEST_OPERATION",
            entity_type="olt",
            entity_id=3,
            description="Operacion de prueba iniciada",
            operator=operator,
            action="OLT.TEST",
        )

        # Deberia haberse creado un OperationId y un primer EventLog.
        op = session.scalar(select(OperationId).where(OperationId.code == ctx.operation_id))
        assert op is not None

        started_event = session.scalar(select(EventLog).where(EventLog.operation_id == ctx.operation_id))
        assert started_event is not None
        assert started_event.result == "started"
        assert started_event.user_name == "admin"
        assert started_event.role_code == "ADMIN"
        assert started_event.origin == "api"

        service.success(
            ctx,
            event_type="TEST_OPERATION_COMPLETED",
            entity_type="olt",
            entity_id=3,
            description="Operacion de prueba completada",
            action="OLT.TEST",
        )

        events = list(session.scalars(select(EventLog).where(EventLog.operation_id == ctx.operation_id)))
        assert len(events) == 2
        assert {e.result for e in events} == {"started", "success"}


def test_operation_log_service_records_error_event():
    session = _setup_db()
    with session:
        service = OperationLogService(session, origin="api")
        ctx = service.start(
            event_type="TEST_ERROR_OPERATION",
            entity_type="onu",
            entity_id=10,
            description="Operacion con error iniciada",
        )

        service.error(
            ctx,
            event_type="TEST_ERROR_OPERATION_FAILED",
            entity_type="onu",
            entity_id=10,
            description="Operacion con error fallida",
            error="boom",
        )

        events = list(session.scalars(select(EventLog).where(EventLog.operation_id == ctx.operation_id)))
        assert len(events) == 2
        results = {e.result for e in events}
        assert "started" in results
        assert "failed" in results
