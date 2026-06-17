import os
import sys
import types

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
fake_telnetlib = types.ModuleType("telnetlib")
fake_telnetlib.Telnet = object
sys.modules.setdefault("telnetlib", fake_telnetlib)
fake_fernet_module = types.ModuleType("cryptography.fernet")


class FakeFernet:
    def __init__(self, *_args, **_kwargs):
        pass

    def encrypt(self, value: bytes) -> bytes:
        return value

    def decrypt(self, value: bytes) -> bytes:
        return value


fake_fernet_module.Fernet = FakeFernet
fake_crypto_module = types.ModuleType("cryptography")
fake_crypto_module.fernet = fake_fernet_module
sys.modules.setdefault("cryptography", fake_crypto_module)
sys.modules.setdefault("cryptography.fernet", fake_fernet_module)
fake_jose_module = types.ModuleType("jose")
fake_jwt_module = types.SimpleNamespace(encode=lambda *_args, **_kwargs: "token")
fake_jose_module.jwt = fake_jwt_module
sys.modules.setdefault("jose", fake_jose_module)
fake_passlib_module = types.ModuleType("passlib")
fake_passlib_context_module = types.ModuleType("passlib.context")


class FakeCryptContext:
    def __init__(self, *_args, **_kwargs):
        pass

    def verify(self, plain: str, hashed: str) -> bool:
        return plain == hashed

    def hash(self, plain: str) -> str:
        return plain


fake_passlib_context_module.CryptContext = FakeCryptContext
fake_passlib_module.context = fake_passlib_context_module
sys.modules.setdefault("passlib", fake_passlib_module)
sys.modules.setdefault("passlib.context", fake_passlib_context_module)

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy import create_engine

from app.drivers.errors import DriverCommandError
from app.drivers.zte.c300_v125p3_telnet.driver import ZteC300V125P3TelnetDriver
from app.drivers.zte.c300_v125p3_telnet.parsers import CardInfo, OnuPower, OnuState
from app.models.base import Base
from app.models.entities import DriverCommandLog, Olt, Onu
from app.schemas.entities import OltCreate, OltRead
from app.services.olt_cli_service import OltCliService
from app.services.olt_service import OltService


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
        olt_code="OLT-READ-ONLY",
        name="OLT Read Only",
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


def add_onus(db_session, olt, total=8):
    for index in range(1, total + 1):
        db_session.add(
            Onu(
                olt_id=olt.id,
                customer_name=f"Cliente {index}",
                serial_number=f"ZTEG000000{index:02d}",
                onu_interface=f"gpon-onu_1/2/3:{index}",
                onu_type="BTPON",
                vlan=200,
                speed_profile="SMARTOLT-1G-DOWN",
                speed_profile_up="SMARTOLT-1G-UP",
                speed_profile_down="SMARTOLT-1G-DOWN",
                status="online",
            )
        )
    db_session.commit()


class FakeReadOnlyDriver:
    def __init__(self):
        self.commands: list[str] = []
        self.connected = False
        self.last_prompt = "FTTH-PCM-ZTE1#"

    def connect(self, disable_paging=True):
        self.connected = True

    def disconnect(self):
        self.connected = False

    def execute(self, command: str, read_only: bool = True):
        self.commands.append(command)
        return "ZXA10 C300 Software Version V1.2.5P3"

    def show_card(self):
        self.commands.append("show card")
        return [CardInfo(slot="1/2", card_type="GTGO", status="online")]

    def show_onu_state(self):
        self.commands.append("show gpon onu state")
        return [
            OnuState("gpon-onu_1/2/3:1", "ZTEG00000001", "online", "working", None),
            OnuState("gpon-onu_1/2/3:2", "ZTEG00000002", "offline", "offline", "LOS"),
            OnuState("gpon-onu_1/2/3:3", "ZTEG00000003", "offline", "offline", "DyingGasp"),
        ]

    def show_onu_rx_power(self, interface: str):
        self.commands.append(f"show pon power onu-rx {interface}")
        return OnuPower(interface=interface, power_dbm=-23.5)

    def show_onu_tx_power(self, interface: str):
        self.commands.append(f"show pon power onu-tx {interface}")
        return OnuPower(interface=interface, power_dbm=2.1)


class FakeBannerTransport:
    def __init__(self):
        self.connected = False
        self.closed = False
        self.write_attempts: list[str] = []

    def connect(self):
        self.connected = True

    def write_line(self, value: str):
        self.write_attempts.append(value)
        raise AssertionError("telnet-debug must not send data")

    def capture_initial_banner(self, seconds: int = 15):
        assert seconds == 15
        return "Username:", 9

    def close(self):
        self.closed = True


def service_with_driver(db_session, driver):
    service = OltCliService(db_session)
    service.olt_service.driver_for = lambda _olt: driver
    return service


def test_read_only_check_does_not_execute_dangerous_commands(db_session, olt):
    driver = FakeReadOnlyDriver()
    result = service_with_driver(db_session, driver).read_only_check(olt)

    assert result["connection_success"] is True
    assert result["prompt_detected"] == "FTTH-PCM-ZTE1#"
    assert result["onu_counts"] == {"total": 3, "working": 1, "offline": 0, "los": 1, "dying_gasp": 1}
    assert driver.commands == ["show version-running", "show card", "show gpon onu state"]
    assert not any(command.startswith(("configure", "write", "reboot", "reload", "reset", "delete", "erase")) for command in driver.commands)


def test_sync_power_with_limit_processes_no_more_than_limit(db_session, olt):
    add_onus(db_session, olt, total=8)
    driver = FakeReadOnlyDriver()

    result = service_with_driver(db_session, driver).sync_power(olt, limit=5)

    assert result["working_onus"] == 5
    assert result["power_samples"] == 5
    assert result["commands"] == 10
    assert len([command for command in driver.commands if command.startswith("show pon power onu-rx")]) == 5


def test_sync_power_with_manual_list_only_processes_interfaces(db_session, olt):
    add_onus(db_session, olt, total=5)
    driver = FakeReadOnlyDriver()

    result = service_with_driver(db_session, driver).sync_power(
        olt,
        only_onu_interfaces=["gpon-onu_1/2/3:2", "gpon-onu_1/2/3:4"],
    )

    assert result["working_onus"] == 2
    assert result["power_samples"] == 2
    assert [command for command in driver.commands if command.startswith("show pon power onu-rx")] == [
        "show pon power onu-rx gpon-onu_1/2/3:2",
        "show pon power onu-rx gpon-onu_1/2/3:4",
    ]


def test_command_logs_records_include_read_only_metadata(db_session, olt):
    db_session.add(
        DriverCommandLog(
            olt_id=olt.id,
            command="show card",
            success=True,
            read_only=True,
            duration_ms=12,
        )
    )
    db_session.commit()

    log = db_session.scalar(select(DriverCommandLog).where(DriverCommandLog.olt_id == olt.id))
    assert log.command == "show card"
    assert log.read_only is True
    assert log.duration_ms == 12


def test_dangerous_command_with_read_only_true_is_blocked_and_can_be_logged(db_session, olt):
    driver = ZteC300V125P3TelnetDriver(
        host="127.0.0.1",
        port=23,
        username="admin",
        password="secret",
        transport=FakeReadOnlyDriver(),
    )
    service = OltCliService(db_session)

    with pytest.raises(DriverCommandError):
        service._call_read_only(olt.id, "write", lambda: driver.execute("write", read_only=True))
    db_session.commit()

    log = db_session.scalar(select(DriverCommandLog).where(DriverCommandLog.olt_id == olt.id))
    assert log is not None
    assert log.command == "write"
    assert log.success is False
    assert log.read_only is True
    assert "Blocked" in log.error_message


def test_create_olt_without_password_fails_validation():
    with pytest.raises(ValidationError):
        OltCreate(
            olt_code="OLT-PROD-01",
            name="OLT Produccion",
            ip_address="10.0.0.10",
            telnet_port=23,
            username="admin",
        )


def test_create_olt_with_empty_password_fails_validation():
    with pytest.raises(ValidationError):
        OltCreate(
            olt_code="OLT-PROD-01",
            name="OLT Produccion",
            ip_address="10.0.0.10",
            telnet_port=23,
            username="admin",
            password="",
        )


def test_create_olt_with_spaces_password_fails_validation():
    with pytest.raises(ValidationError):
        OltCreate(
            olt_code="OLT-PROD-01",
            name="OLT Produccion",
            ip_address="10.0.0.10",
            telnet_port=23,
            username="admin",
            password="   ",
        )


def test_update_olt_without_password_keeps_existing_secret(db_session, olt):
    olt.password_encrypted = "encrypted-current-password"
    db_session.commit()

    updated = OltService(db_session).update(
        olt,
        {
            "name": "OLT Editada",
            "ip_address": "10.0.0.11",
            "telnet_port": 23,
            "username": "admin2",
            "password": "",
            "connection_type": "telnet",
        },
    )

    assert updated.name == "OLT Editada"
    assert updated.password_encrypted == "encrypted-current-password"


def test_olt_read_does_not_expose_plain_password(db_session, olt):
    serialized = OltRead.model_validate(olt).model_dump()

    assert "password" not in serialized
    assert "password_encrypted" not in serialized
    assert serialized["connection_type"] == "telnet"
    assert serialized["has_password"] is True


def test_read_only_check_rejects_olt_without_saved_password(db_session, olt):
    olt.password_encrypted = ""
    db_session.commit()
    driver = FakeReadOnlyDriver()

    with pytest.raises(ValueError, match="no tiene contraseña guardada"):
        service_with_driver(db_session, driver).read_only_check(olt)

    assert driver.commands == []


def test_telnet_debug_captures_banner_without_sending_commands(db_session, olt):
    transport = FakeBannerTransport()

    result = OltCliService(db_session).telnet_debug(olt, transport=transport)

    assert result == {"raw_banner": "Username:", "bytes_received": 9, "timeout": False}
    assert transport.connected is True
    assert transport.closed is True
    assert transport.write_attempts == []
    log = db_session.scalar(select(DriverCommandLog).where(DriverCommandLog.olt_id == olt.id))
    assert log.command == "TELNET_DEBUG"
    assert log.success is True
    assert log.read_only is True
    assert log.output_excerpt == "Username:"
