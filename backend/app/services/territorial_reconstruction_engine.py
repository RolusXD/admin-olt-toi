from __future__ import annotations

"""Territorial Reconstruction Engine (TRE) – Infraestructura genérica P4.

Este módulo define la **arquitectura reutilizable** del motor central de
reconstrucción territorial sin aplicar aún ningún algoritmo concreto de
P4.2/P4.3 ni tocar la BD.

Importante (alineado con las EFO de Gobierno de Catálogos y Modelo
Territorial FTTH, y con las restricciones de esta tarea):

- **Sin efectos laterales**: el TRE trabaja únicamente en memoria sobre
  colecciones de entidades y propuestas ya cargadas; no ejecuta
  ``INSERT/UPDATE/DELETE`` ni ``commit``.
- **Sin endpoints ni Apply**: este módulo no expone rutas HTTP ni
  flujos de apply; se limita a ofrecer un núcleo reutilizable para
  servicios de *preview* (p.ej. Zones, NAP/ODN/ODB, NapPorts).
- **Sin parsers ni importaciones nuevas**: consume evidencias ya
  calculadas por parsers/documentos (por ejemplo, `parsed_nap_name`,
  `parsed_odn`, `odb_name`, snapshots) sin invocar Telnet ni reparsear
  running-config.
- **Reutilizable por dominio territorial**: el mismo motor puede servir
  para `Zone`, `Nap` (incluyendo NAP/ODN/ODB), `NapPort` y, en futuras
  fases, para candidatos derivados de `ProvisioningPlan` o topologías
  GIS, sin duplicar lógica de evaluación de confianza ni detección de
  conflictos.

La implementación actual cubre sólo la **infraestructura genérica**:

- DTOs internos para representar **candidatos territoriales** y su
  estado.
- Contratos de:
  - ``TerritorialCandidate``
  - ``ConfidenceEvaluator``
  - ``ConflictDetector``
  - ``ReportGenerator``
- Un ``TerritorialReconstructionEngine`` parametrizable que orquesta
  estos componentes.

No se conectan todavía fuentes reales de datos P4.2/P4.3; eso quedará
para fases posteriores (P4.2 – NAP/ODN/ODB, P4.3 – NapPorts, P4.4 –
reasignación ONU/ProvisioningPlan).
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Generic, Iterable, List, Optional, Protocol, Sequence, Tuple, TypeVar


class TerritorialCandidateState(str, Enum):
    """Estados genéricos para candidatos territoriales.

    Los estados están pensados para ser estables y reutilizables en
    todos los dominios territoriales (Zones, NAP/ODN/ODB, NapPorts,
    NapPorts ↔ ONU), tanto en P4.2/P4.3 como en fases posteriores.

    - ``NEW``: candidato que no existe todavía en el catálogo de la OLT.
    - ``EXISTS``: corresponde a una entidad ya materializada en BD.
    - ``REVIEW``: requiere revisión humana antes de poder consolidarse.
    - ``BLOCKED``: el sistema no puede proponer una acción automática
      (ambigüedad irresoluble, evidencia contradictoria, violación de
      invariantes de las EFO).
    - ``MERGE``: candidato que sugiere fusionar/conciliar varias
      representaciones históricas/documentales en una identidad
      territorial canónica.
    """

    NEW = "NEW"
    EXISTS = "EXISTS"
    REVIEW = "REVIEW"
    BLOCKED = "BLOCKED"
    MERGE = "MERGE"


@dataclass
class TerritorialEvidence:
    """Evidencia que respalda un candidato territorial.

    No representa entidades de BD; es un contenedor ligero de pistas
    técnicas y documentales (p.ej. descripciones ONU, registros
    SmartOLT, snapshots, frecuencia de aparición) con un ``weight``
    relativo que puede usarse para construir ``evidence_score``.
    """

    source: str
    """Identidad lógica de la fuente (ej.: ``"onu_description"``,
    ``"parsed_nap_name"``, ``"smartolt_export"``, ``"existing_catalog"``)."""

    description: str
    """Resumen humano legible de la evidencia."""

    weight: float = 1.0
    """Peso relativo (>= 0). No es un porcentaje; sirve como insumo para
    calculadoras de confianza específicas por dominio/OLT."""

    metadata: Dict[str, Any] = field(default_factory=dict)
    """Metadatos arbitrarios (ej.: ids de ONUs implicadas, snapshot,
    flags de ambigüedad, prefijos `NAP`/`ODN`/`ODB`, etc.)."""


TId = TypeVar("TId")
TRaw = TypeVar("TRaw")


@dataclass
class TerritorialCandidate(Generic[TId, TRaw]):
    """Candidato territorial genérico.

    Este DTO interno es independiente de las tablas concretas. Permite
    que un mismo motor se aplique a diferentes dominios, por ejemplo:

    - Candidatos de Zone por OLT.
    - Candidatos de Nap/ODN/ODB por OLT y Zone.
    - Candidatos de NapPort por Nap/ODN/ODB.
    - Candidatos de reasignación ONU ↔ Zone/Nap/NapPort.
    """

    candidate_id: Optional[TId]
    """Identificador interno opcional.

    - ``None`` cuando el candidato aún no corresponde a una entidad
      persistida (caso típico ``NEW``).
    - Un id interno cuando se trata de una posible actualización o
      conciliación respecto de un registro existente.
    """

    key: str
    """Clave territorial lógica en el dominio correspondiente.

    Ejemplos:

    - Zone: ``"OLT-PCM-ZTE-01|Lagunas"``.
    - Nap/ODN/ODB: ``"olt=3|type=ODN|canonical_name=ODN H5"``.
    - NapPort: ``"olt=3|nap_id=42|port=9"``.
    """

    state: TerritorialCandidateState

    evidence_score: int
    """Puntaje 0–100 de confianza agregada.

    Este valor no se calcula en el DTO; lo aportan los evaluadores de
    confianza reutilizables por dominio. Se mantiene como entero para
    facilitar su exposición posterior en APIs de sólo lectura.
    """

    evidence: List[TerritorialEvidence] = field(default_factory=list)
    """Evidencias que respaldan este candidato."""

    conflicts: List[str] = field(default_factory=list)
    """Descripción textual de conflictos potenciales detectados para el
    candidato (ej.: colisión NAP/ODN, cruce entre OLTs, violaciones de
    invariantes territoriales)."""

    payload: Optional[TRaw] = None
    """Carga útil específica del dominio.

    Por ejemplo, un *snapshot* estructurado con:

    - Campos conceptuales de ``Zone``/``Nap``/``NapPort``.
    - Resumen de ONUs impactadas.
    - Estadísticas auxiliares.
    """


class ConfidenceEvaluator(Protocol[TRaw]):
    """Calcula puntajes de confianza y propone estados para candidatos.

    Implementaciones específicas se encargarán de mapear las reglas de
    cada EFO a un rango 0–100 y a un estado sugerido (`NEW`, `EXISTS`,
    `REVIEW`, `BLOCKED`, `MERGE`). Este contrato permite reutilizar la
    misma infraestructura del TRE para:

    - P4.1: evaluación de confianza por Zone (ya implementado fuera del
      TRE en ``ZoneReconstructionPreviewService``).
    - P4.2: candidatos Nap/ODN/ODB por OLT/Zone.
    - P4.3: candidatos NapPort por Nap/ODN/ODB.
    - P4.4: reasignaciones ONU/ProvisioningPlan.
    """

    def evaluate(self, raw: TRaw, evidences: Sequence[TerritorialEvidence]) -> Tuple[int, TerritorialCandidateState]:  # pragma: no cover - contrato
        """Devuelve ``(evidence_score, state_sugerido)`` para una carga útil.

        - ``evidence_score`` debe estar en el rango 0–100.
        - ``state`` debe ser uno de los valores de
          :class:`TerritorialCandidateState`.
        """


class ConflictDetector(Protocol[TId, TRaw]):
    """Detecta conflictos entre candidatos territoriales.

    Ejemplos de conflictos que pueden detectarse dependiendo del dominio:

    - Identidades incompatibles entre NAP/ODN/ODB (``NAP D4`` vs
      ``ODN D4`` compartiendo misma evidencia).
    - Cruces territoriales entre OLTs (violando las invariantes de las
      EFO).
    - Solapamientos de puertos de NapPort con diferentes ONUs.
    """

    def detect(self, candidates: Sequence[TerritorialCandidate[TId, TRaw]]) -> None:  # pragma: no cover - contrato
        """Anota los candidatos en sitio, rellenando su lista
        ``conflicts`` cuando proceda.

        La implementación no debe mutar campos ajenos a ``conflicts``.
        """


class ReportGenerator(Protocol[TId, TRaw]):
    """Generador de reportes de alto nivel a partir de candidatos.

    Un mismo conjunto de candidatos puede proyectarse a distintos tipos
    de reportes (por OLT, por zona, por tipo NAP/ODN/ODB, por nivel de
    confianza, por estado). Este contrato mantiene desacoplada la
    construcción de reportes de la lógica central del TRE.
    """

    def build_summary(self, candidates: Sequence[TerritorialCandidate[TId, TRaw]]) -> Dict[str, Any]:  # pragma: no cover - contrato
        """Devuelve un diccionario estructurado de resumen.

        El contenido concreto queda a criterio de cada implementación
        (ej.: histogramas por ``evidence_score``, conteos por estado,
        estadísticas por OLT/Zone/Nap)."""

    def build_detailed(self, candidates: Sequence[TerritorialCandidate[TId, TRaw]]) -> Dict[str, Any]:  # pragma: no cover - contrato
        """Devuelve una vista detallada (por ejemplo, una lista de
        candidatos serializable a un esquema Pydantic de sólo lectura)."""


TReport = TypeVar("TReport")


class TerritorialReconstructionEngine(Generic[TId, TRaw, TReport]):
    """Motor genérico de reconstrucción territorial.

    Orquesta la construcción de candidatos territoriales a partir de
    datos de entrada (ONUs, catálogos existentes, snapshots externos),
    delegando en componentes externos la evaluación de confianza, la
    detección de conflictos y la generación de reportes.

    Este motor no depende de SQLAlchemy ni de los modelos concretos; es
    reutilizable tanto en servicios de backend como, en el futuro, en
    herramientas offline o scripts de auditoría.
    """

    def __init__(
        self,
        *,
        confidence_evaluator: ConfidenceEvaluator[TRaw],
        conflict_detector: Optional[ConflictDetector[TId, TRaw]] = None,
        report_generator: Optional[ReportGenerator[TId, TRaw]] = None,
    ) -> None:
        self._confidence_evaluator = confidence_evaluator
        self._conflict_detector = conflict_detector
        self._report_generator = report_generator

    # Construcción de candidatos -------------------------------------------------

    def build_candidates(
        self,
        items: Iterable[Tuple[Optional[TId], str, TRaw, Sequence[TerritorialEvidence]]],
    ) -> List[TerritorialCandidate[TId, TRaw]]:
        """Construye candidatos a partir de una secuencia de insumos.

        Cada elemento de ``items`` es una tupla:

        - ``existing_id``: id de entidad existente o ``None``.
        - ``key``: clave territorial lógica.
        - ``raw``: carga útil específica del dominio (datos agregados de
          Zone/Nap/NapPort/ONU, etc.).
        - ``evidences``: lista de :class:`TerritorialEvidence`.
        """

        candidates: List[TerritorialCandidate[TId, TRaw]] = []

        for existing_id, key, raw, evidences in items:
            score, state = self._confidence_evaluator.evaluate(raw, evidences)

            # Garantizar rango 0–100 y estado válido incluso si una
            # implementación comete un error leve.
            score = max(0, min(int(score), 100))
            if state not in TerritorialCandidateState.__members__.values():
                # Fallback conservador.
                state = TerritorialCandidateState.REVIEW

            candidate = TerritorialCandidate[TId, TRaw](
                candidate_id=existing_id,
                key=key,
                state=state,
                evidence_score=score,
                evidence=list(evidences),
                conflicts=[],
                payload=raw,
            )
            candidates.append(candidate)

        # Detección de conflictos opcional.
        if self._conflict_detector and candidates:
            self._conflict_detector.detect(candidates)

        return candidates

    # Generación de reportes -----------------------------------------------------

    def generate_report(
        self,
        candidates: Sequence[TerritorialCandidate[TId, TRaw]],
    ) -> Optional[TReport]:
        """Proyecta los candidatos a un reporte estructurado.

        Si no se ha proporcionado un ``ReportGenerator``, devuelve
        ``None``. En caso contrario, delega en el generador para
        construir una estructura arbitraria que después pueda mapearse a
        DTOs Pydantic de solo lectura o exportarse a otros formatos.
        """

        if not self._report_generator:
            return None

        summary = self._report_generator.build_summary(candidates)
        detailed = self._report_generator.build_detailed(candidates)
        return {"summary": summary, "details": detailed}  # type: ignore[return-value]


__all__ = [
    "TerritorialCandidateState",
    "TerritorialEvidence",
    "TerritorialCandidate",
    "ConfidenceEvaluator",
    "ConflictDetector",
    "ReportGenerator",
    "TerritorialReconstructionEngine",
]
