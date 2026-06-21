import pytest

from app.drivers.errors import DriverCommandError
from app.drivers.transports import TelnetlibTransport
from app.drivers.zte.c300_v125p3_telnet.driver import ZteC300V125P3TelnetDriver


class FakeTelnetClient:
    """Minimal fake telnet client for phased logging tests.

    It simulates a successful login, disable-paging command, running-config
    capture, and either a successful or failing prompt confirmation.
    """

    def __init__(self, script):
        # script: list of (index, chunk) tuples returned from expect()
        self.script = script
        self.expect_calls = 0
        self.writes: list[bytes] = []

    def expect(self, patterns, timeout):  # type: ignore[override]
        if self.expect_calls >= len(self.script):
            raise EOFError("telnet connection closed")
        index, chunk = self.script[self.expect_calls]
        self.expect_calls += 1
        # Simulate a match object by returning a truthy value
        return index, True, chunk

    def write(self, data: bytes) -> None:
        self.writes.append(data)

    def read_until(self, expected: bytes, timeout: int) -> bytes:  # pragma: no cover - not used in these tests
        return b""

    def read_very_eager(self) -> bytes:  # pragma: no cover - not used here
        return b""

    def close(self) -> None:  # pragma: no cover - no-op for tests
        pass


@pytest.fixture()
def driver_with_fake_transport(monkeypatch):
    transport = TelnetlibTransport("127.0.0.1", 23, timeout=1)
    driver = ZteC300V125P3TelnetDriver(
        host="127.0.0.1",
        port=23,
        username="admin",
        password="admin",
        timeout=1,
        transport=transport,
    )
    # Avoid creating a real telnetlib.Telnet instance; tests
    # provide a FakeTelnetClient directly on the transport and bypass
    # low-level read_until network behaviour.
    driver.transport.connect = lambda: None  # type: ignore[assignment]
    driver.transport.read_until = (  # type: ignore[assignment]
        lambda expected, timeout: expected.decode("ascii", errors="ignore")
    )
    return driver


def test_show_running_config_succeeds_with_single_prompt(driver_with_fake_transport):
    """show_running_config debe considerar éxito con un único prompt estable.

    El driver ya no envía una línea vacía extra ni realiza una segunda
    lectura de confirmación; si el output contiene un prompt final estable,
    debe devolverlo sin errores.
    """
    prompt = b"ZXAN#\n"
    script = [
        (0, prompt),  # login prompt
        (0, prompt),  # after terminal length 0
        (0, b"output...\n" + prompt),  # after show running-config
    ]
    fake_client = FakeTelnetClient(script)
    driver_with_fake_transport.transport.client = fake_client  # type: ignore[assignment]

    # Connect (login + disable paging) and then run show_running_config
    driver_with_fake_transport.connect(disable_paging=True)

    output = driver_with_fake_transport.show_running_config()
    assert "output..." in output


def test_show_running_config_logs_error_phase_on_driver_command_error(driver_with_fake_transport):
    # Simulate a successful login and disable paging, but make the
    # show running-config phase fail via DriverCommandError.
    prompt = b"ZXAN#\n"
    bad_output = b"% Invalid input\n" + prompt
    # login prompt, prompt after terminal length 0, then bad output for show running-config
    script = [
        (0, prompt),
        (0, prompt),
        (0, bad_output),
    ]
    fake_client = FakeTelnetClient(script)
    driver_with_fake_transport.transport.client = fake_client  # type: ignore[assignment]

    driver_with_fake_transport.connect(disable_paging=True)

    with pytest.raises(DriverCommandError):
        driver_with_fake_transport.show_running_config()
