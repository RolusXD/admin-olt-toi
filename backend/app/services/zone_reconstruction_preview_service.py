from __future__ import annotations

"""Preview de reconstrucción territorial de Zones por OLT (Fase P4.1).

Este módulo implementa un servicio **de solo lectura** que calcula una
propuesta de Zones por OLT a partir de:

- Onu.parsed_zone_name
- Onu.zone_name
- Zone existentes en la BD
- OLT actual de cada ONU

Sin realizar ningún cambio persistente en la base de datos
(`no INSERT/UPDATE/DELETE`, sin `commit`), en línea con las EFO de
Gobierno de Catálogos y Modelo Territorial FTTH.

El resultado se expone como:

- Un resumen por OLT (`ZoneReconstructionOltSummary`).
- Una matriz ONU actual vs propuesta (`ZoneReconstructionOnuProposal`).

Niveles de confianza por ONU:

- ``ALTA``:
  - `parsed_zone_name` no vacío/distinto de `SIN_ZONA`,
  - repetido en varias ONUs de la misma OLT.

- ``MEDIA``:
  - `parsed_zone_name` no vacío pero poco frecuente (1 sola ONU), o
  - `zone_name` estructurado sin evidencia conflictiva.

- ``BAJA``:
  - Sólo `zone_name` heredado y distinto a la Zone actual de la misma OLT,
    sin repetición clara.

- ``BLOQUEADO``:
  - Sin evidencia territorial (`zone_id` nulo y sin `parsed_zone_name`
    ni `zone_name` significativos), o
  - Caso marcado explícitamente como sin evidencia suficiente.

Reglas clave:

- Scoping estricto por ``olt_id``: ninguna propuesta reutiliza ``Zone``
  de otra OLT. Si una ONU PCM está apuntando a una Zone de LAB, la
  propuesta siempre se formula como ``(olt_id = PCM, name = <zona>)``.
- Para ``OLT-PCM-ZTE-01`` se garantiza que, cuando aparezca
  ``parsed_zone_name == "Lagunas"`` en ONUs PCM, la propuesta incluya
  una Zone ``Lagunas`` propia de PCM (en ``zones_missing_proposed``),
  sin reutilizar la Zone ``Lagunas`` de LAB.
"""

from typing import Dict, List, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import Olt, Onu, Zone
from app.schemas.entities import (
    ZoneReconstructionCatalogProposal,
    ZoneReconstructionOltSummary,
    ZoneReconstructionOnuProposal,
    ZoneReconstructionPreview,
)


def _normalize_zone_token(value: str | None) -> str | None:
    """Normaliza nombres de zona descartando vacíos y ``SIN_ZONA``.

    Se aplica tanto a ``parsed_zone_name`` como a ``zone_name`` para
    evitar tratar `SIN_ZONA` como una zona real.
    """

    if not value:
        return None
    normalized = value.strip()
    if not normalized or normalized.upper() == "SIN_ZONA":
        return None
    return normalized


class ZoneReconstructionPreviewService:
    """Servicio de auditoría para preview de reconstrucción de Zones por OLT.

    Importante:
    - **Solo lectura**: no crea ni modifica entidades; sólo realiza
      consultas y cálculos en memoria.
    - No accede a OLTs reales ni reejecuta parsers; se apoya en el
      estado actual de `Onu` y `Zone` persistido desde snapshots
      confirmados.
    """

    def __init__(self, db: Session):
        self.db = db

    # API principal -----------------------------------------------------

    def preview(self) -> ZoneReconstructionPreview:
        """Calcula la preview completa de Zones por OLT.

        Devuelve un ``ZoneReconstructionPreview`` con:

        - ``summaries``: resumen agregado por OLT.
        - ``onus``: matriz ONU actual vs propuesta.
        """

        # Cargar todo el contexto necesario en memoria (solo SELECT).
        olts: list[Olt] = list(self.db.scalars(select(Olt)))
        zones: list[Zone] = list(self.db.scalars(select(Zone)))
        onus: list[Onu] = list(self.db.scalars(select(Onu)))

        olt_by_id: Dict[int, Olt] = {olt.id: olt for olt in olts}
        zone_by_id: Dict[int, Zone] = {zone.id: zone for zone in zones}

        existing_zones_by_olt: Dict[int, List[str]] = {}
        for zone in zones:
            if zone.olt_id is None:
                # Catálogo territorial sin scoping explícito no debe usarse
                # para propuestas nuevas; se ignora en este preview.
                continue
            existing_zones_by_olt.setdefault(zone.olt_id, []).append(zone.name)

        # Primer pase: determinar candidato de zona por ONU y frecuencias
        # por (olt_id, zone_name) para los niveles de confianza.
        candidate_by_onu_id: Dict[int, Tuple[str | None, str | None]] = {}
        candidate_counts: Dict[Tuple[int, str], int] = {}

        for onu in onus:
            parsed_name = _normalize_zone_token(onu.parsed_zone_name)
            zone_name = _normalize_zone_token(onu.zone_name)

            candidate: str | None
            source: str | None

            if parsed_name:
                candidate = parsed_name
                source = "parsed_zone_name"
            elif zone_name:
                candidate = zone_name
                source = "zone_name"
            else:
                candidate = None
                source = None

            candidate_by_onu_id[onu.id] = (candidate, source)

            if candidate:
                key = (onu.olt_id, candidate)
                candidate_counts[key] = candidate_counts.get(key, 0) + 1

        # Segundo pase: construir matriz ONU y resúmenes por OLT.
        summaries_by_olt: Dict[int, ZoneReconstructionOltSummary] = {}
        onu_rows: list[ZoneReconstructionOnuProposal] = []
        cross_olt_by_onu_id: Dict[int, bool] = {}

        for onu in onus:
            olt = olt_by_id.get(onu.olt_id)
            if not olt:
                # Si por alguna razón la OLT no existe, no podemos
                # proponer nada razonable; marcar como bloqueado.
                proposed_name = None
                confidence = "BLOQUEADO"
                reasons = ["missing_olt_for_onu"]
                current_zone = zone_by_id.get(onu.zone_id) if onu.zone_id else None
                row = ZoneReconstructionOnuProposal(
                    onu_id=onu.id,
                    olt_id=onu.olt_id,
                    olt_code=None,
                    interface=onu.onu_interface,
                    serial=onu.serial_number,
                    customer_name=onu.customer_name,
                    current_zone_id=onu.zone_id,
                    current_zone_name=current_zone.name if current_zone else None,
                    current_zone_olt_id=current_zone.olt_id if current_zone else None,
                    current_zone_olt_code=None,
                    current_zone_olt_name=None,
                    proposed_zone_name=proposed_name,
                    proposed_zone_olt_id=None,
                    proposed_zone_olt_code=None,
                    proposed_zone_olt_name=None,
                    confidence=confidence,
                    reasons=reasons,
                )
                onu_rows.append(row)
                continue

            current_zone = zone_by_id.get(onu.zone_id) if onu.zone_id else None

            candidate, source = candidate_by_onu_id.get(onu.id, (None, None))
            freq = candidate_counts.get((onu.olt_id, candidate), 0) if candidate else 0

            # Detectar cruce de OLT en zone_id actual.
            cross_olt_zone = bool(
                current_zone
                and current_zone.olt_id is not None
                and current_zone.olt_id != onu.olt_id
            )

            cross_olt_by_onu_id[onu.id] = cross_olt_zone

            # Calcular confianza y razones.
            reasons: list[str] = []
            if source == "parsed_zone_name":
                reasons.append("from_parsed_zone_name")
            elif source == "zone_name":
                reasons.append("from_zone_name_field")

            if cross_olt_zone:
                reasons.append("cross_olt_zone_detected")

            if not candidate:
                confidence = "BLOQUEADO"
                reasons.append("no_zone_evidence")
            else:
                if source == "parsed_zone_name":
                    # ALTA: nombre claro y repetido en varias ONUs de la misma OLT.
                    confidence = "ALTA" if freq >= 2 else "MEDIA"
                elif source == "zone_name":
                    # Si la zona estructurada ya es coherente con una Zone de
                    # la misma OLT, se considera alta; si no, baja.
                    if current_zone and not cross_olt_zone and current_zone.name == candidate:
                        confidence = "ALTA"
                    else:
                        confidence = "BAJA"
                else:
                    confidence = "BAJA"

            # Propuesta siempre scopiada por OLT de la ONU; nunca reutiliza
            # Zone de otra OLT aunque el nombre coincida.
            proposed_zone_name = candidate
            proposed_olt_id = onu.olt_id if proposed_zone_name else None
            proposed_olt_code = olt.olt_code if proposed_olt_id else None
            proposed_olt_name = olt.name if proposed_olt_id else None

            row = ZoneReconstructionOnuProposal(
                onu_id=onu.id,
                olt_id=onu.olt_id,
                olt_code=olt.olt_code,
                interface=onu.onu_interface,
                serial=onu.serial_number,
                customer_name=onu.customer_name,
                current_zone_id=onu.zone_id,
                current_zone_name=current_zone.name if current_zone else None,
                current_zone_olt_id=current_zone.olt_id if current_zone else None,
                current_zone_olt_code=olt_by_id.get(current_zone.olt_id).olt_code
                if current_zone and current_zone.olt_id in olt_by_id
                else None,
                current_zone_olt_name=olt_by_id.get(current_zone.olt_id).name
                if current_zone and current_zone.olt_id in olt_by_id
                else None,
                proposed_zone_name=proposed_zone_name,
                proposed_zone_olt_id=proposed_olt_id,
                proposed_zone_olt_code=proposed_olt_code,
                proposed_zone_olt_name=proposed_olt_name,
                confidence=confidence,
                reasons=reasons,
            )
            onu_rows.append(row)

            # Actualizar resumen por OLT.
            summary = summaries_by_olt.get(olt.id)
            if not summary:
                summary = ZoneReconstructionOltSummary(
                    olt_id=olt.id,
                    olt_code=olt.olt_code,
                    olt_name=olt.name,
                    total_onus=0,
                    zones_existing=[],
                    zones_missing_proposed=[],
                    onus_with_correct_zone=0,
                    onus_with_cross_olt_zone=0,
                    onus_without_zone=0,
                    onus_reassignable=0,
                    onus_blocked=0,
                )
                summaries_by_olt[olt.id] = summary

            summary.total_onus += 1

            if cross_olt_zone:
                summary.onus_with_cross_olt_zone += 1
            elif not onu.zone_id:
                summary.onus_without_zone += 1
            else:
                summary.onus_with_correct_zone += 1

            if confidence == "BLOQUEADO":
                summary.onus_blocked += 1
            elif proposed_zone_name and (
                # Reasignable si:
                # - No tiene zone_id, o
                # - La zone actual es de otra OLT, o
                # - La zone actual (misma OLT) tiene nombre distinto.
                not onu.zone_id
                or cross_olt_zone
                or (current_zone and not cross_olt_zone and current_zone.name != proposed_zone_name)
            ):
                summary.onus_reassignable += 1

        # Completar listas de zonas existentes y faltantes propuestas.
        for olt in olts:
            summary = summaries_by_olt.get(olt.id)
            if not summary:
                # OLT sin ONUs; aún así exponer resumen mínimo.
                existing = existing_zones_by_olt.get(olt.id, [])
                summaries_by_olt[olt.id] = ZoneReconstructionOltSummary(
                    olt_id=olt.id,
                    olt_code=olt.olt_code,
                    olt_name=olt.name,
                    total_onus=0,
                    zones_existing=sorted(existing),
                    zones_missing_proposed=[],
                    onus_with_correct_zone=0,
                    onus_with_cross_olt_zone=0,
                    onus_without_zone=0,
                    onus_reassignable=0,
                    onus_blocked=0,
                )
                continue

            existing = set(existing_zones_by_olt.get(olt.id, []))
            proposed: set[str] = set()
            for onu in onus:
                if onu.olt_id != olt.id:
                    continue
                candidate, _ = candidate_by_onu_id.get(onu.id, (None, None))
                if candidate and candidate not in existing:
                    proposed.add(candidate)

            summary.zones_existing = sorted(existing)
            summary.zones_missing_proposed = sorted(proposed)

        # Construir catálogo consolidado de propuestas por OLT/zona.
        # Agrupamos por (olt_id, proposed_zone_name) usando las filas ONU.
        zone_by_olt_and_name: Dict[Tuple[int, str], Zone] = {}
        for zone in zones:
            if zone.olt_id is None:
                continue
            zone_by_olt_and_name[(zone.olt_id, zone.name)] = zone

        groups: Dict[Tuple[int, str], List[ZoneReconstructionOnuProposal]] = {}
        for row in onu_rows:
            if not row.proposed_zone_name or not row.proposed_zone_olt_id:
                continue
            key = (row.proposed_zone_olt_id, row.proposed_zone_name)
            groups.setdefault(key, []).append(row)

        catalog_proposals: list[ZoneReconstructionCatalogProposal] = []
        for (olt_id, zone_name), rows in groups.items():
            olt = olt_by_id.get(olt_id)
            if not olt:
                continue

            onu_count = len(rows)
            parsed_count = 0
            zone_name_count = 0
            affected_by_cross_olt = False

            for row in rows:
                candidate, source = candidate_by_onu_id.get(row.onu_id, (None, None))
                if source == "parsed_zone_name":
                    parsed_count += 1
                elif source == "zone_name":
                    zone_name_count += 1
                if cross_olt_by_onu_id.get(row.onu_id):
                    affected_by_cross_olt = True

            if onu_count == 0:
                continue

            zone_obj = zone_by_olt_and_name.get((olt_id, zone_name))
            exists_in_olt = zone_obj is not None
            existing_zone_id = zone_obj.id if zone_obj else None

            # Confianza agregada por zona.
            if parsed_count == 0 and zone_name_count > 0:
                agg_confidence = "BAJA"
            elif parsed_count > 0:
                if onu_count >= 2 and parsed_count * 2 > onu_count:
                    agg_confidence = "ALTA"
                elif onu_count == 1 and parsed_count == 1:
                    agg_confidence = "MEDIA"
                else:
                    agg_confidence = "MEDIA"
            else:
                # Sin evidencia clara; debería ser raro porque no se
                # crean grupos para proposed_zone_name nulo.
                agg_confidence = "BLOQUEADO"

            reasons: list[str] = []
            if exists_in_olt:
                reasons.append("zone_exists_in_olt")
            else:
                reasons.append("zone_missing_in_olt")
            if parsed_count > 0:
                reasons.append("from_parsed_zone_name")
            if zone_name_count > 0:
                reasons.append("from_zone_name_field")
            if affected_by_cross_olt:
                reasons.append("affected_by_cross_olt_zone")

            source_fields: list[str] = []
            if parsed_count > 0:
                source_fields.append("parsed_zone_name")
            if zone_name_count > 0:
                source_fields.append("zone_name")

            catalog_proposals.append(
                ZoneReconstructionCatalogProposal(
                    olt_id=olt.id,
                    olt_code=olt.olt_code,
                    olt_name=olt.name,
                    proposed_zone_name=zone_name,
                    exists_in_olt=exists_in_olt,
                    existing_zone_id=existing_zone_id,
                    onu_count=onu_count,
                    confidence=agg_confidence,
                    reasons=reasons,
                    source_fields=source_fields,
                    onus=rows,
                )
            )

        # Ordenar resúmenes de forma estable por (environment, olt_code).
        ordered_summaries = sorted(
            summaries_by_olt.values(),
            key=lambda s: (
                olt_by_id.get(s.olt_id).environment if olt_by_id.get(s.olt_id) else "production",
                s.olt_code,
            ),
        )

        return ZoneReconstructionPreview(
            summaries=ordered_summaries,
            catalog_proposals=catalog_proposals,
            onus=onu_rows,
        )
