from dataclasses import dataclass
import re


@dataclass(frozen=True)
class ParsedUnauthorizedOnu:
    pon_type: str | None
    slot: int | None
    port: int | None
    pon_port_interface: str | None
    serial_number: str
    detected_type: str | None
    detected_vendor: str | None
    raw_line: str


SERIAL_RE = re.compile(r"\b([A-Z]{4}[A-Z0-9]{8,}|(?=[A-Z0-9]*\d)[A-Z0-9]{8,})\b", re.I)
PON_RE = re.compile(r"\b(?P<pon_type>gpon|epon)(?:-(?:olt|onu))?[_-](?P<rack>\d+)/(?P<slot>\d+)/(?P<port>\d+)(?::\d+)?\b", re.I)
ALT_PON_RE = re.compile(r"\b(?P<rack>\d+)\s*/\s*(?P<slot>\d+)\s*/\s*(?P<port>\d+)\b")
TYPE_RE = re.compile(r"\b(ZTE-F\d+|F\d+|BTPON|CDATA\w*|TENDA|VSOL|HUAWEI|ZTE|XPON|GPON|EPON)[A-Z0-9_.-]*\b", re.I)


def parse_show_gpon_onu_uncfg(output: str) -> list[ParsedUnauthorizedOnu]:
    parsed: list[ParsedUnauthorizedOnu] = []
    for raw_line in output.splitlines():
        line = _strip_prompt(raw_line.strip())
        if not line or line.lower().startswith("show "):
            continue
        if _looks_like_header(line):
            continue
        serial_match = SERIAL_RE.search(line)
        if not serial_match:
            continue
        serial = serial_match.group(1).upper()
        if serial in {"GPON", "EPON", "SN", "TYPE", "VENDOR"}:
            continue

        pon_match = PON_RE.search(line)
        alt_pon_match = ALT_PON_RE.search(line)
        pon_type = pon_match.group("pon_type").lower() if pon_match else _detect_pon_type(line)
        slot = _int_group(pon_match, "slot") if pon_match else _int_group(alt_pon_match, "slot")
        port = _int_group(pon_match, "port") if pon_match else _int_group(alt_pon_match, "port")
        pon_interface = None
        if pon_match:
            pon_interface = f"{pon_type}-olt_{pon_match.group('rack')}/{slot}/{port}"
        elif alt_pon_match and pon_type:
            pon_interface = f"{pon_type}-olt_{alt_pon_match.group('rack')}/{slot}/{port}"

        detected_type = _detect_type(line, serial)
        detected_vendor = _detect_vendor(serial, detected_type, line)
        parsed.append(
            ParsedUnauthorizedOnu(
                pon_type=pon_type,
                slot=slot,
                port=port,
                pon_port_interface=pon_interface,
                serial_number=serial,
                detected_type=detected_type,
                detected_vendor=detected_vendor,
                raw_line=raw_line,
            )
        )
    return parsed


def _strip_prompt(line: str) -> str:
    return re.sub(r"\s+[A-Za-z0-9_.-]+(?:\(config[^\)]*\))?#\s*$", "", line).strip()


def _looks_like_header(line: str) -> bool:
    lowered = line.lower()
    if set(line) <= {"-", " ", "\t"}:
        return True
    return (
        lowered.startswith("interface")
        or lowered.startswith("onu")
        or any(token in lowered for token in ("onu sn", "serial", "password"))
    ) and not SERIAL_RE.search(line.replace("Interface", "").replace("interface", ""))


def _detect_pon_type(line: str) -> str | None:
    lowered = line.lower()
    if "gpon" in lowered:
        return "gpon"
    if "epon" in lowered:
        return "epon"
    return None


def _detect_type(line: str, serial: str) -> str | None:
    candidates = [match.group(0).upper() for match in TYPE_RE.finditer(line)]
    candidates = [
        candidate
        for candidate in candidates
        if candidate != serial
        and candidate not in {"GPON", "EPON"}
        and "GPON-ONU" not in candidate
        and "GPON-OLT" not in candidate
        and "EPON-ONU" not in candidate
        and "EPON-OLT" not in candidate
    ]
    return candidates[-1] if candidates else None


def _detect_vendor(serial: str, detected_type: str | None, line: str) -> str | None:
    prefix = serial[:4].upper()
    vendors = {
        "ZTEG": "ZTE",
        "GPON": "VSOL",
        "BTPT": "BTPON",
        "CDTC": "CDATA",
        "D011": "CDATA",
        "DF1E": "CDATA",
        "DF2D": "CDATA",
        "TDTC": "TENDA",
        "HWTC": "HUAWEI",
    }
    for marker in ("ZTE", "BTPON", "CDATA", "TENDA", "VSOL", "HUAWEI"):
        if marker.lower() in line.lower():
            return marker
    if detected_type:
        for marker in ("ZTE", "BTPON", "CDATA", "TENDA", "VSOL", "HUAWEI"):
            if marker in detected_type.upper():
                return marker
    return vendors.get(prefix)


def _int_group(match, name: str) -> int | None:
    if not match:
        return None
    value = match.group(name)
    return int(value) if value is not None else None
