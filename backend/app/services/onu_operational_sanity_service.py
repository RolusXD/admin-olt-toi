from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.drivers.zte.c300_v125p3_telnet.zte_onu_description_parser import parse_onu_description
from app.drivers.zte.c300_v125p3_telnet.zte_onu_management_mode_parser import (
    ParsedOnuManagementMode,
    parse_onu_management_modes,
)
from app.models.entities import ConfigSnapshot, ImportJob, Olt, Onu
from app.schemas.entities import (
    OnuOperationalSanityChange,
    OnuOperationalSanityPreview,
    OnuOperationalSanitySummary,
)


class OnuOperationalSanityService:
    """Herramienta de sólo lectura para saneamiento operacional de ONUs históricas.

    Fase P3.5 – Saneamiento Operacional de ONUs Históricas.

    Capacidades principales (modo auditoría):

    1. Recalcular ``service_mode_code`` a partir de los bloques
       ``pon-onu-mng`` usando ``parse_onu_management_modes`` sobre el
       último snapshot confirmado por OLT.

    2. Reprocesar descripciones con ``parse_onu_description`` para
       sugerir zona, NAP y fecha AUTHD cuando falten en la ONU.

    3. Trabajar únicamente sobre OLTs en ``environment = "production"``
       excluyendo explícitamente la OLT de laboratorio
       ``OLT-LAB-ZTE-01`` incluso si estuviera mal etiquetada.

    4. No escribir en BD: no realiza ``commit`` ni modifica entidades
       persistidas; sólo calcula un preview de cambios propuestos.
    """

    def __init__(self, db: Session):
        self.db = db

    # API principal -----------------------------------------------------

    def preview(self) -> OnuOperationalSanityPreview:
        """Ejecuta la auditoría y devuelve un resumen + listado de cambios.

        No persiste ningún cambio; toda la información devuelta es una
        vista calculada en memoria para apoyar tareas de saneamiento
        manual posterior.
        """

        summary = OnuOperationalSanitySummary(
            total_onus=0,
            candidate_service_mode_updates=0,
            candidate_zone_updates=0,
            candidate_nap_updates=0,
            candidate_auth_date_updates=0,
            ambiguous_cases=0,
        )
        changes: list[OnuOperationalSanityChange] = []

        # Sólo OLTs de producción; excluir explícitamente la OLT de LAB.
        olts = list(
            self.db.scalars(
                select(Olt).where(Olt.environment == "production")
            )
        )
        olts = [olt for olt in olts if olt.olt_code != "OLT-LAB-ZTE-01"]

        for olt in olts:
            modes_by_if = self._management_modes_by_onu_interface(olt)

            onus = list(self.db.scalars(select(Onu).where(Onu.olt_id == olt.id)))
            summary.total_onus += len(onus)

            for onu in onus:
                change = self._build_change_for_onu(olt, onu, modes_by_if.get(onu.onu_interface))
                if not change:
                    continue

                # Actualizar contadores de resumen según los campos sugeridos.
                if (
                    change.suggested_service_mode_code
                    and (change.current_service_mode_code or "")
                    != change.suggested_service_mode_code
                ):
                    summary.candidate_service_mode_updates += 1

                if (
                    change.suggested_zone_name
                    and (change.current_zone_name or "").upper()
                    != change.suggested_zone_name.upper()
                ):
                    summary.candidate_zone_updates += 1

                if (
                    change.suggested_nap_name
                    and (change.current_nap_name or "").upper()
                    != change.suggested_nap_name.upper()
                ):
                    summary.candidate_nap_updates += 1

                if (
                    change.suggested_auth_date
                    and change.current_auth_date != change.suggested_auth_date
                ):
                    summary.candidate_auth_date_updates += 1

                if "description_ambiguous" in change.reasons:
                    summary.ambiguous_cases += 1

                changes.append(change)

        return OnuOperationalSanityPreview(summary=summary, changes=changes)

    # Helpers internos --------------------------------------------------

    def _management_modes_by_onu_interface(self, olt: Olt) -> dict[str, ParsedOnuManagementMode]:
        """Carga modos de gestión desde el último snapshot confirmado de la OLT.

        Si no hay importaciones confirmadas o snapshots válidos, devuelve
        un diccionario vacío.
        """

        job = self.db.scalar(
            select(ImportJob)
            .where(ImportJob.olt_id == olt.id, ImportJob.status == "confirmed")
            .order_by(ImportJob.confirmed_at.desc().nullslast())
            .limit(1)
        )
        if not job:
            return {}

        snapshot = self.db.get(ConfigSnapshot, job.raw_config_snapshot_id)
        if not snapshot or not snapshot.raw_config:
            return {}

        modes = parse_onu_management_modes(snapshot.raw_config)
        return {item.onu_interface: item for item in modes}

    def _build_change_for_onu(
        self,
        olt: Olt,
        onu: Onu,
        management_mode: ParsedOnuManagementMode | None,
    ) -> OnuOperationalSanityChange | None:
        """Construye un bloque de cambios propuestos para una ONU.

        No modifica la instancia ``onu``; sólo lee su estado actual y
        devuelve una representación sugerida. Si no hay ninguna mejora
        detectable, devuelve ``None``.
        """

        suggested_service_mode_code: str | None = None
        suggested_zone_name: str | None = None
        suggested_nap_name: str | None = None
        suggested_auth_date: datetime | None = None
        reasons: list[str] = []

        # 1) Recalcular service_mode_code desde pon-onu-mng cuando falte.
        if management_mode and management_mode.mode_code != "unknown":
            current_mode = (onu.service_mode_code or "").strip()
            if not current_mode:
                suggested_service_mode_code = management_mode.mode_code
                reasons.append("service_mode_from_snapshot")

        # 2) Reprocesar descripción para zona/NAP/AUTHD cuando falten.
        description_source = (
            onu.description_original
            or onu.raw_description
            or onu.description_generated
        )
        parsed = None
        if description_source:
            parsed = parse_onu_description(description_source)

            # Zona
            if parsed.zone_name:
                current_zone = (onu.zone_name or onu.parsed_zone_name or "").strip()
                if not current_zone or current_zone.upper() == "SIN_ZONA":
                    suggested_zone_name = parsed.zone_name
                    reasons.append("zone_from_description")

            # NAP
            if parsed.nap_name:
                current_nap = (onu.nap_name or "").strip()
                if not current_nap:
                    suggested_nap_name = parsed.nap_name
                    reasons.append("nap_from_description")

            # AUTHD
            if parsed.auth_date and onu.auth_date is None:
                suggested_auth_date = parsed.auth_date
                reasons.append("auth_date_from_description")

            # Casos ambiguos: descripción con warnings o parseo parcial.
            if parsed.warnings and parsed.parse_status in {"partial", "unknown"}:
                reasons.append("description_ambiguous")

        if not (
            suggested_service_mode_code
            or suggested_zone_name
            or suggested_nap_name
            or suggested_auth_date
        ):
            return None

        return OnuOperationalSanityChange(
            onu_id=onu.id,
            olt_id=olt.id,
            olt_code=olt.olt_code,
            onu_interface=onu.onu_interface,
            serial_number=onu.serial_number,
            current_service_mode_code=onu.service_mode_code,
            suggested_service_mode_code=suggested_service_mode_code,
            current_zone_name=onu.zone_name or onu.parsed_zone_name,
            suggested_zone_name=suggested_zone_name,
            current_nap_name=onu.nap_name,
            suggested_nap_name=suggested_nap_name,
            current_auth_date=onu.auth_date,
            suggested_auth_date=suggested_auth_date,
            reasons=reasons,
        )
