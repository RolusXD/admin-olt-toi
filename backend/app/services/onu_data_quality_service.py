from __future__ import annotations

from dataclasses import dataclass
import json

from sqlalchemy.orm import Session

from app.models.entities import Onu


DATA_QUALITY_COMPLETE = "complete"
DATA_QUALITY_NEEDS_REVIEW = "needs_review"
DATA_QUALITY_LEGACY_INCOMPLETE = "legacy_incomplete"
DATA_QUALITY_BLOCKED = "blocked"


@dataclass
class OnuDataQualityResult:
    status: str
    missing_fields: list[str]


class OnuDataQualityService:
    """Evaluador reutilizable de calidad documental de ONU (Fase A1).

    Implementa las reglas de la EFO para clasificar ONUs en:
    - ``complete``: campos críticos + EXTID + AUTHD presentes.
    - ``needs_review``: campos críticos presentes, pero falta EXTID y/o AUTHD.
    - ``legacy_incomplete``: falta al menos un campo crítico.
    - ``blocked``: se respeta si ya viene seteado en la entidad (no se recalcula).
    """

    def __init__(self, db: Session):
        self.db = db

    def evaluate(self, onu: Onu) -> OnuDataQualityResult:
        """Evalúa una ONU e hidrata ``onu.data_quality_status``.

        Campos críticos revisados (EFO, sección 4 + 6):
        - customer_name
        - zone (zone_id o zone_name distinto de SIN_ZONA)
        - address_reference
        - nap (nap_id o nap_name)
        - nap_port
        - onu_type
        - vlan

        Campos recomendados:
        - external_id (EXTID comercial)
        - auth_date (AUTHD)
        """

        # Respetar estado "blocked" si estuviera asignado manualmente.
        if onu.data_quality_status == DATA_QUALITY_BLOCKED:
            # Para Fase A2 registramos igualmente una lista vacía de faltantes
            # (observabilidad) sin alterar el estado existente.
            onu.data_quality_missing_fields = json.dumps([], ensure_ascii=True)
            return OnuDataQualityResult(status=onu.data_quality_status, missing_fields=[])

        missing_critical: list[str] = []

        # Nombre cliente
        if not (onu.customer_name and onu.customer_name.strip()):
            missing_critical.append("customer_name")

        # Zona (id o nombre distinto de SIN_ZONA)
        zone_name = (onu.zone_name or onu.parsed_zone_name or "").strip()
        if not onu.zone_id and (not zone_name or zone_name.upper() == "SIN_ZONA"):
            missing_critical.append("zone")

        # Dirección
        if not (onu.address_reference and onu.address_reference.strip()):
            missing_critical.append("address")

        # NAP (id o nombre)
        if not onu.nap_id and not (onu.nap_name and onu.nap_name.strip()):
            missing_critical.append("nap")

        # Puerto NAP
        if not onu.nap_port:
            missing_critical.append("nap_port")

        # Tipo ONU
        if not (onu.onu_type and onu.onu_type.strip()):
            missing_critical.append("onu_type")

        # VLAN
        if not onu.vlan:
            missing_critical.append("vlan")

        # Recomendados
        missing_extid = not (onu.external_id and onu.external_id.strip())
        missing_authd = onu.auth_date is None

        missing_fields: list[str] = list(missing_critical)
        if missing_extid:
            missing_fields.append("external_id")
        if missing_authd:
            missing_fields.append("auth_date")

        if missing_critical:
            status = DATA_QUALITY_LEGACY_INCOMPLETE
        elif missing_extid or missing_authd:
            status = DATA_QUALITY_NEEDS_REVIEW
        else:
            status = DATA_QUALITY_COMPLETE

        onu.data_quality_status = status
        # Persistimos los faltantes como JSON textual para observabilidad.
        onu.data_quality_missing_fields = json.dumps(missing_fields, ensure_ascii=True)
        return OnuDataQualityResult(status=status, missing_fields=missing_fields)
