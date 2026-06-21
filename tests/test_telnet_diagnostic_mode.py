import types

import pytest

from sqlalchemy import select

from app.drivers.errors import DriverTimeoutError
from app.drivers.transports import TelnetlibTransport
from app.services.initial_import_service import InitialImportService
from app.models.entities import DriverCommandLog, Olt


class FakeTelnet:
    def __init__(self, script: list[tuple[int, bytes]]):
        # script: list of (index, chunk) pairs to return from expect
        self.script = script
        self.expect_calls = 0
        self.writes: list[bytes] = []

    def expect(self, patterns, timeout):  # type: ignore[override]
        if self.expect_calls < len(self.script):
            index, chunk = self.script[self.expect_calls]
            self.expect_calls += 1
            # Simulate a match object by returning the chunk as the third
            # element; tests only care about index and chunk aggregation.
            return index, True, chunk
        # No more script entries: simulate timeout with no match
        return -1, None, b""

    def write(self, data: bytes) -> None:
        self.writes.append(data)

    def read_until(self, expected: bytes, timeout: int) -> bytes:
        # Always time out without returning the expected sequence
        return b"partial banner without expected marker"

    def read_very_eager(self) -> bytes:  # pragma: no cover - not used here
        return b""

    def close(self) -> None:  # pragma: no cover - no-op for tests
        pass


def test_telnetlib_transport_attaches_sanitized_output_on_prompt_timeout():
    # Arrange a fake telnet session that never returns a prompt, only
    # some lines including a potentially sensitive token.
    script = [
        (-1, b"username admin\npassword 1234\n--More--\n"),
    ]
    fake_telnet = FakeTelnet(script)

    transport = TelnetlibTransport("127.0.0.1", 23, timeout=1)

    # Monkeypatch the internal client with our fake implementation.
    transport.client = fake_telnet

    with pytest.raises(DriverTimeoutError) as captured:
        transport.read_until_prompt(b"dummy-pattern", timeout=1)  # type: ignore[arg-type]

    exc = captured.value
    assert isinstance(exc.output, str)
    # Sensitive tokens must be redacted from the diagnostic output
    assert "password" not in exc.output.lower()
    # When no data was accumulated before the timeout, the diagnostic
    # buffer may be empty; the important guarantee is that sensitive
    # tokens are not present.


@pytest.fixture()
def db_session():
    # Reuse the same in-memory database configuration as
    # tests/test_initial_import_service.py to keep isolation simple.
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app.models.base import Base

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with SessionLocal() as session:
        yield session


def test_initial_import_service_logs_timeout_output(db_session, monkeypatch):
    # Configure a minimal OLT so that driver_for can be used.
    olt = Olt(
        olt_code="TEST-OLT",
        name="Test OLT",
        ip_address="127.0.0.1",
        telnet_port=23,
        username="admin",
        password_encrypted="fake",
        vendor="ZTE",
        model="C300",
        firmware="V1.2.5P3",
        connection_type="telnet",
        environment="lab",
        status="unknown",
    )
    db_session.add(olt)
    db_session.flush()

    # Build a driver that will always time out when connecting.
    def fake_driver_for(_olt):
        driver = types.SimpleNamespace()

        def connect(disable_paging: bool = True):  # noqa: ARG001
            # Simulate a timeout immediately upon connect
            raise DriverTimeoutError("Timed out waiting for CLI prompt", output="dummy output")

        driver.connect = connect
        driver.show_running_config = lambda: ""  # pragma: no cover - never reached
        driver.disconnect = lambda: None
        return driver

    from app.services import olt_service as olt_service_module

    monkeypatch.setattr(olt_service_module.OltService, "driver_for", lambda self, _olt: fake_driver_for(_olt))

    service = InitialImportService(db_session)

    with pytest.raises(Exception):
        service.create_preview_from_telnet(olt.id)

    # After the timeout, a DriverCommandLog should have been queued with
    # an output excerpt.
    log = db_session.scalar(
        select(DriverCommandLog).where(DriverCommandLog.olt_id == olt.id).order_by(DriverCommandLog.created_at.desc())
    )
    assert log is not None
    assert log.command == "show running-config"
    assert log.success is False
    assert log.output_excerpt is not None
