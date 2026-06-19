from dataclasses import dataclass
import re


INTERFACE_HEADER_RE = re.compile(
    r"^(?P<name>(?:xgei|gei|eth|mng)[\w_/-]*(?:/\d+)*)\s+is\s+(?P<status>\w+),\s+line protocol is\s+(?P<line>\w+)",
    re.IGNORECASE,
)


@dataclass
class ParsedInterface:
    interface_name: str
    description: str | None
    interface_type: str
    admin_status: str
    oper_status: str
    line_protocol: str
    negotiation: str | None
    speed_kbps: int | None
    mtu: int | None
    mode: str
    pvid_untag: int | None
    allowed_vlans: str | None
    raw_output: str

    @property
    def is_uplink_candidate(self) -> bool:
        lower_name = self.interface_name.lower()
        return (
            lower_name.startswith(("xgei_", "gei_"))
            or bool(self.description)
            or self.mode in {"trunk", "hybrid"}
        )


def parse_show_interface(output: str) -> list[ParsedInterface]:
    blocks = _split_interface_blocks(output)
    parsed: list[ParsedInterface] = []
    for block in blocks:
        interface = _parse_block(block)
        if interface is not None:
            parsed.append(interface)
    return parsed


def _split_interface_blocks(output: str) -> list[list[str]]:
    blocks: list[list[str]] = []
    current: list[str] = []
    for line in output.splitlines():
        cleaned_line = _clean_line(line)
        if INTERFACE_HEADER_RE.match(cleaned_line.strip()):
            if current:
                blocks.append(current)
            current = [cleaned_line.rstrip()]
        elif current:
            current.append(cleaned_line.rstrip())
    if current:
        blocks.append(current)
    return blocks


def _parse_block(lines: list[str]) -> ParsedInterface | None:
    if not lines:
        return None
    header = INTERFACE_HEADER_RE.match(lines[0].strip())
    if not header:
        return None

    raw_output = "\n".join(lines).strip()
    interface_name = header.group("name")
    oper_status = header.group("status").lower()
    line_protocol = header.group("line").lower()
    description = None
    negotiation = None
    speed_kbps = None
    mtu = None
    mode = "unknown"
    pvid_untag = None
    allowed_vlans = None
    interface_type = _default_interface_type(interface_name)

    for line in lines[1:]:
        stripped = line.strip()
        lowered = stripped.lower()

        description_match = re.search(r"description\s+is\s+(.+)$", stripped, re.IGNORECASE)
        if description_match:
            value = description_match.group(1).strip()
            description = None if value.strip(".").lower() in {"", "--", "none"} else value
            continue

        if "negotiation" in lowered:
            negotiation = stripped

        if "optical" in lowered or "fiber" in lowered:
            interface_type = "fiber"
        elif "copper" in lowered or "electrical" in lowered or "electric" in lowered:
            interface_type = "copper"

        vlan_mode_match = re.search(r"vlan\s+mode\s+is\s+(trunk|hybrid|access)", stripped, re.IGNORECASE)
        if vlan_mode_match:
            mode = vlan_mode_match.group(1).lower()
            allowed_vlans = stripped

        pvid_match = re.search(r"\bpvid\s+(\d+)", stripped, re.IGNORECASE)
        if pvid_match:
            pvid_untag = int(pvid_match.group(1))

        bw_match = re.search(r"\bBW\s+(\d+)\s+Kbits", stripped, re.IGNORECASE)
        if bw_match:
            speed_kbps = int(bw_match.group(1))

        mtu_match = re.search(r"\bMTU\s+(\d+)\s+bytes", stripped, re.IGNORECASE)
        if mtu_match:
            mtu = int(mtu_match.group(1))

        vlan_allowed_match = re.search(r"(?:allowed|tagged).*(?:vlan|vlans)\s+(.+)$", stripped, re.IGNORECASE)
        if vlan_allowed_match:
            allowed_vlans = stripped

    return ParsedInterface(
        interface_name=interface_name,
        description=description,
        interface_type=interface_type,
        admin_status=oper_status,
        oper_status=oper_status,
        line_protocol=line_protocol,
        negotiation=negotiation,
        speed_kbps=speed_kbps,
        mtu=mtu,
        mode=mode,
        pvid_untag=pvid_untag,
        allowed_vlans=allowed_vlans,
        raw_output=raw_output,
    )


def _default_interface_type(interface_name: str) -> str:
    lower_name = interface_name.lower()
    if lower_name.startswith("mng"):
        return "management"
    if lower_name.startswith("xgei_"):
        return "fiber"
    if lower_name.startswith(("gei_", "eth")):
        return "copper"
    return "unknown"


def _clean_line(line: str) -> str:
    cleaned = line.replace("\b", "")
    while cleaned.startswith(" "):
        cleaned = cleaned[1:]
    return cleaned.rstrip()
