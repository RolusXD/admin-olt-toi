from abc import ABC, abstractmethod
import re
from time import perf_counter, sleep
import telnetlib

from app.drivers.errors import DriverTimeoutError


class CliTransport(ABC):
    @abstractmethod
    def connect(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def write_line(self, value: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def read_until_prompt(self, prompt_pattern: re.Pattern[bytes], timeout: int) -> str:
        raise NotImplementedError

    @abstractmethod
    def close(self) -> None:
        raise NotImplementedError


class TelnetlibTransport(CliTransport):
    def __init__(self, host: str, port: int, timeout: int):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.client: telnetlib.Telnet | None = None

    def connect(self) -> None:
        self.client = telnetlib.Telnet(self.host, self.port, self.timeout)

    def write_line(self, value: str) -> None:
        if not self.client:
            raise RuntimeError("Transport is not connected")
        self.client.write(value.encode("ascii") + b"\n")

    def read_until_prompt(self, prompt_pattern: re.Pattern[bytes], timeout: int) -> str:
        if not self.client:
            raise RuntimeError("Transport is not connected")
        chunks: list[bytes] = []
        more_pattern = re.compile(rb"\s*--More--\s*")
        while True:
            index, match, chunk = self.client.expect([prompt_pattern, more_pattern], timeout)
            if index == 0 and match:
                chunks.append(chunk)
                return b"".join(chunks).decode("utf-8", errors="ignore")
            if index == 1 and match:
                chunks.append(more_pattern.sub(b"\n", chunk))
                self.client.write(b" ")
                continue
            raise DriverTimeoutError("Timed out waiting for CLI prompt")

    def read_until(self, expected: bytes, timeout: int) -> str:
        if not self.client:
            raise RuntimeError("Transport is not connected")
        data = self.client.read_until(expected, timeout)
        if expected not in data:
            raise DriverTimeoutError(f"Timed out waiting for {expected.decode(errors='ignore')}")
        return data.decode("utf-8", errors="ignore")

    def capture_initial_banner(self, seconds: int = 15) -> tuple[str, int]:
        if not self.client:
            raise RuntimeError("Transport is not connected")
        chunks: list[bytes] = []
        deadline = perf_counter() + seconds
        while perf_counter() < deadline:
            try:
                chunk = self.client.read_very_eager()
            except EOFError:
                break
            if chunk:
                chunks.append(chunk)
            sleep(0.1)
        raw = b"".join(chunks)
        return raw.decode("utf-8", errors="replace"), len(raw)

    def close(self) -> None:
        if self.client:
            self.client.close()
            self.client = None
