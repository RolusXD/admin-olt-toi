import types

import pytest

from app.drivers.errors import DriverCommandError
from app.drivers.transports import TelnetlibTransport


class EofTelnet:
    """Fake telnet client that immediately closes on expect()."""

    def __init__(self):
        self.writes: list[bytes] = []

    def expect(self, patterns, timeout):  # type: ignore[override]
        raise EOFError("telnet connection closed")

    def write(self, data: bytes) -> None:
        self.writes.append(data)

    def read_until(self, expected: bytes, timeout: int) -> bytes:  # pragma: no cover - not used here
        return b""

    def read_very_eager(self) -> bytes:  # pragma: no cover - not used here
        return b""

    def close(self) -> None:  # pragma: no cover - no-op for tests
        pass


def test_telnetlib_transport_raises_driver_command_error_on_eof_during_prompt_wait(monkeypatch):
    """When the remote end closes the connection while waiting for a prompt,
    TelnetlibTransport.read_until_prompt should raise DriverCommandError so
    higher layers can attach diagnostic output via TELNET_DIAGNOSTIC_MODE.
    """

    transport = TelnetlibTransport("127.0.0.1", 23, timeout=1)
    eof_client = EofTelnet()
    transport.client = eof_client

    pattern = types.SimpleNamespace()
    pattern.pattern = b"#"  # any bytes; our fake never reaches this

    with pytest.raises(DriverCommandError) as captured:
        transport.read_until_prompt(pattern, timeout=1)  # type: ignore[arg-type]

    exc = captured.value
    assert exc.command == "show running-config"
    assert "EOF received from OLT" in str(exc)
