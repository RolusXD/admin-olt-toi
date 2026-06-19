from dataclasses import dataclass, field
from datetime import UTC, datetime
import re

from app.drivers.zte.c300_v125p3_telnet.zte_onu_description_parser import parse_onu_description


@dataclass(frozen=True)
class ParsedVlan:
    vlan_id: int
    name: str | None = None
    description: str | None = None


@dataclass(frozen=True)
class ParsedGponProfile:
    profile_type: str
    name: str
    upstream_rate: int | None = None
    downstream_rate: int | None = None
    type_value: int | None = None
    fixed_kbps: int | None = None
    assured_kbps: int | None = None
    maximum_kbps: int | None = None
    sir_kbps: int | None = None
    pir_kbps: int | None = None


@dataclass(frozen=True)
class ParsedProfileCatalog:
    direction: str
    profile_kind: str
    name: str
    service_type: str = "internet"
    speed_kbps: int | None = None
    is_default: bool = False
    type_value: int | None = None
    fixed_kbps: int | None = None
    assured_kbps: int | None = None
    maximum_kbps: int | None = None
    sir_kbps: int | None = None
    pir_kbps: int | None = None


@dataclass(frozen=True)
class ParsedOnuType:
    name: str
    vendor_detected: str | None = None
    technology: str = "gpon"
    pon_type: str = "GPON"
    channel_gpon: bool = True
    channel_xgpon: bool = False
    channel_xgspon: bool = False
    max_tcont: int | None = None
    max_gemport: int | None = None
    max_ports: int | None = None
    max_switch_perslot: int | None = None
    max_flow_perswitch: int | None = None
    max_iphost: int | None = None
    ethernet_ports: int | None = None
    wifi_ports: int | None = None
    pots_ports: int | None = None
    rf_ports: int | None = None
    allow_custom_profiles: bool = True
    default_custom_profile_id: int | None = None
    capability_mode: str = "bridging"


@dataclass(frozen=True)
class ParsedPonPort:
    interface_name: str
    rack: int
    shelf: int
    slot: int
    port: int


@dataclass(frozen=True)
class ParsedOltUplink:
    interface_name: str
    description: str | None = None
    interface_type: str | None = None
    admin_status: str = "unknown"
    oper_status: str = "unknown"
    negotiation: str | None = None
    mtu: int | None = None
    mode: str | None = None
    allowed_vlans: str | None = None
    pvid_untag: int | None = None


@dataclass
class ParsedOnu:
    pon_interface_name: str
    onu_interface: str
    onu_index: int
    onu_type: str
    serial_number: str
    customer_name: str | None = None
    raw_description: str | None = None
    parsed_zone_name: str | None = None
    parsed_nap_name: str | None = None
    parsed_nap_port: int | None = None
    parsed_odn: str | None = None
    address_reference: str | None = None
    external_id: str | None = None
    description_parse_status: str | None = None
    description_parse_warnings: list[str] = field(default_factory=list)
    auth_date: datetime | None = None
    vlan: int | None = None
    upstream_profile: str | None = None
    downstream_profile: str | None = None
    warnings: list[str] = field(default_factory=list)

    @property
    def speed_profile_up(self) -> str | None:
        return self.upstream_profile

    @property
    def speed_profile_down(self) -> str | None:
        return self.downstream_profile


@dataclass
class RunningConfigParseResult:
    vlans: list[ParsedVlan]
    gpon_profiles: list[ParsedGponProfile]
    profile_catalogs: list[ParsedProfileCatalog]
    onu_types: list[ParsedOnuType]
    pon_ports: list[ParsedPonPort]
    uplinks: list[ParsedOltUplink]
    onus: list[ParsedOnu]
    warnings: list[str]

    def summary(self) -> dict:
        zones = sorted({onu.parsed_zone_name for onu in self.onus if onu.parsed_zone_name})
        naps = sorted({onu.parsed_nap_name for onu in self.onus if onu.parsed_nap_name})
        return {
            "vlans": len(self.vlans),
            "gpon_profiles": len(self.gpon_profiles),
            "profile_catalogs": len(self.profile_catalogs),
            "onu_types": len(self.onu_types),
            "pon_ports": len(self.pon_ports),
            "uplinks": len(self.uplinks),
            "onus": len(self.onus),
            "zones_detected": zones,
            "naps_detected": naps,
            "warnings": self.warnings,
        }


def parse_running_config(raw_config: str) -> RunningConfigParseResult:
    lines = raw_config.splitlines()
    vlans = _parse_vlans(lines)
    profiles = _parse_profiles(lines)
    profile_catalogs = _parse_profile_catalogs(profiles)
    onu_types = _parse_onu_types(lines)
    pon_ports = _parse_pon_ports(lines)
    uplinks = _parse_uplinks(lines)
    onus, warnings = _parse_onus(lines)
    return RunningConfigParseResult(vlans, profiles, profile_catalogs, onu_types, pon_ports, uplinks, onus, warnings)


def _parse_vlans(lines: list[str]) -> list[ParsedVlan]:
    vlans: dict[int, ParsedVlan] = {}
    in_vlan_database = False
    current_vlan_id: int | None = None
    for raw in lines:
        line = raw.strip()
        if line == "vlan database":
            in_vlan_database = True
            continue
        if in_vlan_database:
            if line.startswith("!"):
                in_vlan_database = False
                continue
            if line.startswith("vlan "):
                for vlan_id in _expand_vlan_tokens(line.removeprefix("vlan ").strip()):
                    vlans.setdefault(vlan_id, ParsedVlan(vlan_id=vlan_id))
            continue
        vlan_block = re.match(r"vlan\s+(\d+)\s*$", line, re.I)
        if vlan_block:
            current_vlan_id = int(vlan_block.group(1))
            vlans.setdefault(current_vlan_id, ParsedVlan(vlan_id=current_vlan_id))
            continue
        if current_vlan_id and line.startswith("description "):
            existing = vlans[current_vlan_id]
            vlans[current_vlan_id] = ParsedVlan(
                vlan_id=current_vlan_id,
                name=existing.name,
                description=line.removeprefix("description ").strip(),
            )
            continue
        if line.startswith("!"):
            current_vlan_id = None
    return sorted(vlans.values(), key=lambda vlan: vlan.vlan_id)


def _parse_profiles(lines: list[str]) -> list[ParsedGponProfile]:
    profiles: dict[tuple[str, str], ParsedGponProfile] = {}
    current: dict | None = None
    for raw in lines:
        line = raw.strip()
        match = re.match(r"profile\s+(tcont|traffic)\s+(\S+)(.*)", line, re.I)
        if match:
            if current:
                profile = ParsedGponProfile(**current)
                profiles[(profile.profile_type, profile.name)] = profile
            profile_type = match.group(1).lower()
            tail = match.group(3).strip()
            current = {
                "profile_type": profile_type,
                "name": match.group(2).strip(),
                "upstream_rate": None,
                "downstream_rate": None,
                "type_value": _value_after_keyword(tail, "type"),
                "fixed_kbps": _value_after_keyword(tail, "fixed"),
                "assured_kbps": _value_after_keyword(tail, "assured"),
                "maximum_kbps": _value_after_keyword(tail, "maximum"),
                "sir_kbps": _value_after_keyword(tail, "sir"),
                "pir_kbps": _value_after_keyword(tail, "pir"),
            }
            if profile_type == "tcont":
                current["upstream_rate"] = current["maximum_kbps"] or _last_int(tail)
            if profile_type == "traffic":
                current["downstream_rate"] = current["pir_kbps"] or _last_int(tail)
            continue
        if current and re.search(r"\bupstream\b|\bup\b", line, re.I):
            rate = _value_after_keyword(line, "maximum") or _last_int(line)
            current["upstream_rate"] = rate or current["upstream_rate"]
        if current and re.search(r"\bdownstream\b|\bdown\b", line, re.I):
            rate = _value_after_keyword(line, "pir") or _last_int(line)
            current["downstream_rate"] = rate or current["downstream_rate"]
        if current and line.startswith("!"):
            profile = ParsedGponProfile(**current)
            profiles[(profile.profile_type, profile.name)] = profile
            current = None
    if current:
        profile = ParsedGponProfile(**current)
        profiles[(profile.profile_type, profile.name)] = profile
    return list(profiles.values())


def _parse_onu_types(lines: list[str]) -> list[ParsedOnuType]:
    by_name: dict[str, dict] = {}
    interfaces: dict[str, dict[str, set[str]]] = {}
    for raw in lines:
        line = raw.strip()
        match = re.match(r"onu-type\s+(\S+)\s+(\S+)(.*)", line, re.I)
        if match:
            name = match.group(1)
            technology = match.group(2).lower()
            current = by_name.setdefault(
                name,
                {
                    "name": name,
                    "vendor_detected": _detect_vendor(name),
                    "technology": technology,
                    "pon_type": technology.upper(),
                    "channel_gpon": technology.lower() == "gpon",
                    "channel_xgpon": "xgpon" in technology.lower() and "xgs" not in technology.lower(),
                    "channel_xgspon": "xgs" in technology.lower(),
                    "max_tcont": None,
                    "max_gemport": None,
                    "max_ports": None,
                    "max_switch_perslot": None,
                    "max_flow_perswitch": None,
                    "max_iphost": None,
                    "ethernet_ports": None,
                    "wifi_ports": None,
                    "pots_ports": None,
                    "rf_ports": None,
                    "allow_custom_profiles": True,
                    "default_custom_profile_id": None,
                    "capability_mode": "bridging",
                },
            )
            tail = match.group(3)
            current["technology"] = technology
            current["pon_type"] = technology.upper()
            current["channel_gpon"] = technology.lower() == "gpon"
            current["channel_xgpon"] = "xgpon" in technology.lower() and "xgs" not in technology.lower()
            current["channel_xgspon"] = "xgs" in technology.lower()
            if "max-tcont" in tail.lower():
                current["max_tcont"] = _last_int(tail) or current["max_tcont"]
            if "max-gemport" in tail.lower():
                current["max_gemport"] = _last_int(tail) or current["max_gemport"]
            if "max-switch-perslot" in tail.lower():
                current["max_switch_perslot"] = _last_int(tail) or current["max_switch_perslot"]
                current["max_ports"] = current["max_switch_perslot"]
            if "max-flow-perswitch" in tail.lower():
                current["max_flow_perswitch"] = _last_int(tail) or current["max_flow_perswitch"]
            if "max-iphost" in tail.lower():
                current["max_iphost"] = _last_int(tail) or current["max_iphost"]
            if "max-port" in tail.lower():
                current["max_ports"] = _last_int(tail) or current["max_ports"]
            continue
        if_match = re.match(r"onu-type-if\s+(\S+)\s+(\S+)", line, re.I)
        if if_match:
            name = if_match.group(1)
            iface = if_match.group(2).lower()
            current = by_name.setdefault(
                name,
                {
                    "name": name,
                    "vendor_detected": _detect_vendor(name),
                    "technology": "gpon",
                    "pon_type": "GPON",
                    "channel_gpon": True,
                    "channel_xgpon": False,
                    "channel_xgspon": False,
                    "max_tcont": None,
                    "max_gemport": None,
                    "max_ports": None,
                    "max_switch_perslot": None,
                    "max_flow_perswitch": None,
                    "max_iphost": None,
                    "ethernet_ports": None,
                    "wifi_ports": None,
                    "pots_ports": None,
                    "rf_ports": None,
                    "allow_custom_profiles": True,
                    "default_custom_profile_id": None,
                    "capability_mode": "bridging",
                },
            )
            buckets = interfaces.setdefault(name, {"eth": set(), "wifi": set(), "pots": set(), "rf": set()})
            if iface.startswith("eth_"):
                buckets["eth"].add(iface)
            elif iface.startswith("wifi_"):
                buckets["wifi"].add(iface)
            elif iface.startswith("pots_"):
                buckets["pots"].add(iface)
            elif iface.startswith("rf_"):
                buckets["rf"].add(iface)
    for name, buckets in interfaces.items():
        current = by_name[name]
        current["ethernet_ports"] = len(buckets["eth"])
        current["wifi_ports"] = len(buckets["wifi"])
        current["pots_ports"] = len(buckets["pots"])
        current["rf_ports"] = len(buckets["rf"])
        current["capability_mode"] = _infer_capability_mode(
            current["ethernet_ports"] or 0,
            current["wifi_ports"] or 0,
            current["pots_ports"] or 0,
            current["rf_ports"] or 0,
        )
    return [ParsedOnuType(**value) for value in by_name.values()]


def _parse_profile_catalogs(profiles: list[ParsedGponProfile]) -> list[ParsedProfileCatalog]:
    catalogs: list[ParsedProfileCatalog] = []
    for profile in profiles:
        if profile.profile_type == "tcont":
            catalogs.append(
                ParsedProfileCatalog(
                    direction="upload",
                    profile_kind="tcont",
                    name=profile.name,
                    speed_kbps=profile.maximum_kbps or profile.upstream_rate,
                    type_value=profile.type_value,
                    fixed_kbps=profile.fixed_kbps,
                    assured_kbps=profile.assured_kbps,
                    maximum_kbps=profile.maximum_kbps or profile.upstream_rate,
                )
            )
        elif profile.profile_type == "traffic":
            catalogs.append(
                ParsedProfileCatalog(
                    direction="download",
                    profile_kind="traffic",
                    name=profile.name,
                    speed_kbps=profile.pir_kbps or profile.downstream_rate,
                    sir_kbps=profile.sir_kbps,
                    pir_kbps=profile.pir_kbps or profile.downstream_rate,
                )
            )
    return catalogs


def _parse_pon_ports(lines: list[str]) -> list[ParsedPonPort]:
    ports: list[ParsedPonPort] = []
    seen: set[str] = set()
    for raw in lines:
        match = re.match(r"\s*interface\s+(gpon-olt_(\d+)/(\d+)/(\d+))\b", raw, re.I)
        if not match or match.group(1) in seen:
            continue
        interface_name = match.group(1)
        rack = int(match.group(2))
        shelf = int(match.group(3))
        port = int(match.group(4))
        ports.append(ParsedPonPort(interface_name=interface_name, rack=rack, shelf=shelf, slot=shelf, port=port))
        seen.add(interface_name)
    return ports


def _parse_uplinks(lines: list[str]) -> list[ParsedOltUplink]:
    uplinks: dict[str, dict] = {}
    current: dict | None = None
    for raw in lines:
        line = raw.strip()
        match = re.match(r"interface\s+((?:xgei|gei)_?\d+/\d+/\d+(?::\d+)?)\b", line, re.I)
        if match:
            if current:
                uplinks[current["interface_name"]] = current
            interface_name = match.group(1)
            current = {
                "interface_name": interface_name,
                "description": None,
                "interface_type": "xgei" if interface_name.lower().startswith("xgei") else "gei",
                "admin_status": "unknown",
                "oper_status": "unknown",
                "negotiation": None,
                "mtu": None,
                "mode": None,
                "allowed_vlans": None,
                "pvid_untag": None,
            }
            continue
        if not current:
            continue
        if line.startswith("!"):
            uplinks[current["interface_name"]] = current
            current = None
            continue
        if line.startswith("description "):
            current["description"] = line.removeprefix("description ").strip()
        elif line.startswith("mtu "):
            current["mtu"] = _first_int(line)
        elif "switchport mode" in line:
            mode = re.search(r"switchport\s+mode\s+(\S+)", line, re.I)
            current["mode"] = mode.group(1) if mode else current["mode"]
        elif "switchport trunk vlan" in line or "switchport hybrid vlan" in line:
            current["allowed_vlans"] = line
        elif "pvid" in line.lower():
            current["pvid_untag"] = _last_int(line)
        elif "negotiation" in line.lower():
            current["negotiation"] = line
    if current:
        uplinks[current["interface_name"]] = current
    return [ParsedOltUplink(**value) for value in uplinks.values()]


def _parse_onus(lines: list[str]) -> tuple[list[ParsedOnu], list[str]]:
    onus: dict[str, ParsedOnu] = {}
    warnings: list[str] = []
    current_pon: str | None = None
    current_onu: ParsedOnu | None = None

    for raw in lines:
        line = raw.strip()
        pon_match = re.match(r"interface\s+(gpon-olt_\d+/\d+/\d+)\b", line, re.I)
        if pon_match:
            current_pon = pon_match.group(1)
            current_onu = None
            continue

        auth_match = re.match(r"onu\s+(\d+)\s+type\s+(\S+)\s+sn\s+(\S+)", line, re.I)
        if auth_match and current_pon:
            onu_index = int(auth_match.group(1))
            interface = current_pon.replace("gpon-olt_", "gpon-onu_") + f":{onu_index}"
            onus[interface] = ParsedOnu(
                pon_interface_name=current_pon,
                onu_interface=interface,
                onu_index=onu_index,
                onu_type=auth_match.group(2),
                serial_number=auth_match.group(3),
            )
            continue

        onu_if_match = re.match(r"interface\s+(gpon-onu_\d+/\d+/\d+:\d+)\b", line, re.I)
        if onu_if_match:
            current_onu = onus.get(onu_if_match.group(1))
            if current_onu is None:
                parts = re.match(r"gpon-onu_(\d+)/(\d+)/(\d+):(\d+)", onu_if_match.group(1))
                if parts:
                    current_onu = ParsedOnu(
                        pon_interface_name=f"gpon-olt_{parts.group(1)}/{parts.group(2)}/{parts.group(3)}",
                        onu_interface=onu_if_match.group(1),
                        onu_index=int(parts.group(4)),
                        onu_type="unknown",
                        serial_number=onu_if_match.group(1),
                    )
                    current_onu.warnings.append("ONU interface found without matching authorization line")
                    onus[current_onu.onu_interface] = current_onu
            continue

        if not current_onu:
            continue
        if line.startswith("name "):
            current_onu.customer_name = line.removeprefix("name ").strip()
        elif line.startswith("description "):
            raw_description = line.removeprefix("description ").strip()
            current_onu.raw_description = raw_description
            description_warnings = _apply_description(current_onu, raw_description)
            current_onu.warnings.extend(description_warnings)
            warnings.extend(f"{current_onu.onu_interface}: {warning}" for warning in description_warnings)
        elif line.startswith("tcont "):
            profile = re.search(r"profile\s+(\S+)", line, re.I)
            if profile:
                current_onu.upstream_profile = profile.group(1)
        elif line.startswith("gemport "):
            profile = re.search(r"downstream\s+(\S+)", line, re.I)
            if profile:
                current_onu.downstream_profile = profile.group(1)
        elif "switchport vlan" in line:
            vlan = re.search(r"switchport\s+vlan\s+(\d+)", line, re.I)
            if vlan:
                current_onu.vlan = int(vlan.group(1))

    for onu in onus.values():
        if onu.raw_description and not onu.parsed_zone_name:
            warning = "description could not be fully interpreted"
            onu.warnings.append(warning)
            warnings.append(f"{onu.onu_interface}: {warning}")
    return list(onus.values()), warnings


def _apply_description(onu: ParsedOnu, description: str) -> list[str]:
    parsed = parse_onu_description(description)
    onu.parsed_zone_name = parsed.zone_name
    onu.parsed_nap_name = parsed.nap_name
    onu.parsed_nap_port = int(parsed.nap_port_label) if parsed.nap_port_label and parsed.nap_port_label.isdigit() else None
    onu.parsed_odn = parsed.odb_name
    onu.address_reference = parsed.address_reference
    onu.external_id = parsed.external_id
    onu.auth_date = parsed.auth_date
    onu.description_parse_status = parsed.parse_status
    onu.description_parse_warnings = parsed.warnings
    if parsed.external_id:
        onu.serial_number = parsed.external_id
    return parsed.warnings


def _first_int(value: str) -> int | None:
    match = re.search(r"\d+", value)
    return int(match.group(0)) if match else None


def _last_int(value: str) -> int | None:
    matches = re.findall(r"\d+", value)
    return int(matches[-1]) if matches else None


def _value_after_keyword(value: str, keyword: str) -> int | None:
    match = re.search(rf"\b{re.escape(keyword)}\s+(\d+)", value, re.I)
    return int(match.group(1)) if match else None


def _expand_vlan_tokens(value: str) -> list[int]:
    vlan_ids: list[int] = []
    for token in value.split(","):
        token = token.strip()
        if not token:
            continue
        if "-" in token:
            start_text, end_text = token.split("-", 1)
            vlan_ids.extend(range(int(start_text), int(end_text) + 1))
        elif token.isdigit():
            vlan_ids.append(int(token))
    return vlan_ids


def _detect_vendor(name: str) -> str | None:
    upper = name.upper()
    for vendor in ("ZTE", "BTPON", "CDATA", "VSOL", "HUAWEI"):
        if vendor in upper:
            return vendor
    return None


def _infer_capability_mode(ethernet_ports: int, wifi_ports: int, pots_ports: int, rf_ports: int) -> str:
    if wifi_ports > 0:
        return "bridging_routing"
    if ethernet_ports > 1 or pots_ports > 0 or rf_ports > 0:
        return "bridging_routing"
    return "bridging"
