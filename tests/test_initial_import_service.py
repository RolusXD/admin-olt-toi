from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy import create_engine

from app.models.base import Base
from app.models.entities import (
    ConfigSnapshot,
    DriverCommandLog,
    GponProfile,
    ImportJob,
    Nap,
    NapPort,
    Olt,
    Onu,
    OnuType,
    PonPort,
    ProfileCatalog,
    SpeedProfile,
    Vlan,
    Zone,
)
from app.api.routes.onus import list_onus
from app.schemas.entities import OltCreate
from app.schemas.entities import OnuRead
from app.services.initial_import_service import InitialImportService
from app.services.olt_service import OltService
from app.services.provisioning_service import ProvisioningService


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with SessionLocal() as session:
        yield session


@pytest.fixture()
def olt(db_session):
    olt = Olt(
        olt_code="OLT-TEST-01",
        name="OLT Test",
        vendor="ZTE",
        model="C300",
        firmware="V1.2.5P3",
        ip_address="127.0.0.1",
        telnet_port=23,
        username="admin",
        password_encrypted="not-used",
        status="test",
    )
    db_session.add(olt)
    db_session.commit()
    db_session.refresh(olt)
    return olt


@pytest.fixture(scope="module")
def raw_config():
    fixture = Path(__file__).parent / "fixtures" / "zte_c300_running_config.txt"
    return fixture.read_text(encoding="utf-8")


def scalar_count(db_session, model) -> int:
    return len(db_session.scalars(select(model)).all())


def productive_counts(db_session) -> dict:
    return {
        "onus": scalar_count(db_session, Onu),
        "pon_ports": scalar_count(db_session, PonPort),
        "vlans": scalar_count(db_session, Vlan),
        "onu_types": scalar_count(db_session, OnuType),
        "gpon_profiles": scalar_count(db_session, GponProfile),
        "profile_catalogs": scalar_count(db_session, ProfileCatalog),
        "zones": scalar_count(db_session, Zone),
        "naps": scalar_count(db_session, Nap),
    }


def test_preview_from_text_does_not_create_productive_records(db_session, olt, raw_config):
    result = InitialImportService(db_session).create_preview_from_text(olt.id, raw_config)

    assert result["vlans"] == 215
    assert result["tcont_profiles"] == 14
    assert result["traffic_profiles"] == 14
    assert result["onu_types"] == 13
    assert result["pon_ports"] == 16
    assert result["onus"] == 557
    assert "Lagunas" in result["zones_detected"]
    assert "C1" in result["naps_detected"]
    assert scalar_count(db_session, ConfigSnapshot) == 1
    assert scalar_count(db_session, ImportJob) == 1
    assert scalar_count(db_session, Onu) == 0
    assert scalar_count(db_session, PonPort) == 0
    assert scalar_count(db_session, Vlan) == 0
    job = db_session.scalar(select(ImportJob))
    assert job.source == "text"
    db_session.refresh(olt)
    assert olt.initial_import_status == "preview_created"


def test_confirm_import_creates_expected_records_and_is_idempotent(db_session, olt, raw_config):
    preview = InitialImportService(db_session).create_preview_from_text(olt.id, raw_config)
    service = InitialImportService(db_session)

    confirmed = service.confirm_import(preview["import_job_id"])

    assert confirmed["status"] == "confirmed"
    assert scalar_count(db_session, Onu) == 557
    assert scalar_count(db_session, PonPort) == 16
    assert scalar_count(db_session, Vlan) == 215
    assert scalar_count(db_session, OnuType) == 13
    assert scalar_count(db_session, GponProfile) == 28
    assert scalar_count(db_session, ProfileCatalog) == 28
    assert scalar_count(db_session, SpeedProfile) > 0

    vlan_200 = db_session.scalar(select(Vlan).where(Vlan.olt_id == olt.id, Vlan.vlan_id == 200))
    assert vlan_200 is not None
    assert vlan_200.description == "FTTH-TH1"

    onu_type = db_session.scalar(select(OnuType).where(OnuType.olt_id == olt.id, OnuType.name == "BTPON"))
    assert onu_type is not None
    assert onu_type.vendor == "ZTE"
    assert onu_type.model == "C300"
    assert onu_type.firmware == "V1.2.5P3"
    assert onu_type.max_switch_perslot == 8
    assert onu_type.max_flow_perswitch == 8
    assert onu_type.max_iphost == 5

    upload_catalog = db_session.scalar(
        select(ProfileCatalog).where(ProfileCatalog.olt_id == olt.id, ProfileCatalog.direction == "upload", ProfileCatalog.name == "SMARTOLT-1G-UP")
    )
    download_catalog = db_session.scalar(
        select(ProfileCatalog).where(
            ProfileCatalog.olt_id == olt.id,
            ProfileCatalog.direction == "download",
            ProfileCatalog.name == "SMARTOLT-1G-DOWN",
        )
    )
    assert upload_catalog is not None
    assert upload_catalog.vendor == "ZTE"
    assert upload_catalog.model == "C300"
    assert upload_catalog.firmware == "V1.2.5P3"
    assert upload_catalog.maximum_kbps == 1048064
    assert download_catalog is not None
    assert download_catalog.pir_kbps == 1048064

    zone = db_session.scalar(select(Zone).where(Zone.name == "Lagunas"))
    assert zone is not None

    nap = db_session.scalar(select(Nap).where(Nap.zone_id == zone.id, Nap.name == "C1"))
    assert nap is not None
    assert db_session.scalar(select(NapPort).where(NapPort.nap_id == nap.id, NapPort.port_number == 1)) is not None

    onu = db_session.scalar(select(Onu).where(Onu.olt_id == olt.id, Onu.serial_number == "BTPTDD2459E4"))
    assert onu is not None
    assert onu.customer_name == "Jhonny_Apaza"
    assert onu.onu_type == "BTPON"
    assert onu.vlan == 200
    assert onu.speed_profile == "SMARTOLT-1G-DOWN"
    assert onu.raw_description == (
        "$$$$zone_Lagunas_descr_Nap_C1_Puerto_2_Av_Venezuela_"
        "odb_ODN_C01_extid_BTPTDD2459E4_authd_20210521"
    )
    assert onu.parsed_zone_name == "Lagunas"
    assert onu.parsed_nap_name == "C1"
    assert onu.parsed_nap_port == 2
    assert onu.parsed_odn == "ODN_C01"
    assert onu.imported_from_config is True
    assert onu.source == "cli_import"
    assert onu.import_source == "text_input"
    assert onu.olt_code_snapshot == "OLT-TEST-01"
    occupied_port = db_session.scalar(select(NapPort).where(NapPort.nap_id == nap.id, NapPort.port_number == 2))
    assert occupied_port.status == "occupied"
    assert occupied_port.onu_id == onu.id

    upload_catalog.source = "manual"
    upload_catalog.is_active = False
    upload_catalog.maximum_kbps = 123
    db_session.commit()

    counts_before_repeat = productive_counts(db_session)
    service.confirm_import(preview["import_job_id"])

    assert productive_counts(db_session) == counts_before_repeat
    db_session.refresh(upload_catalog)
    assert upload_catalog.source == "manual"
    assert upload_catalog.is_active is False
    assert upload_catalog.maximum_kbps == 123
    db_session.refresh(olt)
    assert olt.initial_import_status == "confirmed"
    assert olt.last_import_job_id == preview["import_job_id"]
    assert olt.last_import_confirmed_at is not None
    assert ProvisioningService(db_session).can_provision(olt.id) is True


def test_olt_code_validation_and_uniqueness(db_session):
    with pytest.raises(Exception):
        OltCreate(
            name="OLT Sin Codigo",
            ip_address="10.0.0.1",
            username="admin",
            password="secret",
        )
    with pytest.raises(Exception):
        OltCreate(
            olt_code="OLT CON ESPACIOS",
            name="OLT Espacios",
            ip_address="10.0.0.2",
            username="admin",
            password="secret",
        )

    service = OltService(db_session)
    created = service.create(
        {
            "olt_code": "olt-prod-01",
            "name": "OLT Produccion",
            "ip_address": "10.0.0.3",
            "telnet_port": 23,
            "username": "admin",
            "password": "secret",
            "vendor": "ZTE",
            "model": "C300",
            "firmware": "V1.2.5P3",
            "connection_type": "telnet",
            "status": "unknown",
        }
    )
    assert created.olt_code == "OLT-PROD-01"
    assert created.initial_import_status == "pending"
    assert ProvisioningService(db_session).can_provision(created.id) is False

    with pytest.raises(ValueError, match="olt_code already exists"):
        service.create(
            {
                "olt_code": "OLT-PROD-01",
                "name": "OLT Produccion 2",
                "ip_address": "10.0.0.4",
                "telnet_port": 23,
                "username": "admin",
                "password": "secret",
                "vendor": "ZTE",
                "model": "C300",
                "firmware": "V1.2.5P3",
                "connection_type": "telnet",
                "status": "unknown",
            }
        )


class FakeImportDriver:
    def __init__(self, raw_config: str):
        self.raw_config = raw_config
        self.commands: list[str] = []
        self.connected = False

    def connect(self, disable_paging=True):
        assert disable_paging is False
        self.connected = True

    def disconnect(self):
        self.connected = False

    def show_running_config(self):
        self.commands.append("show running-config")
        return self.raw_config


def test_preview_sources_and_telnet_read_only(db_session, olt, raw_config, monkeypatch):
    driver = FakeImportDriver(raw_config)
    monkeypatch.setattr(OltService, "driver_for", lambda _self, _olt: driver)

    telnet_preview = InitialImportService(db_session).create_preview_from_telnet(olt.id)
    file_preview = InitialImportService(db_session).create_preview_from_text(olt.id, raw_config, source="file")

    telnet_job = db_session.get(ImportJob, telnet_preview["import_job_id"])
    file_job = db_session.get(ImportJob, file_preview["import_job_id"])
    assert telnet_job.source == "telnet"
    assert file_job.source == "file"
    assert driver.commands == ["show running-config"]
    assert not any(command.startswith(("configure", "write", "reboot", "reload", "reset", "delete", "erase")) for command in driver.commands)
    log = db_session.scalar(select(DriverCommandLog).where(DriverCommandLog.command == "show running-config"))
    assert log is not None
    assert log.read_only is True

    InitialImportService(db_session).confirm_import(telnet_job.id)
    onu = db_session.scalar(select(Onu).where(Onu.olt_id == olt.id, Onu.serial_number == "BTPTDD2459E4"))
    assert onu.import_source == "telnet_running_config"
    assert onu.olt_code_snapshot == olt.olt_code


def test_reimport_does_not_delete_existing_records(db_session, olt, raw_config):
    service = InitialImportService(db_session)
    first = service.create_preview_from_text(olt.id, raw_config)
    service.confirm_import(first["import_job_id"])
    db_session.add(
        Onu(
            olt_id=olt.id,
            olt_code_snapshot=olt.olt_code,
            customer_name="Manual",
            serial_number="MANUAL123",
            onu_interface="gpon-onu_1/2/99:1",
            onu_type="BTPON",
            vlan=200,
            speed_profile="manual",
            import_source="manual",
        )
    )
    db_session.commit()

    second = service.create_preview_from_text(olt.id, raw_config)
    service.confirm_import(second["import_job_id"])

    assert db_session.scalar(select(Onu).where(Onu.serial_number == "MANUAL123")) is not None


def test_onus_response_includes_olt_identity_and_filter_by_olt_code(db_session, olt, raw_config):
    preview = InitialImportService(db_session).create_preview_from_text(olt.id, raw_config)
    InitialImportService(db_session).confirm_import(preview["import_job_id"])

    filtered = list_onus(db_session, q=None, olt_code=olt.olt_code)
    assert filtered
    serialized = OnuRead.model_validate(filtered[0]).model_dump()
    assert serialized["olt_id"] == olt.id
    assert serialized["olt_code"] == olt.olt_code
    assert serialized["olt_name"] == olt.name
    assert serialized["olt_code_snapshot"] == olt.olt_code
    assert list_onus(db_session, q=None, olt_code="OLT-NO-EXISTE") == []
