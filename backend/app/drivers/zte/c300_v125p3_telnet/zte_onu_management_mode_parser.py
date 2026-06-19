from __future__ import annotations

from dataclasses import dataclass, field
import re


SERVICE_MODE_DEFINITIONS = {
    "bridge_tag_internet": {
        "name": "Modo Bridge TAG Internet",
        "description": "Bridge con VLAN TAG en Ethernet y DHCP desde Internet.",
        "template_body": """loop-detect ethuni {ethernet_port} enable
flow mode 1 tag-filter vid-filter untag-filter discard
flow 1 priority 0 vid {vlan}
gemport 1 flow 1
switchport-bind switch_0/1 veip 1
vlan port {ethernet_port} mode tag vlan {vlan}
dhcp-ip ethuni {ethernet_port} from-internet
security-mng 998 state enable mode permit ingress-type lan protocol web https
security-mng 999 state enable ingress-type lan protocol ftp telnet ssh snmp tr069""",
    },
    "router_iphost": {
        "name": "Modo Router IPHost",
        "description": "Router con IPHost, VEIP, filtros VLAN y DHCP desde ONU.",
        "template_body": """flow mode 1 tag-filter vid-filter untag-filter discard
flow 1 priority 0 vid {vlan}
gemport 1 flow 1
switchport-bind switch_0/1 iphost 1
switchport-bind switch_0/1 veip 1
vlan-filter-mode iphost 1 tag-filter vid-filter untag-filter discard
vlan-filter iphost 1 priority 0 vid {vlan}
{dhcp_lines}
security-mng 998 state enable mode permit ingress-type lan protocol web https
security-mng 999 state enable ingress-type lan protocol ftp telnet ssh snmp tr069""",
    },
    "transparent_special": {
        "name": "Modo Transparent Especial",
        "description": "Transparent con IPHost, VEIP, filtros VLAN y WiFi deshabilitado.",
        "template_body": """interface wifi wifi_0/1 state lock
flow mode 1 tag-filter vid-filter untag-filter discard
flow 1 priority 0 vid {vlan}
gemport 1 flow 1
switchport-bind switch_0/1 iphost 1
switchport-bind switch_0/1 veip 1
vlan-filter-mode iphost 1 tag-filter vid-filter untag-filter discard
vlan-filter iphost 1 priority 0 vid {vlan}
{ethernet_vlan_lines}
{dhcp_lines}
security-mng 998 state enable mode permit ingress-type lan protocol web https
security-mng 999 state enable ingress-type lan protocol ftp telnet ssh snmp tr069
wifi disable""",
    },
}


@dataclass(frozen=True)
class ParsedOnuManagementMode:
    onu_interface: str
    vlan_id: int | None
    vlan_mode: str
    dhcp_source: str
    has_iphost: bool
    has_veip: bool
    has_vlan_filter: bool
    has_switchport_bind: bool
    ethernet_ports_configured: list[str] = field(default_factory=list)
    wifi_disabled: bool = False
    loop_detect_enabled: bool = False
    security_profiles: list[str] = field(default_factory=list)
    mode_code: str = "unknown"
    raw_block: str = ""


def parse_onu_management_modes(raw_config: str) -> list[ParsedOnuManagementMode]:
    blocks: list[tuple[str, list[str]]] = []
    current_interface: str | None = None
    current_lines: list[str] = []

    for raw_line in raw_config.splitlines():
        line = raw_line.strip()
        match = re.match(r"pon-onu-mng\s+(gpon-onu_\d+/\d+/\d+:\d+)", line, re.IGNORECASE)
        if match:
            if current_interface:
                blocks.append((current_interface, current_lines))
            current_interface = match.group(1)
            current_lines = [line]
            continue
        if current_interface:
            if line == "!":
                blocks.append((current_interface, current_lines))
                current_interface = None
                current_lines = []
            else:
                current_lines.append(line)

    if current_interface:
        blocks.append((current_interface, current_lines))

    return [_parse_block(interface, lines) for interface, lines in blocks]


def _parse_block(interface: str, lines: list[str]) -> ParsedOnuManagementMode:
    text = "\n".join(lines)
    lower = text.lower()
    vlan_mode = _vlan_mode(lines)
    dhcp_source = _dhcp_source(lines)
    has_iphost = bool(re.search(r"switchport-bind\s+\S+\s+iphost\s+\d+", text, re.IGNORECASE))
    has_veip = bool(re.search(r"switchport-bind\s+\S+\s+veip\s+\d+", text, re.IGNORECASE))
    has_vlan_filter = bool(re.search(r"\bvlan-filter(?:-mode)?\s+", text, re.IGNORECASE))
    has_switchport_bind = "switchport-bind " in lower
    ethernet_ports = sorted(set(re.findall(r"\beth_\d+/\d+\b", text, re.IGNORECASE)))
    security_profiles = [
        match.group(1)
        for line in lines
        if (match := re.match(r"security-mng\s+(\d+)\b", line, re.IGNORECASE))
    ]
    vlan_id = _vlan_id(lines)

    if vlan_mode == "transparent":
        mode_code = "transparent_special"
    elif has_iphost and has_vlan_filter and dhcp_source == "from-onu":
        mode_code = "router_iphost"
    elif vlan_mode == "tag" and dhcp_source == "from-internet":
        mode_code = "bridge_tag_internet"
    else:
        mode_code = "unknown"

    return ParsedOnuManagementMode(
        onu_interface=interface,
        vlan_id=vlan_id,
        vlan_mode=vlan_mode,
        dhcp_source=dhcp_source,
        has_iphost=has_iphost,
        has_veip=has_veip,
        has_vlan_filter=has_vlan_filter,
        has_switchport_bind=has_switchport_bind,
        ethernet_ports_configured=ethernet_ports,
        wifi_disabled="wifi disable" in lower,
        loop_detect_enabled=bool(re.search(r"loop-detect\s+ethuni\s+\S+\s+enable", text, re.IGNORECASE)),
        security_profiles=security_profiles,
        mode_code=mode_code,
        raw_block=text,
    )


def _vlan_mode(lines: list[str]) -> str:
    for mode in ("transparent", "tag", "untag"):
        if any(re.search(rf"vlan\s+port\s+\S+\s+mode\s+{mode}\b", line, re.IGNORECASE) for line in lines):
            return mode
    return "unknown"


def _dhcp_source(lines: list[str]) -> str:
    sources = {
        match.group(1).lower()
        for line in lines
        if (match := re.search(r"dhcp-ip\s+ethuni\s+\S+\s+(from-internet|from-onu|none)\b", line, re.IGNORECASE))
    }
    if "from-onu" in sources:
        return "from-onu"
    if "from-internet" in sources:
        return "from-internet"
    return "none"


def _vlan_id(lines: list[str]) -> int | None:
    patterns = (
        r"vlan\s+port\s+\S+\s+mode\s+tag\s+vlan\s+(\d+)",
        r"vlan-filter\s+iphost\s+\d+.*?\bvid\s+(\d+)",
        r"flow\s+\d+.*?\bvid\s+(\d+)",
    )
    for pattern in patterns:
        for line in lines:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                return int(match.group(1))
    return None
