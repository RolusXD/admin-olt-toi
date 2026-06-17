import re
from dataclasses import dataclass


@dataclass(frozen=True)
class CardInfo:
    slot: str
    card_type: str
    status: str


@dataclass(frozen=True)
class OnuState:
    interface: str
    serial_number: str | None
    status: str
    phase_state: str | None
    last_down_cause: str | None


@dataclass(frozen=True)
class OnuDetail:
    interface: str
    serial_number: str | None
    onu_type: str | None
    distance_m: int | None
    last_down_cause: str | None


@dataclass(frozen=True)
class OnuPower:
    interface: str
    power_dbm: float


@dataclass(frozen=True)
class UnauthorizedOnuInfo:
    interface: str
    serial_number: str


def _clean_lines(output: str) -> list[str]:
    return [line.strip() for line in output.splitlines() if line.strip() and not line.strip().endswith("#")]


def parse_show_card(output: str) -> list[CardInfo]:
    cards: list[CardInfo] = []
    for line in _clean_lines(output):
        columns = line.split()
        if len(columns) >= 8 and columns[0].isdigit() and columns[1].isdigit() and columns[2].isdigit():
            cards.append(CardInfo(f"{columns[0]}/{columns[1]}/{columns[2]}", columns[4], columns[-1].lower()))
            continue
        match = re.search(r"^(?P<slot>\d+/\d+|\d+)\s+(?P<type>[A-Za-z0-9_-]+)\s+.*?(?P<status>INSERVICE|STANDBY|ONLINE|OFFLINE|FAULT|NORMAL)\b", line, re.I)
        if match:
            cards.append(CardInfo(match.group("slot"), match.group("type"), match.group("status").lower()))
    return cards


def parse_onu_state(output: str) -> list[OnuState]:
    states: list[OnuState] = []
    for line in _clean_lines(output):
        if "gpon-onu_" not in line:
            continue
        interface = re.search(r"gpon-onu_\d+/\d+/\d+:\d+", line)
        if not interface:
            continue
        serial = re.search(r"\b([A-Z]{4}[A-Z0-9]{8,})\b", line)
        status = "online" if re.search(r"\bonline\b|working", line, re.I) else "offline"
        cause_match = re.search(r"\b(LOS|DyingGasp|PWRFail|Offline)\b", line, re.I)
        phase_match = re.search(r"\b(working|online|offline|los|dyinggasp|pwfail)\b", line, re.I)
        states.append(
            OnuState(
                interface=interface.group(0),
                serial_number=serial.group(1) if serial else None,
                status=status,
                phase_state=phase_match.group(1) if phase_match else None,
                last_down_cause=cause_match.group(1) if cause_match else None,
            )
        )
    return states


def parse_onu_detail(output: str, interface: str) -> OnuDetail:
    serial = re.search(r"(?:Serial number|SN)\s*[:=]\s*([A-Z0-9]+)", output, re.I)
    onu_type = re.search(r"(?:ONU type|Type)\s*[:=]\s*([A-Za-z0-9_-]+)", output, re.I)
    distance = re.search(r"(?:Distance|ONU distance)\s*[:=]\s*(\d+)", output, re.I)
    cause = re.search(r"(?:Last down cause|Down cause)\s*[:=]\s*([A-Za-z0-9_-]+)", output, re.I)
    return OnuDetail(
        interface=interface,
        serial_number=serial.group(1) if serial else None,
        onu_type=onu_type.group(1) if onu_type else None,
        distance_m=int(distance.group(1)) if distance else None,
        last_down_cause=cause.group(1) if cause else None,
    )


def parse_onu_power(output: str, interface: str) -> OnuPower | None:
    line_match = re.search(rf"{re.escape(interface)}.*?(-?\d+(?:\.\d+)?)\s*(?:dbm|dBm)?", output, re.I)
    if line_match:
        return OnuPower(interface=interface, power_dbm=float(line_match.group(1)))
    value_match = re.search(r"(-?\d+(?:\.\d+)?)\s*(?:dbm|dBm)", output)
    if value_match:
        return OnuPower(interface=interface, power_dbm=float(value_match.group(1)))
    return None


def parse_uncfg(output: str) -> list[UnauthorizedOnuInfo]:
    onus: list[UnauthorizedOnuInfo] = []
    for line in _clean_lines(output):
        interface = re.search(r"gpon-onu_\d+/\d+/\d+:\d+|gpon_\d+/\d+/\d+", line)
        serial = re.search(r"\b([A-Z]{4}[A-Z0-9]{8,})\b", line)
        if interface and serial:
            onus.append(UnauthorizedOnuInfo(interface=interface.group(0), serial_number=serial.group(1)))
    return onus
