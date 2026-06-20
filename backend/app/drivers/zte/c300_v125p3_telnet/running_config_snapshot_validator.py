from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import re


FINAL_PROMPT = re.compile(r"(?m)(?:^|\n)[\w.-]+(?:\([^\r\n#)]*\))?#\s*$")
ONU_INTERFACE = re.compile(r"^\s*interface\s+(gpon-onu_\d+/\d+/\d+:\d+)\s*$", re.I)
PON_INTERFACE = re.compile(r"^\s*interface\s+(gpon-olt_\d+/\d+/\d+)\s*$", re.I)
ONU_AUTH = re.compile(r"^\s*onu\s+(\d+)\s+type\s+\S+\s+sn\s+(\S+)\s*$", re.I)


@dataclass(frozen=True)
class SnapshotValidation:
    is_complete: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    authorized_interfaces: list[str] = field(default_factory=list)
    configured_interfaces: list[str] = field(default_factory=list)

    def metrics(self) -> dict:
        return {
            "authorized_interfaces": len(self.authorized_interfaces),
            "configured_interfaces": len(self.configured_interfaces),
        }


def snapshot_checksum(raw_config: str) -> str:
    return hashlib.sha256(raw_config.encode("utf-8")).hexdigest()


def validate_running_config_snapshot(raw_config: str, require_final_prompt: bool = False) -> SnapshotValidation:
    errors: list[str] = []
    warnings: list[str] = []
    authorized: list[str] = []
    configured: list[str] = []
    current_pon: str | None = None

    if not raw_config or len(raw_config.strip()) < 50:
        errors.append("Snapshot vacio o demasiado corto")
    if "--More--" in raw_config:
        errors.append("Snapshot conserva marcadores de paginacion --More--")
    if require_final_prompt and not FINAL_PROMPT.search(raw_config.replace("\r", "")):
        errors.append("Snapshot Telnet sin prompt final estable")

    lines = raw_config.splitlines()
    block_starts: list[tuple[int, str]] = []
    for line_number, raw_line in enumerate(lines):
        pon_match = PON_INTERFACE.match(raw_line)
        if pon_match:
            current_pon = pon_match.group(1).lower()
            continue
        auth_match = ONU_AUTH.match(raw_line)
        if auth_match and current_pon:
            onu_id = int(auth_match.group(1))
            authorized.append(current_pon.replace("gpon-olt_", "gpon-onu_", 1) + f":{onu_id}")
            continue
        onu_match = ONU_INTERFACE.match(raw_line)
        if onu_match:
            interface_name = onu_match.group(1).lower()
            configured.append(interface_name)
            block_starts.append((line_number, interface_name))

    for position, (start, interface_name) in enumerate(block_starts):
        next_start = block_starts[position + 1][0] if position + 1 < len(block_starts) else len(lines)
        for candidate in range(start + 1, next_start):
            if re.match(r"^\s*(?:interface|pon-onu-mng)\s+", lines[candidate], re.I):
                next_start = candidate
                break
        body = [line.strip() for line in lines[start + 1:next_start] if line.strip() and line.strip() != "!"]
        if not body:
            errors.append(f"Bloque interface incompleto: {interface_name}")

    if len(configured) != len(set(configured)):
        errors.append("Existen bloques interface gpon-onu duplicados")
    if len(authorized) != len(set(authorized)):
        errors.append("Existen autorizaciones ONU duplicadas")

    authorized_set = set(authorized)
    configured_set = set(configured)
    missing_blocks = sorted(authorized_set - configured_set)
    orphan_blocks = sorted(configured_set - authorized_set)
    if missing_blocks:
        errors.append(f"Faltan {len(missing_blocks)} bloques interface para ONUs autorizadas; ejemplo: {missing_blocks[0]}")
    if orphan_blocks:
        errors.append(f"Existen {len(orphan_blocks)} bloques interface sin autorizacion; ejemplo: {orphan_blocks[0]}")
    if len(authorized) != len(configured):
        errors.append(f"Cantidad ONU inconsistente: autorizadas={len(authorized)}, interfaces={len(configured)}")
    if not authorized and not configured:
        if not any(PON_INTERFACE.match(line) for line in raw_config.splitlines()):
            errors.append("Snapshot sin interfaces GPON reconocibles")
        else:
            warnings.append("Snapshot sin ONUs autorizadas")

    return SnapshotValidation(
        is_complete=not errors,
        errors=errors,
        warnings=warnings,
        authorized_interfaces=sorted(authorized_set),
        configured_interfaces=sorted(configured_set),
    )


def validate_parsed_interface_count(validation: SnapshotValidation, parsed_count: int) -> list[str]:
    expected = len(validation.configured_interfaces)
    if parsed_count == expected:
        return []
    return [f"Cantidad parseada inconsistente: interfaces={expected}, onus_parseadas={parsed_count}"]
