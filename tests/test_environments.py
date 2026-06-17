from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes.dashboard import environment_summary
from app.api.routes.olts import list_olts
from app.models.base import Base
from app.models.entities import Olt, Onu, UnauthorizedOnu
from app.schemas.entities import OltCreate
from app.services.olt_service import OltService
from app.services.onu_discovery_service import OnuDiscoveryService


def make_session():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return SessionLocal()


def create_olt(db, olt_code: str, name: str, environment: str) -> Olt:
    olt = Olt(
        olt_code=olt_code,
        name=name,
        environment=environment,
        vendor="ZTE",
        model="C300",
        firmware="V1.2.5P3",
        ip_address="127.0.0.1",
        telnet_port=23,
        username="admin",
        password_encrypted="secret",
    )
    db.add(olt)
    db.commit()
    db.refresh(olt)
    return olt


def test_olt_can_be_created_as_production_and_lab():
    with make_session() as db:
        service = OltService(db)
        prod_payload = OltCreate(
            olt_code="OLT-PROD-NEW",
            name="Prod",
            environment="production",
            ip_address="10.0.0.1",
            username="admin",
            password="secret",
        )
        lab_payload = OltCreate(
            olt_code="OLT-LAB-NEW",
            name="Lab",
            environment="lab",
            ip_address="10.0.0.2",
            username="admin",
            password="secret",
        )

        prod = service.create(prod_payload.model_dump())
        lab = service.create(lab_payload.model_dump())

        assert prod.environment == "production"
        assert lab.environment == "lab"
        assert service.is_production_olt(prod.id) is True
        assert service.is_production_olt(lab.id) is False


def test_environment_filter_and_expected_codes_work():
    with make_session() as db:
        create_olt(db, "OLT-LAB-ZTE-01", "OLT Lab", "lab")
        create_olt(db, "OLT-PCM-ZTE-01", "FTTH-PCM-ZTE1", "production")

        prod = list_olts(db, environment="production")
        lab = list_olts(db, environment="lab")

        assert [olt.olt_code for olt in prod] == ["OLT-PCM-ZTE-01"]
        assert [olt.olt_code for olt in lab] == ["OLT-LAB-ZTE-01"]


def test_dashboard_separates_environment_statistics():
    with make_session() as db:
        prod = create_olt(db, "OLT-PCM-ZTE-01", "FTTH-PCM-ZTE1", "production")
        lab = create_olt(db, "OLT-LAB-ZTE-01", "OLT Lab", "lab")
        db.add_all(
            [
                Onu(olt_id=prod.id, customer_name="Prod 1", serial_number="PROD0001", onu_interface="gpon-onu_1/1/1:1", onu_type="ZTE", vlan=200, speed_profile="1G", status="online"),
                Onu(olt_id=lab.id, customer_name="Lab 1", serial_number="LAB00001", onu_interface="gpon-onu_1/1/1:2", onu_type="ZTE", vlan=200, speed_profile="1G", status="unknown"),
            ]
        )
        db.commit()

        summary = environment_summary(db)

        assert summary["production"]["olts"] == 1
        assert summary["production"]["onus"] == 1
        assert summary["production"]["online"] == 1
        assert summary["lab"]["olts"] == 1
        assert summary["lab"]["onus"] == 1


def test_onu_discovery_filters_production_by_default_and_keeps_history():
    with make_session() as db:
        prod = create_olt(db, "OLT-PCM-ZTE-01", "FTTH-PCM-ZTE1", "production")
        lab = create_olt(db, "OLT-LAB-ZTE-01", "OLT Lab", "lab")
        db.add_all(
            [
                UnauthorizedOnu(olt_id=prod.id, olt_code_snapshot=prod.olt_code, serial_number="GPONPROD0001", status="pending"),
                UnauthorizedOnu(olt_id=lab.id, olt_code_snapshot=lab.olt_code, serial_number="GPONLAB0001", status="pending"),
            ]
        )
        db.commit()

        service = OnuDiscoveryService(db)

        assert [onu.serial_number for onu in service.list(environment="production")] == ["GPONPROD0001"]
        assert [onu.serial_number for onu in service.list(environment="lab")] == ["GPONLAB0001"]
        assert len(service.list(environment="all")) == 2
        assert db.scalar(select(UnauthorizedOnu).where(UnauthorizedOnu.serial_number == "GPONLAB0001")) is not None
