import os

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

# Forzar una URL SQLite ligera antes de importar módulos que crean el engine
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")

from app.models.base import Base
from app.models.entities import Olt, Onu
from app.services.onu_data_quality_service import OnuDataQualityService
from app.api.routes.olts import olt_data_quality_summary
from app.api.routes.onus import list_onus_data_quality


def _setup_db():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return engine, SessionLocal


def _create_sample_data(session: Session) -> int:
    olt = Olt(
        olt_code="OLT-QA-01",
        name="OLT QA 01",
        ip_address="127.0.0.1",
        telnet_port=23,
        username="admin",
        password_encrypted="not-used",
    )
    session.add(olt)
    session.commit()
    session.refresh(olt)

    # Una ONU completa
    onu_complete = Onu(
        olt_id=olt.id,
        olt_code_snapshot=olt.olt_code,
        customer_name="Cliente Completo",
        serial_number="SN-COMPLETE",
        onu_interface="gpon-onu_1/1/1:1",
        onu_type="BTPON",
        vlan=200,
        speed_profile="imported",
        zone_id=None,
        zone_name="Lagunas",
        address_reference="Calle 1 #123",
        nap_id=None,
        nap_name="NAP-01",
        nap_port=5,
        external_id="EXT-COMPLETE",
    )

    # Una ONU legacy_incomplete
    onu_incomplete = Onu(
        olt_id=olt.id,
        olt_code_snapshot=olt.olt_code,
        customer_name=" ",
        serial_number="SN-INCOMPLETE",
        onu_interface="gpon-onu_1/1/1:2",
        onu_type="BTPON",
        vlan=0,
        speed_profile="imported",
        zone_name="SIN_ZONA",
    )

    session.add_all([onu_complete, onu_incomplete])
    session.commit()

    service = OnuDataQualityService(session)
    for onu in session.scalars(select(Onu)).all():
        service.evaluate(onu)
    session.commit()

    return olt.id


def test_olt_data_quality_summary(monkeypatch):
    engine, SessionLocal = _setup_db()

    with SessionLocal() as session:
        olt_id = _create_sample_data(session)

        data = olt_data_quality_summary(olt_id=olt_id, db=session)

        assert data["olt_id"] == olt_id
        assert data["total_onus"] == 2
        # Con los datos de prueba, la ONU "completa" carece de auth_date,
        # por lo que se clasifica como needs_review, no como complete.
        assert data["complete"] == 0
        assert data["legacy_incomplete"] == 1
        assert data["needs_review"] == 1
        assert data["blocked"] == 0
        assert 0 <= data["quality_score"] <= 100


def test_onus_data_quality_listing(monkeypatch):
    engine, SessionLocal = _setup_db()

    with SessionLocal() as session:
        olt_id = _create_sample_data(session)

        # Sin filtros debe devolver las dos ONUs
        items = list_onus_data_quality(db=session, olt_id=olt_id, status=None, zone=None, nap=None)
        assert len(items) == 2

        statuses = {item.data_quality_status for item in items}
        # La ONU "completa" carece de auth_date, por lo que queda en needs_review.
        assert "needs_review" in statuses
        assert "legacy_incomplete" in statuses

        # Filtro por estado de calidad
        review_items = list_onus_data_quality(db=session, olt_id=olt_id, status="needs_review", zone=None, nap=None)
        assert len(review_items) == 1
        assert review_items[0].serial_number == "SN-COMPLETE"
