from __future__ import annotations

"""Preview de reconstrucción de NAP/ODN/ODB por OLT (Fase P4.3).

Este servicio implementa un flujo **de solo lectura** que:

- Lee OLTs, Zones, NAPs y ONUs desde la BD.
- Usa `TerritorialNormalizer` para obtener identidades territoriales
  canónicas (NAP/ODN/ODB) a partir de `parsed_nap_name`, `parsed_odn`
  y `odb_name`, preservando prefijos según las EFO.
- Construye candidatos territoriales mediante el
  `TerritorialReconstructionEngine` (TRE) a partir de evidencias por
  ONU.
- Produce un `NapReconstructionPreview` con:
  - Resumen por OLT (`NapReconstructionOltSummary`).
  - Catálogo consolidado de candidatos (`NapReconstructionCatalogProposal`).
  - Matriz ONU actual vs propuesta (`NapReconstructionOnuProposal`).

No realiza ningún cambio persistente (`no INSERT/UPDATE/DELETE`, sin
`commit`) y no expone endpoints ni flujos de apply.
"""

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import Nap, Olt, Onu, Zone
from app.schemas.entities import (
    NapReconstructionCatalogProposal,
    NapReconstructionOltSummary,
    NapReconstructionOnuProposal,
    NapReconstructionPreview,
)
from app.services.territorial_identity import (
    TerritorialIdentity,
    TerritorialNormalizer,
    TerritorialObjectType,
)
from app.services.territorial_reconstruction_engine import (
    ConfidenceEvaluator,
    TerritorialCandidate,
    TerritorialCandidateState,
    TerritorialEvidence,
    TerritorialReconstructionEngine,
)


@dataclass
class NapCandidatePayload:
    """Carga útil de candidato NAP/ODN/ODB para el TRE.

    Representa un candidato consolidado por (OLT, zona, tipo, nombre
    canónico) agregando todas las ONUs que lo respaldan.
    """

    olt_id: int
    zone_name: Optional[str]
    identity: TerritorialIdentity
    existing_nap_id: Optional[int]
    existing_nap_display_name: Optional[str]
    supporting_onu_ids: List[int] = field(default_factory=list)
    source_fields: List[str] = field(default_factory=list)
    has_cross_olt_nap: bool = False


class NapConfidenceEvaluator(ConfidenceEvaluator[NapCandidatePayload]):
    """Evaluador de confianza para candidatos NAP/ODN/ODB.

    Combina `identity.identity_score` con el número de ONUs que
    respaldan el candidato y con las razones de identidad para producir
    un `evidence_score` agregado y un `TerritorialCandidateState`.
    """

    def evaluate(
        self,
        raw: NapCandidatePayload,
        evidences: Sequence[TerritorialEvidence],
    ) -> Tuple[int, TerritorialCandidateState]:
        identity = raw.identity
        base = identity.identity_score
        onu_count = max(1, len(raw.supporting_onu_ids))

        # Ajustes básicos según tipo de evidencia.
        score = base

        explicit_prefix = "explicit_prefix" in identity.reasons
        default_type_applied = "default_type_applied" in identity.reasons

        if explicit_prefix:
            if onu_count >= 2 and raw.zone_name:
                # Prefijo explícito + zona clara + varias ONUs.
                score = min(100, base + 5)
            elif onu_count == 1:
                # Prefijo explícito pero sólo una ONU.
                score = max(80, base - 5)
        elif default_type_applied:
            # Prefijo inferido a partir de default_type.
            score = min(base, 75)
        else:
            # Otros casos ambiguos.
            score = min(base, 80)

        score = max(0, min(int(score), 100))

        # Estado sugerido.
        if score == 0:
            state = TerritorialCandidateState.BLOCKED
        elif raw.existing_nap_id is not None and score >= 75:
            state = TerritorialCandidateState.EXISTS
        elif default_type_applied or score < 75:
            state = TerritorialCandidateState.REVIEW
        else:
            state = TerritorialCandidateState.NEW

        return score, state


class NapReconstructionPreviewService:
    """Servicio de auditoría para preview de NAP/ODN/ODB por OLT (P4.3).

    Importante:
    - **Solo lectura**: no crea ni modifica entidades; sólo realiza
      consultas y cálculos en memoria.
    - No accede a OLTs reales ni reejecuta parsers; se apoya en el
      estado actual de `Onu`, `Nap` y `Zone` persistido desde snapshots
      confirmados.
    """

    def __init__(self, db: Session):
        self.db = db
        self._normalizer = TerritorialNormalizer()

    # API principal -----------------------------------------------------

    def preview(self) -> NapReconstructionPreview:
        """Calcula la preview completa de NAP/ODN/ODB por OLT.

        Devuelve un ``NapReconstructionPreview`` con resúmenes por OLT,
        catálogo propuesto y matriz ONU actual vs propuesta.
        """

        olts: list[Olt] = list(self.db.scalars(select(Olt)))
        zones: list[Zone] = list(self.db.scalars(select(Zone)))
        naps: list[Nap] = list(self.db.scalars(select(Nap)))
        onus: list[Onu] = list(self.db.scalars(select(Onu)))

        olt_by_id: Dict[int, Olt] = {o.id: o for o in olts}
        zone_by_id: Dict[int, Zone] = {z.id: z for z in zones}
        nap_by_id: Dict[int, Nap] = {n.id: n for n in naps}

        existing_naps_by_olt: Dict[int, List[str]] = {}
        canonical_to_nap_id: Dict[Tuple[int, str], int] = {}

        for nap in naps:
            if nap.olt_id is None:
                continue
            canonical = self._canonical_from_nap(nap)
            existing_naps_by_olt.setdefault(nap.olt_id, []).append(canonical)
            canonical_to_nap_id[(nap.olt_id, canonical)] = nap.id

        # Construir payloads de candidatos por (olt_id, zone_name, object_type, canonical_name).
        candidate_payloads: Dict[
            Tuple[int, Optional[str], str, str], NapCandidatePayload
        ] = {}

        # Primer pase: construir filas ONU con contexto básico y agrupar evidencia.
        onu_rows: list[NapReconstructionOnuProposal] = []

        for onu in onus:
            olt = olt_by_id.get(onu.olt_id)
            if not olt:
                # Sin OLT no se puede proponer nada razonable.
                row = NapReconstructionOnuProposal(
                    onu_id=onu.id,
                    olt_id=onu.olt_id,
                    olt_code=None,
                    interface=onu.onu_interface,
                    serial=onu.serial_number,
                    customer_name=onu.customer_name,
                    current_nap_id=onu.nap_id,
                    current_nap_name=None,
                    current_nap_olt_id=None,
                    current_nap_olt_code=None,
                    parsed_nap_name=onu.parsed_nap_name,
                    parsed_odn=onu.parsed_odn,
                    odb_name=onu.odb_name,
                    proposed_zone_name=None,
                    proposed_object_type=None,
                    proposed_canonical_name=None,
                    proposed_olt_id=None,
                    state=TerritorialCandidateState.BLOCKED.value,
                    confidence="BLOQUEADO",
                    identity_score=0,
                    evidence_score=0,
                    reasons=["missing_olt_for_onu"],
                )
                onu_rows.append(row)
                continue

            current_nap = nap_by_id.get(onu.nap_id) if onu.nap_id else None
            current_nap_olt_id = current_nap.olt_id if current_nap else None
            cross_olt_nap = bool(
                current_nap
                and current_nap.olt_id is not None
                and current_nap.olt_id != onu.olt_id
            )

            # Determinar zona propuesta (sólo como nombre lógico).
            proposed_zone_name = self._select_zone_name_for_onu(onu)

            # Determinar mejor fuente de identidad territorial.
            identity, source, source_field = self._build_identity_for_onu(onu)

            if identity is None:
                # Sin identidad territorial → ONU bloqueada para este preview.
                reasons = ["no_nap_evidence"]
                if cross_olt_nap:
                    reasons.append("cross_olt_nap_detected")

                row = NapReconstructionOnuProposal(
                    onu_id=onu.id,
                    olt_id=onu.olt_id,
                    olt_code=olt.olt_code,
                    interface=onu.onu_interface,
                    serial=onu.serial_number,
                    customer_name=onu.customer_name,
                    current_nap_id=onu.nap_id,
                    current_nap_name=current_nap.name if current_nap else None,
                    current_nap_olt_id=current_nap_olt_id,
                    current_nap_olt_code=olt_by_id.get(current_nap_olt_id).olt_code
                    if current_nap_olt_id in olt_by_id
                    else None,
                    parsed_nap_name=onu.parsed_nap_name,
                    parsed_odn=onu.parsed_odn,
                    odb_name=onu.odb_name,
                    proposed_zone_name=proposed_zone_name,
                    proposed_object_type=None,
                    proposed_canonical_name=None,
                    proposed_olt_id=None,
                    state=TerritorialCandidateState.BLOCKED.value,
                    confidence="BLOQUEADO",
                    identity_score=0,
                    evidence_score=0,
                    reasons=reasons,
                )
                onu_rows.append(row)
                continue

            # Determinar si ya existe en catálogo de esta OLT.
            canonical = identity.canonical_name
            existing_nap_id = canonical_to_nap_id.get((onu.olt_id, canonical))
            existing_nap = nap_by_id.get(existing_nap_id) if existing_nap_id else None

            key = (onu.olt_id, proposed_zone_name, identity.object_type.value, canonical)
            payload = candidate_payloads.get(key)
            if not payload:
                payload = NapCandidatePayload(
                    olt_id=onu.olt_id,
                    zone_name=proposed_zone_name,
                    identity=identity,
                    existing_nap_id=existing_nap_id,
                    existing_nap_display_name=existing_nap.name if existing_nap else None,
                )
                candidate_payloads[key] = payload

            payload.supporting_onu_ids.append(onu.id)
            if source_field not in payload.source_fields:
                payload.source_fields.append(source_field)
            if cross_olt_nap:
                payload.has_cross_olt_nap = True

            onu_rows.append(
                NapReconstructionOnuProposal(
                    onu_id=onu.id,
                    olt_id=onu.olt_id,
                    olt_code=olt.olt_code,
                    interface=onu.onu_interface,
                    serial=onu.serial_number,
                    customer_name=onu.customer_name,
                    current_nap_id=onu.nap_id,
                    current_nap_name=current_nap.name if current_nap else None,
                    current_nap_olt_id=current_nap_olt_id,
                    current_nap_olt_code=olt_by_id.get(current_nap_olt_id).olt_code
                    if current_nap_olt_id in olt_by_id
                    else None,
                    parsed_nap_name=onu.parsed_nap_name,
                    parsed_odn=onu.parsed_odn,
                    odb_name=onu.odb_name,
                    proposed_zone_name=proposed_zone_name,
                    proposed_object_type=identity.object_type.value,
                    proposed_canonical_name=canonical,
                    proposed_olt_id=onu.olt_id,
                    state="PENDING",  # Se rellenará tras evaluar candidatos.
                    confidence="PENDING",
                    identity_score=identity.identity_score,
                    evidence_score=0,
                    reasons=[source],
                )
            )

        # Construir evidencias para el TRE a nivel de candidato.
        tre_items: List[
            Tuple[Optional[int], str, NapCandidatePayload, Sequence[TerritorialEvidence]]
        ] = []

        for (olt_id, zone_name, obj_type, canonical), payload in candidate_payloads.items():
            evidences: List[TerritorialEvidence] = []
            for source_field in payload.source_fields:
                evidences.append(
                    TerritorialEvidence(
                        source=source_field,
                        description=f"from_{source_field}",
                        weight=1.0,
                        metadata={
                            "olt_id": olt_id,
                            "zone_name": zone_name,
                            "canonical_name": payload.identity.canonical_name,
                            "object_type": obj_type,
                        },
                    )
                )

            key = f"olt={olt_id}|zone={zone_name}|type={obj_type}|name={canonical}"
            tre_items.append((payload.existing_nap_id, key, payload, evidences))

        # Ejecutar TRE.
        engine: TerritorialReconstructionEngine[
            int, NapCandidatePayload, Dict[str, object]
        ] = TerritorialReconstructionEngine[
            int, NapCandidatePayload, Dict[str, object]
        ](confidence_evaluator=NapConfidenceEvaluator())

        candidates = engine.build_candidates(tre_items)
        candidate_by_key: Dict[str, TerritorialCandidate[int, NapCandidatePayload]] = {
            c.key: c for c in candidates
        }

        # Construir propuestas de catálogo a partir de los candidatos.
        catalog_proposals: list[NapReconstructionCatalogProposal] = []

        for (olt_id, zone_name, obj_type, canonical), payload in candidate_payloads.items():
            key = f"olt={olt_id}|zone={zone_name}|type={obj_type}|name={canonical}"
            candidate = candidate_by_key.get(key)
            if not candidate:
                continue

            olt = olt_by_id.get(olt_id)
            if not olt:
                continue

            exists_in_olt = payload.existing_nap_id is not None

            confidence_label = self._confidence_label(candidate.evidence_score)

            reasons: List[str] = list(payload.identity.reasons)
            if exists_in_olt:
                reasons.append("nap_exists_in_olt")
            else:
                reasons.append("nap_missing_in_olt")
            if payload.has_cross_olt_nap:
                reasons.append("affected_by_cross_olt_nap")

            catalog_proposals.append(
                NapReconstructionCatalogProposal(
                    olt_id=olt.id,
                    olt_code=olt.olt_code,
                    olt_name=olt.name,
                    proposed_zone_name=zone_name,
                    object_type=obj_type,
                    canonical_name=payload.identity.canonical_name,
                    display_name=payload.identity.display_name,
                    code=payload.identity.code,
                    notes=payload.identity.notes,
                    exists_in_olt=exists_in_olt,
                    existing_nap_id=payload.existing_nap_id,
                    onu_count=len(payload.supporting_onu_ids),
                    identity_score=payload.identity.identity_score,
                    evidence_score=candidate.evidence_score,
                    state=candidate.state.value,
                    confidence=confidence_label,
                    reasons=reasons,
                    source_fields=list(payload.source_fields),
                    supporting_onu_ids=list(payload.supporting_onu_ids),
                )
            )

        # Rellenar estado/confianza/evidence_score en filas ONU.
        key_to_candidate = candidate_by_key
        for row in onu_rows:
            if not row.proposed_canonical_name or not row.proposed_object_type:
                # Bloqueados ya configurados.
                continue
            key = (
                row.olt_id,
                row.proposed_zone_name,
                row.proposed_object_type,
                row.proposed_canonical_name,
            )
            tre_key = (
                f"olt={key[0]}|zone={key[1]}|type={key[2]}|name={key[3]}"
            )
            candidate = key_to_candidate.get(tre_key)
            if not candidate:
                continue

            row.state = candidate.state.value
            row.evidence_score = candidate.evidence_score
            row.confidence = self._confidence_label(candidate.evidence_score)
            row.identity_score = candidate.payload.identity.identity_score

        # Construir resúmenes por OLT.
        summaries_by_olt: Dict[int, NapReconstructionOltSummary] = {}

        for olt in olts:
            existing = sorted(set(existing_naps_by_olt.get(olt.id, [])))
            summaries_by_olt[olt.id] = NapReconstructionOltSummary(
                olt_id=olt.id,
                olt_code=olt.olt_code,
                olt_name=olt.name,
                total_onus=0,
                existing_naps=existing,
                proposed_catalog_count=0,
                proposed_new_count=0,
                proposed_exists_count=0,
                proposed_review_count=0,
                proposed_blocked_count=0,
                onus_with_nap_id=0,
                onus_with_cross_olt_nap=0,
                onus_without_nap_id=0,
                onus_reassignable=0,
                onus_blocked=0,
            )

        # Contabilizar por ONU.
        for row in onu_rows:
            summary = summaries_by_olt.get(row.olt_id)
            if not summary:
                continue
            summary.total_onus += 1

            if row.current_nap_id:
                summary.onus_with_nap_id += 1
                if (
                    row.current_nap_olt_id is not None
                    and row.current_nap_olt_id != row.olt_id
                ):
                    summary.onus_with_cross_olt_nap += 1
            else:
                summary.onus_without_nap_id += 1

            if row.state == TerritorialCandidateState.BLOCKED.value:
                summary.onus_blocked += 1
            else:
                # Reasignable si no tiene nap_id, o si está cruzado, o si el
                # canónico propuesto no coincide con el actual (cuando exista).
                current_canonical = None
                if row.current_nap_name and row.current_nap_olt_id == row.olt_id:
                    current_canonical = row.current_nap_name

                if (
                    not row.current_nap_id
                    or (
                        row.current_nap_olt_id is not None
                        and row.current_nap_olt_id != row.olt_id
                    )
                    or (
                        current_canonical
                        and row.proposed_canonical_name
                        and current_canonical.upper()
                        != row.proposed_canonical_name.upper()
                    )
                ):
                    summary.onus_reassignable += 1

        # Contabilizar propuestas de catálogo.
        for proposal in catalog_proposals:
            summary = summaries_by_olt.get(proposal.olt_id)
            if not summary:
                continue
            summary.proposed_catalog_count += 1
            if proposal.state == TerritorialCandidateState.NEW.value:
                summary.proposed_new_count += 1
            elif proposal.state == TerritorialCandidateState.EXISTS.value:
                summary.proposed_exists_count += 1
            elif proposal.state == TerritorialCandidateState.REVIEW.value:
                summary.proposed_review_count += 1
            elif proposal.state == TerritorialCandidateState.BLOCKED.value:
                summary.proposed_blocked_count += 1

        ordered_summaries = sorted(
            summaries_by_olt.values(), key=lambda s: (s.olt_code)
        )

        return NapReconstructionPreview(
            summaries=ordered_summaries,
            catalog_proposals=catalog_proposals,
            onus=onu_rows,
        )

    # --------------------------- Helpers -------------------------------

    @staticmethod
    def _canonical_from_nap(nap: Nap) -> str:
        """Construye un nombre canónico a partir de una fila Nap.

        Usa `nap_type` + `code` o, en su defecto, `name`.
        """

        code = nap.code or nap.name or ""
        prefix = nap.nap_type or "NAP"
        canonical = f"{prefix} {code}".strip()
        return canonical.upper()

    @staticmethod
    def _select_zone_name_for_onu(onu: Onu) -> Optional[str]:
        """Selecciona el mejor nombre de zona disponible para una ONU.

        Prioridad:
        - `parsed_zone_name` cuando exista y no sea `SIN_ZONA`.
        - `zone_name` en su defecto.
        """

        for candidate in (onu.parsed_zone_name, onu.zone_name):
            if candidate:
                value = candidate.strip()
                if value and value.upper() != "SIN_ZONA":
                    return value
        return None

    def _build_identity_for_onu(
        self, onu: Onu
    ) -> Tuple[Optional[TerritorialIdentity], str, str]:
        """Construye la mejor identidad territorial disponible para una ONU.

        Prioridad de fuentes (A–C):
        A) `parsed_odn` / `odb_name` con prefijo explícito.
        B) `parsed_nap_name` con prefijo explícito.
        C) `parsed_nap_name` sin prefijo usando `default_type=NAP`.
        """

        # A) parsed_odn / odb_name
        for field_name in ("parsed_odn", "odb_name"):
            raw = getattr(onu, field_name, None)
            if raw:
                identity = self._normalizer.normalize_territorial_object(
                    raw, olt_id=onu.olt_id
                )
                if identity is not None:
                    return identity, f"from_{field_name}", field_name

        # B/C) parsed_nap_name
        if onu.parsed_nap_name:
            # Primero intentar con prefijo explícito.
            identity = self._normalizer.normalize_territorial_object(
                onu.parsed_nap_name, olt_id=onu.olt_id
            )
            if identity is not None:
                return identity, "from_parsed_nap_name", "parsed_nap_name"

            # Sin prefijo: permitir default_type=NAP, marcando menor confianza.
            identity = self._normalizer.normalize_territorial_object(
                onu.parsed_nap_name,
                olt_id=onu.olt_id,
                default_type=TerritorialObjectType.NAP,
            )
            if identity is not None:
                return identity, "from_parsed_nap_name", "parsed_nap_name"

        return None, "no_nap_evidence", ""

    @staticmethod
    def _confidence_label(evidence_score: int) -> str:
        if evidence_score >= 90:
            return "ALTA"
        if evidence_score >= 75:
            return "MEDIA"
        if evidence_score >= 50:
            return "BAJA"
        return "BLOQUEADO"


__all__ = ["NapReconstructionPreviewService"]
