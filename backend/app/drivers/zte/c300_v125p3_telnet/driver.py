from dataclasses import dataclass
import re

from loguru import logger

from app.drivers.base import DeviceDriver
from app.drivers.errors import DriverCommandError
from app.drivers.transports import CliTransport, TelnetlibTransport
from app.drivers.zte.c300_v125p3_telnet.parsers import (
    parse_onu_detail,
    parse_onu_power,
    parse_onu_state,
    parse_show_card,
    parse_uncfg,
)


SUPPORTED_COMMANDS = {
    "show_card": "show card",
    "show_onu_state": "show gpon onu state",
    "show_onu_detail": "show gpon onu detail-info",
    "show_onu_rx_power": "show pon power onu-rx",
    "show_onu_tx_power": "show pon power onu-tx",
    "show_uncfg": "show gpon onu uncfg",
    "show_running_config": "show running-config",
    "show_version_running": "show version-running",
    "show_version": "show version",
}

COMMAND_ERRORS = (
    "% Incomplete command",
    "% Invalid input",
    "% Unrecognized command",
    "% Ambiguous command",
)
BLOCKED_READ_ONLY_COMMANDS = (
    "configure",
    "conf",
    "write",
    "reboot",
    "reload",
    "delete",
    "erase",
    "reset",
)
READ_ONLY_COMMAND_PATTERNS = (
    re.compile(r"^show version-running$", re.I),
    re.compile(r"^show card$", re.I),
    re.compile(r"^show gpon onu state$", re.I),
    re.compile(r"^show gpon onu uncfg$", re.I),
    re.compile(r"^show running-config$", re.I),
    re.compile(r"^show pon power onu-rx gpon-onu_\d+/\d+/\d+:\d+$", re.I),
    re.compile(r"^show pon power onu-tx gpon-onu_\d+/\d+/\d+:\d+$", re.I),
    re.compile(r"^show interface(?:\s+(?:brief|gei|xgei|gei_\d+/\d+/\d+(?::\d+)?|xgei_\d+/\d+/\d+(?::\d+)?))?$", re.I),
    re.compile(r"^show vlan(?:\s+brief)?$", re.I),
)
# ZTE changes the parenthesized context name depending on firmware and command,
# for example (config-if), (config-gpon-onu-mng) or (gpon-onu-mng).
PROMPT_PATTERN = re.compile(rb"(?m)(?:[\w.-]+)(?:\([^\r\n#\)]*\))?#\s*$")


@dataclass
class ZteC300V125P3TelnetDriver(DeviceDriver):
    host: str
    port: int
    username: str
    password: str
    timeout: int = 10
    transport: CliTransport | None = None

    def __post_init__(self) -> None:
        self.transport = self.transport or TelnetlibTransport(self.host, self.port, self.timeout)
        self.prompt_pattern = PROMPT_PATTERN
        self.last_prompt: str | None = None

    def connect(self, disable_paging: bool = True) -> None:
        logger.info("Connecting to ZTE C300 {}:{}", self.host, self.port)
        assert self.transport is not None
        self.transport.connect()
        if hasattr(self.transport, "read_until"):
            self.transport.read_until(b"Username:", self.timeout)
        self.transport.write_line(self.username)
        if hasattr(self.transport, "read_until"):
            self.transport.read_until(b"Password:", self.timeout)
        self.transport.write_line(self.password)
        initial_output = self.transport.read_until_prompt(self.prompt_pattern, self.timeout)
        self.last_prompt = self._extract_prompt(initial_output)
        if disable_paging:
            try:
                self.execute("terminal length 0", read_only=False)
            except Exception as exc:
                logger.warning("OLT did not accept terminal length 0: {}", exc)

    def disconnect(self, send_exit: bool = True) -> None:
        if self.transport:
            try:
                if send_exit:
                    self.transport.write_line("exit")
            except Exception:
                pass
            finally:
                self.transport.close()

    def execute(self, command: str, read_only: bool = True, timeout: int | None = None) -> str:
        if not self.transport:
            raise RuntimeError("Driver is not connected")
        if read_only:
            self._ensure_read_only_command(command)
        self.transport.write_line(command)
        output = self.transport.read_until_prompt(self.prompt_pattern, timeout or self.timeout)
        self.last_prompt = self._extract_prompt(output) or self.last_prompt
        for error in COMMAND_ERRORS:
            if error in output:
                raise DriverCommandError(command=command, message=error, output=output)
        return output

    def _ensure_read_only_command(self, command: str) -> None:
        normalized = command.strip().lower()
        if any(normalized == blocked or normalized.startswith(f"{blocked} ") for blocked in BLOCKED_READ_ONLY_COMMANDS):
            raise DriverCommandError(command=command, message="Blocked non-read-only command", output="")
        if not any(pattern.match(command.strip()) for pattern in READ_ONLY_COMMAND_PATTERNS):
            raise DriverCommandError(command=command, message="Blocked command outside read-only whitelist", output="")

    def _extract_prompt(self, output: str) -> str | None:
        for line in reversed(output.splitlines()):
            stripped = line.strip()
            if stripped.endswith("#"):
                return stripped
        return None

    def run_wrapper(self, wrapper_name: str) -> str:
        command = SUPPORTED_COMMANDS[wrapper_name]
        return self.execute(command)

    def show_version_running(self) -> str:
        return self.execute(SUPPORTED_COMMANDS["show_version_running"])

    def show_card(self) -> list:
        return parse_show_card(self.execute(SUPPORTED_COMMANDS["show_card"]))

    def show_onu_state(self) -> list:
        return parse_onu_state(self.execute(SUPPORTED_COMMANDS["show_onu_state"]))

    def show_onu_detail(self, interface: str):
        return parse_onu_detail(self.execute(f"{SUPPORTED_COMMANDS['show_onu_detail']} {interface}"), interface)

    def show_onu_rx_power(self, interface: str):
        return parse_onu_power(self.execute(f"{SUPPORTED_COMMANDS['show_onu_rx_power']} {interface}"), interface)

    def show_onu_tx_power(self, interface: str):
        return parse_onu_power(self.execute(f"{SUPPORTED_COMMANDS['show_onu_tx_power']} {interface}"), interface)

    def show_uncfg(self) -> list:
        return parse_uncfg(self.execute(SUPPORTED_COMMANDS["show_uncfg"]))

    def show_uncfg_raw(self) -> str:
        return self.execute(SUPPORTED_COMMANDS["show_uncfg"], read_only=True)

    def backup(self) -> str:
        return self.execute(SUPPORTED_COMMANDS["show_running_config"], read_only=False)

    def show_running_config(self) -> str:
        output = self.execute(SUPPORTED_COMMANDS["show_running_config"], read_only=True, timeout=max(self.timeout, 120))
        captured_prompt = self._extract_prompt(output)
        if not captured_prompt or not self.transport:
            raise DriverCommandError("show running-config", "No stable final prompt detected", output)
        self.transport.write_line("")
        prompt_confirmation = self.transport.read_until_prompt(self.prompt_pattern, self.timeout)
        confirmed_prompt = self._extract_prompt(prompt_confirmation)
        if confirmed_prompt != captured_prompt:
            raise DriverCommandError("show running-config", "Final prompt could not be confirmed", output + prompt_confirmation)
        self.last_prompt = confirmed_prompt
        return output

    def health_check(self) -> bool:
        try:
            return "ZTE" in self.show_version_running()
        except Exception as exc:
            logger.warning("ZTE health check failed: {}", exc)
            return False
