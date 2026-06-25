from __future__ import annotations

"""Centro de Auditoría Territorial (P4.5).

Servicio de solo lectura que consolida en una única vista los previews
territoriales existentes:

- Preview de Zones por OLT (`ZoneReconstructionPreviewService`).
- Preview de NAP/ODN/ODB por OLT (`NapReconstructionPreviewService`).

No realiza ningún cambio en BD (solo SELECT + cálculo en memoria), no
expone flujos de apply y no accede a OLTs reales.
"""

from datetime import datetime, timezone
from typing import Dict, Iterable, List, Tuple

from sqlalchemy.orm import Session

from app.schemas.entities import (
    NapReconstructionPreview,
    TerritorialAuditCenter,
    TerritorialAuditConfidenceSummary,
    TerritorialAuditIssue,
    TerritorialAuditOltSummary,
    TerritorialAuditStateSummary,
    ZoneReconstructionPreview,
)
from app.services.nap_reconstruction_preview_service import (
    NapReconstructionPreviewService,
)
from app.services.zone_reconstruction_preview_service import (
    ZoneReconstructionPreviewService,
)


class TerritorialAuditCenterService:
    """Agrega en memoria los previews territoriales para construir P4.5.

    Importante (alineado con las EFO y reglas del proyecto):

    - Solo lectura: utiliza los servicios de preview existentes, que
      únicamente ejecutan SELECT y cálculos en memoria.
    - No crea ni modifica entidades; no hay INSERT/UPDATE/DELETE ni
      commit.
    - No reejecuta parsers ni accede a OLTs reales.
    """

    def __init__(self, db: Session) -> None:
        self._db = db

    # API principal -----------------------------------------------------

    def build(self) -> TerritorialAuditCenter:
        """Construye la vista consolidada del Centro de Auditoría.

        Reutiliza internamente los previews de Zones y NAP/ODN/ODB.
        """

        zones_preview = ZoneReconstructionPreviewService(self._db).preview()
        naps_preview = NapReconstructionPreviewService(self._db).preview()

        olt_summaries = self._build_olt_summaries(zones_preview, naps_preview)
        zone_state_summary = self._build_zone_state_summary(zones_preview)
        nap_state_summary = self._build_nap_state_summary(naps_preview)
        confidence_summary = self._build_confidence_summary(
            zones_preview, naps_preview
        )

        critical_issues = self._build_critical_issues(
            zones_preview, naps_preview, olt_summaries
        )
        recommendations = self._build_recommendations(critical_issues)

        return TerritorialAuditCenter(
            generated_at=datetime.now(timezone.utc),
            olt_summaries=list(olt_summaries.values()),
            zone_state_summary=zone_state_summary,
            nap_state_summary=nap_state_summary,
            confidence_summary=confidence_summary,
            critical_issues=critical_issues,
            recommendations=recommendations,
        )

    # Construcción de resúmenes por OLT --------------------------------

    def _build_olt_summaries(
        self,
        zones_preview: ZoneReconstructionPreview,
        naps_preview: NapReconstructionPreview,
    ) -> Dict[int, TerritorialAuditOltSummary]:
        """Fusiona los resúmenes de Zones y NAP/ODN/ODB por OLT."""

        by_olt: Dict[int, TerritorialAuditOltSummary] = {}

        # Punto de partida: información de Zones.
        for zs in zones_preview.summaries:
            by_olt[zs.olt_id] = TerritorialAuditOltSummary(
                olt_id=zs.olt_id,
                olt_code=zs.olt_code,
                olt_name=zs.olt_name,
                total_onus=zs.total_onus,
                zones_existing_count=len(zs.zones_existing),
                zones_missing_count=len(zs.zones_missing_proposed),
                zones_reassignable_onus=zs.onus_reassignable,
                zones_blocked_onus=zs.onus_blocked,
                naps_existing_count=0,
                naps_proposed_count=0,
                naps_new_count=0,
                naps_exists_count=0,
                naps_review_count=0,
                naps_blocked_count=0,
                onus_with_cross_olt_zone=zs.onus_with_cross_olt_zone,
                onus_with_cross_olt_nap=0,
                territorial_health_score=0,
                status="CRITICAL",
            )

        # Incorporar información de NAPs.
        for ns in naps_preview.summaries:
            summary = by_olt.get(ns.olt_id)
            if summary is None:
                summary = TerritorialAuditOltSummary(
                    olt_id=ns.olt_id,
                    olt_code=ns.olt_code,
                    olt_name=ns.olt_name,
                    total_onus=ns.total_onus,
                    zones_existing_count=0,
                    zones_missing_count=0,
                    zones_reassignable_onus=0,
                    zones_blocked_onus=0,
                    naps_existing_count=0,
                    naps_proposed_count=0,
                    naps_new_count=0,
                    naps_exists_count=0,
                    naps_review_count=0,
                    naps_blocked_count=0,
                    onus_with_cross_olt_zone=0,
                    onus_with_cross_olt_nap=0,
                    territorial_health_score=0,
                    status="CRITICAL",
                )
                by_olt[ns.olt_id] = summary

            summary.naps_existing_count = len(ns.existing_naps)
            summary.naps_proposed_count = ns.proposed_catalog_count
            summary.naps_new_count = ns.proposed_new_count
            summary.naps_exists_count = ns.proposed_exists_count
            summary.naps_review_count = ns.proposed_review_count
            summary.naps_blocked_count = ns.proposed_blocked_count
            summary.onus_with_cross_olt_nap = ns.onus_with_cross_olt_nap

            # total_onus coherente si viene sin Zones.
            if summary.total_onus == 0:
                summary.total_onus = ns.total_onus

        # Calcular health_score y status por OLT.
        for summary in by_olt.values():
            score = self._calculate_health_score(summary)
            summary.territorial_health_score = score
            summary.status = self._status_from_score(score)

        return by_olt

    # Score y estado ----------------------------------------------------

    @staticmethod
    def _calculate_health_score(summary: TerritorialAuditOltSummary) -> int:
        """Calcula `territorial_health_score` 0–100 según reglas P4.5.

        - Parte de 100.
        - Resta por ONUs con zone cruzada.
        - Resta por ONUs con nap cruzado.
        - Resta por propuestas BLOCKED.
        - Resta por propuestas REVIEW.
        - Mínimo 0 (se trunca).
        """

        score = 100

        score -= summary.onus_with_cross_olt_zone
        score -= summary.onus_with_cross_olt_nap
        score -= summary.naps_blocked_count
        score -= summary.naps_review_count

        if score < 0:
            score = 0
        if score > 100:
            score = 100
        return score

    @staticmethod
    def _status_from_score(score: int) -> str:
        if score >= 90:
            return "HEALTHY"
        if score >= 70:
            return "NEEDS_REVIEW"
        if score >= 40:
            return "DEGRADED"
        return "CRITICAL"

    # Resúmenes agregados -----------------------------------------------

    @staticmethod
    def _build_zone_state_summary(
        zones_preview: ZoneReconstructionPreview,
    ) -> TerritorialAuditStateSummary:
        summary = TerritorialAuditStateSummary()
        # Zones no tienen `state` explícito; inferimos:
        for catalog in zones_preview.catalog_proposals:
            if catalog.exists_in_olt:
                summary.exists_count += 1
            else:
                summary.new_count += 1
        return summary

    @staticmethod
    def _build_nap_state_summary(
        naps_preview: NapReconstructionPreview,
    ) -> TerritorialAuditStateSummary:
        summary = TerritorialAuditStateSummary()
        for catalog in naps_preview.catalog_proposals:
            state = (catalog.state or "").upper()
            if state == "NEW":
                summary.new_count += 1
            elif state == "EXISTS":
                summary.exists_count += 1
            elif state == "REVIEW":
                summary.review_count += 1
            elif state == "BLOCKED":
                summary.blocked_count += 1
            elif state == "MERGE":
                summary.merge_count += 1
        return summary

    @staticmethod
    def _build_confidence_summary(
        zones_preview: ZoneReconstructionPreview,
        naps_preview: NapReconstructionPreview,
    ) -> TerritorialAuditConfidenceSummary:
        summary = TerritorialAuditConfidenceSummary()

        for catalog in zones_preview.catalog_proposals:
            label = (catalog.confidence or "").upper()
            if label == "ALTA":
                summary.alta_count += 1
            elif label == "MEDIA":
                summary.media_count += 1
            elif label == "BAJA":
                summary.baja_count += 1
            elif label == "BLOQUEADO":
                summary.bloqueado_count += 1

        for catalog in naps_preview.catalog_proposals:
            label = (catalog.confidence or "").upper()
            if label == "ALTA":
                summary.alta_count += 1
            elif label == "MEDIA":
                summary.media_count += 1
            elif label == "BAJA":
                summary.baja_count += 1
            elif label == "BLOQUEADO":
                summary.bloqueado_count += 1

        return summary

    # Issues y recomendaciones ------------------------------------------

    def _build_critical_issues(
        self,
        zones_preview: ZoneReconstructionPreview,
        naps_preview: NapReconstructionPreview,
        olt_summaries: Dict[int, TerritorialAuditOltSummary],
    ) -> List[TerritorialAuditIssue]:
        issues: List[TerritorialAuditIssue] = []

        # Index rápidos por OLT y nombre.
        zones_by_olt: Dict[int, Tuple[int, int]] = {}
        for zs in zones_preview.summaries:
            zones_by_olt[zs.olt_id] = (
                len(zs.zones_existing),
                len(zs.zones_missing_proposed),
            )

        naps_by_olt: Dict[int, Tuple[int, int]] = {}
        for ns in naps_preview.summaries:
            naps_by_olt[ns.olt_id] = (
                ns.naps_with_id if hasattr(ns, "naps_with_id") else ns.onus_with_nap_id,
                ns.proposed_catalog_count,
            )

        # 1) OLT sin zonas propias / sin NAPs propios.
        for olt_id, s in olt_summaries.items():
            zones_existing, zones_missing = zones_by_olt.get(olt_id, (0, 0))
            naps_existing, naps_proposed = naps_by_olt.get(olt_id, (0, 0))

            if zones_existing == 0:
                issues.append(
                    TerritorialAuditIssue(
                        issue_type="NO_ZONES",
                        severity="HIGH",
                        olt_id=olt_id,
                        olt_code=s.olt_code,
                        entity_type="OLT",
                        entity_name=s.olt_name,
                        affected_onu_count=s.total_onus,
                        message=(
                            "La OLT no tiene zonas propias en catálogo; todas las "
                            "ONUs dependen de zonas propuestas o cruzadas."
                        ),
                        recommendation=(
                            "Revisar y confirmar un catálogo de Zones por OLT antes "
                            "de aplicar reasignaciones territoriales."
                        ),
                    )
                )

            if naps_existing == 0:
                issues.append(
                    TerritorialAuditIssue(
                        issue_type="NO_NAPS",
                        severity="HIGH",
                        olt_id=olt_id,
                        olt_code=s.olt_code,
                        entity_type="OLT",
                        entity_name=s.olt_name,
                        affected_onu_count=s.total_onus,
                        message=(
                            "La OLT no tiene NAP/ODN/ODB propios en catálogo; las ONUs "
                            "apuntan a NAPs cruzados o dependen solo de propuestas."
                        ),
                        recommendation=(
                            "Reconstruir el catálogo NAP/ODN/ODB para la OLT antes de "
                            "cualquier apply territorial."
                        ),
                    )
                )

            # Zonas propuestas faltantes / NAPs propuestos faltantes.
            if zones_missing > 0:
                issues.append(
                    TerritorialAuditIssue(
                        issue_type="ZONES_MISSING",
                        severity="MEDIUM",
                        olt_id=olt_id,
                        olt_code=s.olt_code,
                        entity_type="ZONE_CATALOG",
                        entity_name=None,
                        affected_onu_count=None,
                        message=(
                            f"Hay {zones_missing} zonas propuestas que aún no "
                            "existen en el catálogo territorial de la OLT."
                        ),
                        recommendation=(
                            "Revisar las Zones propuestas y decidir cuáles deben "
                            "crearse en el catálogo territorial."
                        ),
                    )
                )

            if naps_proposed > 0:
                issues.append(
                    TerritorialAuditIssue(
                        issue_type="NAPS_MISSING",
                        severity="MEDIUM",
                        olt_id=olt_id,
                        olt_code=s.olt_code,
                        entity_type="NAP_CATALOG",
                        entity_name=None,
                        affected_onu_count=None,
                        message=(
                            f"Hay {naps_proposed} candidatos NAP/ODN/ODB propuestos "
                            "que aún no están materializados en el catálogo."
                        ),
                        recommendation=(
                            "Revisar candidatos NAP/ODN/ODB y consolidar aquellos "
                            "que representen planta externa real."
                        ),
                    )
                )

            # ONUs con cruce de zone/nap.
            if s.onus_with_cross_olt_zone > 0:
                issues.append(
                    TerritorialAuditIssue(
                        issue_type="CROSS_OLT_ZONE",
                        severity="CRITICAL",
                        olt_id=olt_id,
                        olt_code=s.olt_code,
                        entity_type="ONU",
                        entity_name="*",
                        affected_onu_count=s.onus_with_cross_olt_zone,
                        message=(
                            f"{s.onus_with_cross_olt_zone} ONUs apuntan a Zones de "
                            "otra OLT, violando la regla de aislamiento territorial."
                        ),
                        recommendation=(
                            "Usar el preview de Zones por OLT para reasignar estas ONUs "
                            "a Zones propias de la OLT antes de cualquier apply."
                        ),
                    )
                )

            if s.onus_with_cross_olt_nap > 0:
                issues.append(
                    TerritorialAuditIssue(
                        issue_type="CROSS_OLT_NAP",
                        severity="CRITICAL",
                        olt_id=olt_id,
                        olt_code=s.olt_code,
                        entity_type="ONU",
                        entity_name="*",
                        affected_onu_count=s.onus_with_cross_olt_nap,
                        message=(
                            f"{s.onus_with_cross_olt_nap} ONUs apuntan a NAP/ODN/ODB "
                            "de otra OLT, violando la regla de aislamiento territorial."
                        ),
                        recommendation=(
                            "Usar el preview de NAP/ODN/ODB por OLT para reasignar "
                            "estas ONUs a NAPs propios de la OLT."
                        ),
                    )
                )

        # 2) NAP/ODN/ODB en REVIEW/BLOCKED (a nivel de catálogo).
        review_or_blocked = [
            c for c in naps_preview.catalog_proposals if c.state in {"REVIEW", "BLOCKED"}
        ]
        for c in review_or_blocked:
            issues.append(
                TerritorialAuditIssue(
                    issue_type="NAP_REVIEW_OR_BLOCKED",
                    severity="MEDIUM" if c.state == "REVIEW" else "HIGH",
                    olt_id=c.olt_id,
                    olt_code=c.olt_code,
                    entity_type=c.object_type,
                    entity_name=c.canonical_name,
                    affected_onu_count=c.onu_count,
                    message=(
                        f"Candidato {c.object_type} {c.canonical_name} en estado "
                        f"{c.state} con {c.onu_count} ONUs asociadas."
                    ),
                    recommendation=(
                        "Revisar manualmente candidatos territoriales en estados "
                        "REVIEW/BLOCKED antes de consolidar el catálogo."
                    ),
                )
            )

        return issues

    @staticmethod
    def _build_recommendations(issues: Iterable[TerritorialAuditIssue]) -> List[str]:
        """Genera recomendaciones de alto nivel a partir de los issues."""

        recs: List[str] = []
        issue_types = {i.issue_type for i in issues}
        has_blocked_or_review_naps = any(
            i.issue_type == "NAP_REVIEW_OR_BLOCKED" for i in issues
        )

        # Ejemplos de recomendaciones globales.
        if "CROSS_OLT_ZONE" in issue_types:
            recs.append(
                "Reasignar ONUs con Zones cruzadas usando Zones propias de cada OLT, "
                "empezando por OLT-PCM-ZTE-01."
            )
        if "CROSS_OLT_NAP" in issue_types:
            recs.append(
                "Reconstruir y utilizar catálogos NAP/ODN/ODB propios por OLT antes de "
                "tocar planes de provisión heredados."
            )
        if "NO_ZONES" in issue_types:
            recs.append(
                "Para OLT-PCM-ZTE-01 se recomienda crear explícitamente una Zone "
                '"Lagunas" propia (Zone Lagunas para OLT-PCM-ZTE-01).'
            )
        if "NO_NAPS" in issue_types:
            recs.append(
                "Reconstruir el catálogo NAP/ODN/ODB para OLT-PCM-ZTE-01 a partir de "
                "las descripciones de ONU y evidencias históricas."
            )
        if has_blocked_or_review_naps:
            recs.append(
                "Revisar manualmente todos los objetos territoriales en estado "
                "REVIEW o BLOCKED antes de confirmar catálogos."
            )
            recs.append(
                "No ejecutar apply de reconstrucción territorial hasta resolver "
                "los candidatos marcados como BLOCKED/REVIEW."
            )

        # Eliminar duplicados preservando orden.
        seen = set()
        unique_recs: List[str] = []
        for r in recs:
            if r in seen:
                continue
            seen.add(r)
            unique_recs.append(r)

        return unique_recs


__all__ = ["TerritorialAuditCenterService"]
