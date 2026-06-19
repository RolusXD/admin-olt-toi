from __future__ import annotations

from datetime import UTC, date, datetime
import re


def build_onu_description(
    *,
    zone: str | None,
    address_reference: str | None,
    nap_name: str | None = None,
    nap_port_label: str | int | None = None,
    odb_name: str | None = None,
    serial: str,
    auth_date: date | datetime | str | None = None,
) -> str:
    authd = _format_auth_date(auth_date)
    parts = ["$$$$zone", _sanitize(zone or "SIN_ZONA"), "descr", _sanitize(address_reference or "")]
    if nap_name:
        parts.extend(["Nap", _sanitize(nap_name)])
    if nap_port_label not in {None, ""}:
        parts.extend(["Puerto", _sanitize(str(nap_port_label))])
    if odb_name:
        parts.extend(["odb", _sanitize(odb_name)])
    parts.extend(["extid", _sanitize(serial), "authd", authd])
    return "_".join(part for part in parts if part != "")


def _format_auth_date(value: date | datetime | str | None) -> str:
    if value is None:
        return datetime.now(UTC).strftime("%Y%m%d")
    if isinstance(value, datetime):
        return value.strftime("%Y%m%d")
    if isinstance(value, date):
        return value.strftime("%Y%m%d")
    digits = re.sub(r"\D", "", value)
    if len(digits) >= 8:
        return digits[:8]
    return datetime.now(UTC).strftime("%Y%m%d")


def _sanitize(value: str) -> str:
    cleaned = value.strip()
    cleaned = re.sub(r"\s+", "_", cleaned)
    cleaned = re.sub(r"_+", "_", cleaned)
    return cleaned.strip("_")
