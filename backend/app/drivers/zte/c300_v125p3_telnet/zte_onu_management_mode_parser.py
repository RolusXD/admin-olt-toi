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
    # Proyección normalizada y modelo estructurado adicional
    mode_simple: str = "unknown"  # router / bridge / transparent / unknown
    port_mode: str = "unknown"  # access / tag / hybrid / trunk / transparent / unknown
    service_vlans: list[int] = field(default_factory=list)
    allowed_vlans: list[int] = field(default_factory=list)
    native_vlan: int | None = None
    wan_vlan_id: int | None = None
    vlan_filter_rules: list[dict] = field(default_factory=list)
    flows: list[dict] = field(default_factory=list)


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
    port_mode = _port_mode(lines)
    vlan_filter_rules = _vlan_filter_rules(lines)
    flows, service_vlans = _flows_and_service_vlans(lines)
    allowed_vlans, native_vlan = _allowed_vlans_and_native_vlan(lines)

    # Reglas de clasificación de modo ONU (service_mode_code) compatibles con históricos
    if vlan_mode == "transparent":
        # Casos tipo transparent_special (incluyen IPHost/VEIP + vlan-filter + DHCP desde Internet)
        mode_code = "transparent_special"
    elif has_iphost and has_vlan_filter and dhcp_source == "from-onu":
        # Router con IPHost, filtros VLAN y DHCP servido por la ONU
        mode_code = "router_iphost"
    elif (not has_iphost) and has_veip and dhcp_source == "from-internet":
        # Bridge: sin IPHost, con VEIP y DHCP desde Internet, independientemente del modo de puerto
        mode_code = "bridge_tag_internet"
    else:
        mode_code = "unknown"

    if mode_code == "router_iphost":
        mode_simple = "router"
    elif mode_code == "bridge_tag_internet":
        mode_simple = "bridge"
    elif mode_code == "transparent_special":
        mode_simple = "transparent"
    else:
        mode_simple = "unknown"

    # WAN principal: priorizar VLAN de vlan-filter; si no hay, caer al heurístico _vlan_id
    wan_vlan_id = vlan_filter_rules[0]["vlan_id"] if vlan_filter_rules else vlan_id

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
        mode_simple=mode_simple,
        port_mode=port_mode,
        service_vlans=service_vlans,
        allowed_vlans=allowed_vlans,
        native_vlan=native_vlan,
        wan_vlan_id=wan_vlan_id,
        vlan_filter_rules=vlan_filter_rules,
        flows=flows,
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


def _port_mode(lines: list[str]) -> str:
    """Detectar el modo principal del puerto Ethernet de servicio.

    Se basa en la primera coincidencia de ``vlan port <port> mode <mode>`` y
    normaliza el valor a uno de: access / tag / hybrid / trunk / transparent / unknown.
    """

    for line in lines:
        match = re.search(r"vlan\s+port\s+\S+\s+mode\s+(\S+)", line, re.IGNORECASE)
        if not match:
            continue
        mode = match.group(1).lower()
        if mode in {"tag", "tagged"}:
            return "tag"
        if mode == "hybrid":
            return "hybrid"
        if mode == "trunk":
            return "trunk"
        if mode == "transparent":
            return "transparent"
        if mode in {"untag", "access"}:
            return "access"
        return "unknown"
    return "unknown"


def _vlan_filter_rules(lines: list[str]) -> list[dict]:
    rules: list[dict] = []
    for line in lines:
        match = re.search(
            r"vlan-filter\s+iphost\s+(\d+).*?priority\s+(\d+)\s+vid\s+(\d+)",
            line,
            re.IGNORECASE,
        )
        if match:
            rules.append(
                {
                    "iphost_index": int(match.group(1)),
                    "priority": int(match.group(2)),
                    "vlan_id": int(match.group(3)),
                }
            )
    return rules


def _flows_and_service_vlans(lines: list[str]) -> tuple[list[dict], list[int]]:
    flows_by_id: dict[int, dict] = {}
    flow_mode: str | None = None
    service_vlans: set[int] = set()

    for line in lines:
        mode_match = re.match(r"flow\s+mode\s+\d+\s+(.*)", line.strip(), re.IGNORECASE)
        if mode_match:
            flow_mode = mode_match.group(1).strip()
            continue
        match = re.match(r"flow\s+(\d+)\s+priority\s+(\d+)\s+vid\s+(\d+)", line.strip(), re.IGNORECASE)
        if match:
            flow_id = int(match.group(1))
            vlan_id = int(match.group(3))
            flows_by_id.setdefault(
                flow_id,
                {"id": flow_id, "priority": int(match.group(2)), "vlan_id": vlan_id, "gemport_id": None},
            )
            service_vlans.add(vlan_id)

    # Asociar gemport↔flow
    for line in lines:
        match = re.match(r"gemport\s+(\d+)\s+flow\s+(\d+)", line.strip(), re.IGNORECASE)
        if match:
            gemport_id = int(match.group(1))
            flow_id = int(match.group(2))
            if flow_id in flows_by_id:
                flows_by_id[flow_id]["gemport_id"] = gemport_id

    flows: list[dict] = []
    for item in sorted(flows_by_id.values(), key=lambda value: value["id"]):
        if flow_mode is not None:
            item["mode"] = flow_mode
        service_vlans.add(item["vlan_id"])
        flows.append(item)

    # También considerar VLANs de switchport vlan ... tag vport 1
    for line in lines:
        match = re.search(r"switchport\s+vlan\s+([\d,]+)\s+tag\s+vport\s+\d+", line, re.IGNORECASE)
        if match:
            for token in match.group(1).split(","):
                token = token.strip()
                if token.isdigit():
                    service_vlans.add(int(token))

    return flows, sorted(service_vlans)


def _allowed_vlans_and_native_vlan(lines: list[str]) -> tuple[list[int], int | None]:
    allowed_by_port: dict[str, set[int]] = {}
    native_by_port: dict[str, int] = {}

    for line in lines:
        vlan_match = re.search(r"vlan\s+port\s+(\S+)\s+vlan\s+([\d,]+)", line, re.IGNORECASE)
        if vlan_match:
            port = vlan_match.group(1)
            allowed = allowed_by_port.setdefault(port, set())
            for token in vlan_match.group(2).split(","):
                token = token.strip()
                if token.isdigit():
                    allowed.add(int(token))

        native_match = re.search(r"vlan\s+port\s+(\S+)\s+mode\s+hybrid\s+def-vlan\s+(\d+)", line, re.IGNORECASE)
        if native_match:
            native_by_port[native_match.group(1)] = int(native_match.group(2))

    # Seleccionar el puerto "principal" (priorizar eth_0/1 si existe)
    preferred_port: str | None = None
    if "eth_0/1" in allowed_by_port or "eth_0/1" in native_by_port:
        preferred_port = "eth_0/1"
    elif allowed_by_port:
        preferred_port = sorted(allowed_by_port.keys())[0]
    elif native_by_port:
        preferred_port = sorted(native_by_port.keys())[0]

    if not preferred_port:
        return [], None

    allowed = sorted(allowed_by_port.get(preferred_port, set()))
    native = native_by_port.get(preferred_port)
    return allowed, native
