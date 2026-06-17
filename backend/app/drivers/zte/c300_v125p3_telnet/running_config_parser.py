from dataclasses import dataclass, field
from datetime import UTC, datetime
import re


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


@dataclass(frozen=True)
class ParsedOnuType:
    name: str
    vendor_detected: str | None = None
    max_tcont: int | None = None
    max_gemport: int | None = None
    max_ports: int | None = None


@dataclass(frozen=True)
class ParsedPonPort:
    interface_name: str
    rack: int
    shelf: int
    slot: int
    port: int


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
    onu_types: list[ParsedOnuType]
    pon_ports: list[ParsedPonPort]
    onus: list[ParsedOnu]
    warnings: list[str]

    def summary(self) -> dict:
        zones = sorted({onu.parsed_zone_name for onu in self.onus if onu.parsed_zone_name})
        naps = sorted({onu.parsed_nap_name for onu in self.onus if onu.parsed_nap_name})
        return {
            "vlans": len(self.vlans),
            "gpon_profiles": len(self.gpon_profiles),
            "onu_types": len(self.onu_types),
            "pon_ports": len(self.pon_ports),
            "onus": len(self.onus),
            "zones_detected": zones,
            "naps_detected": naps,
            "warnings": self.warnings,
        }


def parse_running_config(raw_config: str) -> RunningConfigParseResult:
    lines = raw_config.splitlines()
    vlans = _parse_vlans(lines)
    profiles = _parse_profiles(lines)
    onu_types = _parse_onu_types(lines)
    pon_ports = _parse_pon_ports(lines)
    onus, warnings = _parse_onus(lines)
    return RunningConfigParseResult(vlans, profiles, onu_types, pon_ports, onus, warnings)


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
            }
            if profile_type == "tcont":
                current["upstream_rate"] = _value_after_keyword(tail, "maximum") or _last_int(tail)
            if profile_type == "traffic":
                current["downstream_rate"] = _value_after_keyword(tail, "pir") or _last_int(tail)
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
    for raw in lines:
        line = raw.strip()
        match = re.match(r"onu-type\s+(\S+)\s+gpon(.*)", line, re.I)
        if match:
            name = match.group(1)
            current = by_name.setdefault(
                name,
                {
                    "name": name,
                    "vendor_detected": _detect_vendor(name),
                    "max_tcont": None,
                    "max_gemport": None,
                    "max_ports": None,
                },
            )
            tail = match.group(2)
            if "max-tcont" in tail.lower():
                current["max_tcont"] = _last_int(tail) or current["max_tcont"]
            if "max-gemport" in tail.lower():
                current["max_gemport"] = _last_int(tail) or current["max_gemport"]
            if "max-switch-perslot" in tail.lower() or "max-port" in tail.lower():
                current["max_ports"] = _last_int(tail) or current["max_ports"]
    return [ParsedOnuType(**value) for value in by_name.values()]


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
    warnings: list[str] = []
    patterns = {
        "parsed_zone_name": r"zone_(.*?)_descr_",
        "parsed_nap_name": r"Nap_(.*?)_Puerto_",
        "parsed_nap_port": r"(?:^|_)Puerto_(\d+)",
        "parsed_odn": r"odb_(.*?)_extid_",
        "serial_number": r"extid_(.*?)_authd_",
        "auth_date": r"(?:^|_)authd_(\d{8})",
    }
    for field_name, pattern in patterns.items():
        match = re.search(pattern, description, re.I)
        if not match:
            warnings.append(f"missing {field_name} in description")
            continue
        value = match.group(1)
        if field_name == "parsed_nap_port":
            onu.parsed_nap_port = int(value)
        elif field_name == "auth_date":
            try:
                onu.auth_date = datetime.strptime(value, "%Y%m%d").replace(tzinfo=UTC)
            except ValueError:
                warnings.append("invalid auth_date in description")
        else:
            setattr(onu, field_name, value)
    return warnings


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
