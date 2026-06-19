from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
import re


@dataclass(frozen=True)
class ParsedOnuDescription:
    description_original: str
    zone_name: str | None = None
    address_reference: str | None = None
    nap_name: str | None = None
    nap_port_label: str | None = None
    odb_name: str | None = None
    external_id: str | None = None
    auth_date: datetime | None = None
    parse_status: str = "partial"
    warnings: list[str] = field(default_factory=list)


def parse_onu_description(value: str | None) -> ParsedOnuDescription:
    original = (value or "").strip()
    description = re.sub(r"^\s*description\s+", "", original, flags=re.IGNORECASE).strip()
    warnings: list[str] = []

    zone = _find_between(description, "zone", ["descr", "nap", "puerto", "odb", "odn", "extid", "authd"])
    authd_raw = _find_after(description, "authd")
    extid = _find_between(description, "extid", ["authd"])
    odb = _find_odb(description)
    nap = _find_nap(description)
    port = _find_port(description)
    address = _find_address(description, nap, port, odb, extid, authd_raw)

    auth_date = None
    if authd_raw:
        match = re.search(r"\d{8}", authd_raw)
        if match:
            try:
                auth_date = datetime.strptime(match.group(0), "%Y%m%d").replace(tzinfo=UTC)
            except ValueError:
                warnings.append("invalid authd date")
        else:
            warnings.append("authd token without yyyymmdd date")

    if not zone:
        warnings.append("missing zone")
    if not address:
        warnings.append("missing descr/address")
    if not extid:
        warnings.append("missing extid")
    if not auth_date:
        warnings.append("missing authd")

    useful_fields = [zone, address, nap, port, odb, extid, auth_date]
    if zone and extid and auth_date:
        status = "parsed"
    elif any(useful_fields):
        status = "partial"
    elif original:
        status = "unparsed"
    else:
        status = "empty"

    return ParsedOnuDescription(
        description_original=original,
        zone_name=_clean(zone),
        address_reference=_clean(address),
        nap_name=_clean(nap),
        nap_port_label=_clean(port),
        odb_name=_clean(odb),
        external_id=_clean(extid),
        auth_date=auth_date,
        parse_status=status,
        warnings=warnings,
    )


def _find_between(value: str, token: str, stop_tokens: list[str]) -> str | None:
    start = _token_match(value, token)
    if not start:
        return None
    begin = start.end()
    end = len(value)
    for stop in stop_tokens:
        match = _token_match(value[begin:], stop)
        if match:
            end = min(end, begin + match.start())
    return value[begin:end].strip(" _-")


def _find_after(value: str, token: str) -> str | None:
    match = _token_match(value, token)
    if not match:
        return None
    return value[match.end():].strip(" _-")


def _token_match(value: str, token: str) -> re.Match[str] | None:
    if token == "puerto":
        pattern = r"(?i)(?:^|[$_\s])(?:puerto|puero|p)(?:[_\s]*)"
    elif token == "nap":
        pattern = r"(?i)(?:^|[$_\s])(?:nap|nao)(?:[_\s]*)"
    elif token == "odb":
        pattern = r"(?i)(?:^|[$_\s])(?:odb)(?:[_\s]*)"
    elif token == "odn":
        pattern = r"(?i)(?:^|[$_\s])(?:odn)(?:[_\s]*)"
    else:
        pattern = rf"(?i)(?:^|[$_\s]){re.escape(token)}(?:[_\s]*)"
    return re.search(pattern, value)


def _find_odb(value: str) -> str | None:
    odb = _find_between(value, "odb", ["extid", "authd"])
    if odb:
        return odb
    return _find_between(value, "odn", ["extid", "authd"])


def _find_nap(value: str) -> str | None:
    nap = _find_between(value, "nap", ["puerto", "odb", "odn", "extid", "authd"])
    if not nap:
        return None
    p_match = re.search(r"(?i)(.*?)[_\s]+P(\d+)\s*$", nap)
    if p_match:
        return p_match.group(1)
    return nap


def _find_port(value: str) -> str | None:
    port = _find_between(value, "puerto", ["odb", "odn", "extid", "authd"])
    if port:
        match = re.search(r"\d+", port)
        return match.group(0) if match else port
    nap = _find_between(value, "nap", ["odb", "odn", "extid", "authd"])
    if nap:
        match = re.search(r"(?i)(?:^|[_\s])P(?:uerto)?[_\s]*(\d+)", nap)
        if match:
            return match.group(1)
    return None


def _find_address(
    value: str,
    nap: str | None,
    port: str | None,
    odb: str | None,
    extid: str | None,
    authd: str | None,
) -> str | None:
    port_match = _token_match(value, "puerto")
    if port_match:
        remainder = value[port_match.end():]
        remainder = re.sub(r"^\d+", "", remainder).strip(" _-,")
        end = len(remainder)
        for stop in ["odb", "odn", "extid", "authd"]:
            match = _token_match(remainder, stop)
            if match:
                end = min(end, match.start())
        direct = remainder[:end].strip(" _-,")
        if direct:
            return direct

    descr = _find_between(value, "descr", ["odb", "odn", "extid", "authd"])
    if not descr:
        without_prefix = re.sub(r"^\$+", "", value).strip(" _")
        if not _token_match(without_prefix, "zone") and without_prefix:
            return without_prefix
        return None

    pieces = descr
    for candidate in [nap, port, odb, extid, authd]:
        if candidate:
            pieces = re.sub(re.escape(candidate), "", pieces, flags=re.IGNORECASE)
    pieces = re.sub(r"(?i)(?:^|[_\s])(?:nap|nao|puerto|puero|odb|odn)(?:[_\s]*)", "_", pieces)
    return pieces.strip(" _-")


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = re.sub(r"[_\s]+", "_", value.strip(" _-"))
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned or None
