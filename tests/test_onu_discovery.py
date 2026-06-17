from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import pytest

from app.models.base import Base
from app.models.entities import DriverCommandLog, EventLog, Olt, UnauthorizedOnu, UnauthorizedOnuEvent
from app.services.onu_discovery_service import OnuDiscoveryService
from app.services.olt_service import OltService
from app.drivers.zte.c300_v125p3_telnet.zte_c300_uncfg_parser import parse_show_gpon_onu_uncfg


UNCFG_OUTPUT = """
show gpon onu uncfg
-----------------------------------------------
Interface          SN             Type
gpon-olt_1/2/3     ZTEGC0F5D7A9   ZTE-F660
-----------------------------------------------
FTTH-PCM-ZTE1#
"""


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
        olt_code="OLT-DISCOVERY",
        name="OLT Discovery",
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


class FakeDiscoveryDriver:
    def __init__(self, output=UNCFG_OUTPUT):
        self.output = output
        self.commands: list[str] = []
        self.connected = False

    def connect(self, disable_paging=True):
        assert disable_paging is False
        self.connected = True

    def disconnect(self):
        self.connected = False

    def show_uncfg_raw(self):
        self.commands.append("show gpon onu uncfg")
        return self.output


def service_with_driver(db_session, driver):
    service = OnuDiscoveryService(db_session)
    service.olt_service.driver_for = lambda _olt: driver
    return service


def test_discover_executes_only_uncfg_and_logs_read_only(db_session, olt):
    driver = FakeDiscoveryDriver()

    result = service_with_driver(db_session, driver).discover(olt)

    assert result["detected"] == 1
    assert result["new"] == 1
    assert driver.commands == ["show gpon onu uncfg"]
    assert not any(command.startswith(("configure", "write", "reboot", "reload", "reset", "delete", "erase")) for command in driver.commands)
    log = db_session.scalar(select(DriverCommandLog).where(DriverCommandLog.olt_id == olt.id))
    assert log.command == "show gpon onu uncfg"
    assert log.read_only is True
    assert log.success is True


def test_discover_does_not_duplicate_and_increments_times_detected(db_session, olt):
    driver = FakeDiscoveryDriver()
    service = service_with_driver(db_session, driver)

    first = service.discover(olt)
    second = service.discover(olt)

    onu = db_session.scalar(select(UnauthorizedOnu).where(UnauthorizedOnu.serial_number == "ZTEGC0F5D7A9"))
    assert first["new"] == 1
    assert second["new"] == 0
    assert second["existing"] == 1
    assert len(db_session.scalars(select(UnauthorizedOnu)).all()) == 1
    assert onu.times_detected == 2
    assert onu.olt_code_snapshot == "OLT-DISCOVERY"
    assert onu.pon_port_interface == "gpon-olt_1/2/3"
    assert onu.detected_vendor == "ZTE"


def test_ignore_restore_ready_and_filter_by_olt_code(db_session, olt):
    service = service_with_driver(db_session, FakeDiscoveryDriver())
    service.discover(olt)
    onu = db_session.scalar(select(UnauthorizedOnu).where(UnauthorizedOnu.serial_number == "ZTEGC0F5D7A9"))

    service.set_status(onu, "ignored")
    assert onu.status == "ignored"
    service.set_status(onu, "pending")
    assert onu.status == "pending"
    service.set_status(onu, "ready_for_provisioning")
    assert onu.status == "ready_for_provisioning"

    assert service.list(olt_code="OLT-DISCOVERY")[0].id == onu.id
    assert service.list(olt_code="OLT-OTHER") == []
    events = db_session.scalars(select(UnauthorizedOnuEvent).where(UnauthorizedOnuEvent.unauthorized_onu_id == onu.id)).all()
    assert {event.event_type for event in events} >= {"detected", "ignored", "restored", "ready_for_provisioning"}


def test_recurrent_pending_creates_alert_after_more_than_three_detections(db_session, olt):
    service = service_with_driver(db_session, FakeDiscoveryDriver())

    for _ in range(4):
        service.discover(olt)

    alert = db_session.scalar(select(EventLog).where(EventLog.event_type == "UNAUTHORIZED_ONU_RECURRENT"))
    assert alert is not None
    assert "ONU pendiente recurrente" in alert.description


def test_uncfg_parser_handles_real_line_with_prompt_suffix():
    output = "show gpon onu uncfg\r\nOnuIndex                 Sn                  State\r\n" \
        "---------------------------------------------------------------------\r\n" \
        "gpon-onu_1/2/15:1        GPON00CBAC10        unknown             FTTH-PCM-ZTE1#"

    parsed = parse_show_gpon_onu_uncfg(output)

    assert len(parsed) == 1
    assert parsed[0].serial_number == "GPON00CBAC10"
    assert parsed[0].pon_port_interface == "gpon-olt_1/2/15"
    assert parsed[0].slot == 2
    assert parsed[0].port == 15
    assert parsed[0].detected_type is None
