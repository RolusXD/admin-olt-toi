from __future__ import annotations

"""Infraestructura de identidad territorial para el TRE (P4.2).

Este módulo define una capa reutilizable de **identidad territorial**
independiente de SQLAlchemy y de servicios concretos. Su objetivo es:

- Centralizar la normalización de nombres territoriales (NAP/ODN/ODB,
  NapPorts y, en menor medida, Zones).
- Preservar la identidad canónica con prefijos (`NAP`/`ODN`/`ODB`)
  según las EFO de Calidad de Datos y Normalización de Modelo ONU.
- Evitar que la lógica de parsing documental de nombres territoriales
  quede duplicada en múltiples servicios de P4.x.

La salida principal es :class:`TerritorialIdentity`, un DTO inmutable
con `identity_score` y `reasons` explícitas que puede usarse como
insumo para el Territorial Reconstruction Engine (TRE).

Importante:
- No accede a BD ni a OLTs reales.
- No modifica entidades persistidas.
- No reemplaza parsers existentes; actúa sobre valores de texto ya
  extraídos (por ejemplo, `parsed_nap_name`, `parsed_odn`, `odb_name`).
"""

from dataclasses import dataclass, field
from enum import Enum
import re
from typing import List, Optional


class TerritorialObjectType(str, Enum):
    """Tipos lógicos de objetos territoriales.

    Se usan para distinguir entre zonas, elementos de planta externa y
    puertos NAP dentro de una misma OLT.
    """

    ZONE = "ZONE"
    NAP = "NAP"
    ODN = "ODN"
    ODB = "ODB"
    NAP_PORT = "NAP_PORT"


@dataclass(frozen=True)
class TerritorialIdentity:
    """Identidad territorial normalizada (DTO inmutable).

    No representa una fila de BD, sino una interpretación canónica de
    un valor textual territorial para una OLT concreta.
    """

    olt_id: int
    zone_name: Optional[str]
    object_type: TerritorialObjectType

    code: str
    """Código territorial tras el prefijo (ej.: ``"H5"``, ``"C4 A"``, ``"D4"``)."""

    canonical_name: str
    """Nombre canónico completo, incluyendo siempre el prefijo cuando
    aplica (ej.: ``"ODN H5"``, ``"NAP D4"``)."""

    display_name: str
    """Valor textual tal como fue recibido (trimeado)."""

    notes: Optional[str]
    """Texto documental posterior al identificador canónico (cuando
    procede), por ejemplo descripciones largas heredadas."""

    identity_score: int
    """Puntaje 0–100 de confianza en la identidad.

    - 100: prefijo explícito + código claro.
    - 90: prefijo explícito + nota/documento largo.
    - 75: prefijo inferido (``default_type`` aplicado).
    - <= 50: evidencia incompleta / formato dudoso.
    """

    raw_value: str
    """Valor original recibido, sin normalización (salvo trimming)."""

    reasons: List[str] = field(default_factory=list)
    """Razones textuales que explican cómo se llegó a esta identidad.

    Algunos valores típicos:

    - ``"explicit_prefix"``
    - ``"normalized_separator"``
    - ``"notes_extracted"``
    - ``"default_type_applied"``
    - ``"missing_prefix"``
    - ``"invalid_format"``
    - ``"empty_value"``
    """


_MULTI_DASH_RE = re.compile(r"-{3,}")
_WHITESPACE_RE = re.compile(r"\s+")


class TerritorialNormalizer:
    """Normalizador reutilizable de identidad territorial.

    Esta clase encapsula las reglas documentadas en las EFO para:

    - Preservar prefijos `NAP` / `ODN` / `ODB` como parte de la
      identidad canónica.
    - Normalizar separadores internos del código (espacios, guiones,
      subrayados).
    - Separar notas/documento largo del identificador canónico.
    - Calcular un `identity_score` aproximado según la evidencia.
    """

    # --------------------------- Zonas ---------------------------------

    def normalize_zone(self, raw: str, olt_id: int) -> Optional[TerritorialIdentity]:
        """Normaliza una zona a una identidad territorial.

        - Valores vacíos o ``"SIN_ZONA"`` devuelven ``None``.
        - El nombre canónico preserva el valor principal tal cual
          (colapsando espacios internos).
        """

        if raw is None:
            return None

        value = raw.strip()
        if not value:
            return None
        if value.upper() == "SIN_ZONA":
            return None

        canonical = _WHITESPACE_RE.sub(" ", value)
        reasons = ["zone_normalized"]

        return TerritorialIdentity(
            olt_id=olt_id,
            zone_name=canonical,
            object_type=TerritorialObjectType.ZONE,
            code=canonical,
            canonical_name=canonical,
            display_name=value,
            notes=None,
            identity_score=90,
            raw_value=value,
            reasons=reasons,
        )

    # -------------------- NAP / ODN / ODB genérico ---------------------

    def normalize_territorial_object(
        self,
        raw: str,
        olt_id: int,
        zone_name: Optional[str] = None,
        default_type: Optional[TerritorialObjectType] = None,
    ) -> Optional[TerritorialIdentity]:
        """Normaliza un valor territorial de planta externa.

        Maneja nombres con prefijo explícito (`NAP`/`ODN`/`ODB`) y, de
        forma controlada, valores sin prefijo cuando se proporciona un
        ``default_type``.

        Reglas clave:
        - Si el valor está vacío o es ``"SIN_ZONA"`` → ``None``.
        - Si hay prefijo explícito → se preserva y se normaliza el
          código interno.
        - Si no hay prefijo:
          - Sin ``default_type`` → ``None`` (no inferir automáticamente).
          - Con ``default_type`` → se aplica prefijo con
            ``identity_score = 75`` y razón ``default_type_applied``.
        """

        if raw is None:
            return None

        value = raw.strip()
        if not value:
            return None

        upper = value.upper()
        if upper == "SIN_ZONA":
            return None

        # Intentar detectar un prefijo explícito en cualquier parte del
        # string, priorizando ODN, luego NAP y finalmente ODB. Esto
        # permite casos como "odb_ODN_H5------COOPERATIVA" donde la
        # identidad real es ODN.
        explicit_prefix_order = [
            TerritorialObjectType.ODN,
            TerritorialObjectType.NAP,
            TerritorialObjectType.ODB,
        ]

        best_identity: Optional[TerritorialIdentity] = None

        for obj_type in explicit_prefix_order:
            prefix = obj_type.value
            idx = upper.find(prefix)
            if idx == -1:
                continue

            segment = value[idx:]
            identity = self._build_identity_from_segment(
                segment=segment,
                full_value=value,
                olt_id=olt_id,
                zone_name=zone_name,
                obj_type=obj_type,
            )
            if identity is not None:
                best_identity = identity
                break

        if best_identity is not None:
            return best_identity

        # Sin prefijo explícito
        if default_type is None:
            # Preferencia explícita de la EFO: no inferir automáticamente
            # el tipo si no hay prefijo.
            return None

        # Aplicar default_type de forma conservadora.
        code = self._normalize_code(value)
        canonical = f"{default_type.value} {code}" if code else default_type.value
        reasons = ["missing_prefix", "default_type_applied"]
        score = 75 if code else 50

        return TerritorialIdentity(
            olt_id=olt_id,
            zone_name=zone_name,
            object_type=default_type,
            code=code or value,
            canonical_name=canonical,
            display_name=value,
            notes=None,
            identity_score=score,
            raw_value=value,
            reasons=reasons,
        )

    # --------------------------- NapPort --------------------------------

    def normalize_nap_port(
        self,
        raw: str,
        olt_id: int,
        zone_name: Optional[str] = None,
    ) -> Optional[TerritorialIdentity]:
        """Normaliza un identificador de puerto NAP.

        Estrategia simple basada en el primer número encontrado en el
        valor textual. Valores vacíos o sin dígitos devuelven ``None``.
        """

        if raw is None:
            return None

        value = raw.strip()
        if not value:
            return None

        match = re.search(r"(\d+)", value)
        if not match:
            return None

        code = match.group(1)
        canonical = f"NAP_PORT {code}"
        reasons = ["nap_port_numeric"]

        return TerritorialIdentity(
            olt_id=olt_id,
            zone_name=zone_name,
            object_type=TerritorialObjectType.NAP_PORT,
            code=code,
            canonical_name=canonical,
            display_name=value,
            notes=None,
            identity_score=100,
            raw_value=value,
            reasons=reasons,
        )

    # ---------------------------- Helpers -------------------------------

    def _build_identity_from_segment(
        self,
        *,
        segment: str,
        full_value: str,
        olt_id: int,
        zone_name: Optional[str],
        obj_type: TerritorialObjectType,
    ) -> Optional[TerritorialIdentity]:
        """Construye una identidad a partir de un segmento que
        comienza en el prefijo (NAP/ODN/ODB)."""

        seg = segment.strip()
        upper = seg.upper()

        m = re.match(r"^(NAP|ODN|ODB)[\s_-]*(.*)$", upper)
        if not m:
            return None

        prefix = m.group(1)
        rest_upper = m.group(2) or ""
        # Usar el mismo slicing sobre el valor original para preservar
        # mayúsculas/minúsculas en display_name y notas.
        # Calculamos la misma longitud que el prefijo.
        prefix_len = len(prefix)
        # seg_original = seg
        rest_original = seg[prefix_len:]

        # Separar código y notas usando secuencias largas de guiones.
        notes: Optional[str] = None
        reasons: List[str] = ["explicit_prefix"]

        dash_match = _MULTI_DASH_RE.search(rest_original)
        if dash_match:
            code_part = rest_original[: dash_match.start()]
            notes_part = rest_original[dash_match.end() :].strip(" -_")
            if notes_part:
                notes = notes_part
                reasons.append("notes_extracted")
        else:
            code_part = rest_original

        code_part = code_part.strip(" _-")
        if not code_part:
            # No hay código claro tras el prefijo.
            reasons.append("invalid_format")
            return TerritorialIdentity(
                olt_id=olt_id,
                zone_name=zone_name,
                object_type=obj_type,
                code="",
                canonical_name=prefix,
                display_name=full_value.strip(),
                notes=notes,
                identity_score=50,
                raw_value=full_value.strip(),
                reasons=reasons,
            )

        # Detectar si hubo que normalizar separadores.
        if any(ch in code_part for ch in ["_", "-"]):
            reasons.append("normalized_separator")

        code = self._normalize_code(code_part)
        canonical = f"{prefix} {code}" if code else prefix

        # Calcular score según presencia de notas.
        if notes:
            score = 90
        else:
            score = 100

        return TerritorialIdentity(
            olt_id=olt_id,
            zone_name=zone_name,
            object_type=obj_type,
            code=code,
            canonical_name=canonical,
            display_name=full_value.strip(),
            notes=notes,
            identity_score=score,
            raw_value=full_value.strip(),
            reasons=reasons,
        )

    @staticmethod
    def _normalize_code(raw_code: str) -> str:
        """Normaliza el sufijo/código tras el prefijo.

        Reglas:
        - Reemplazar guiones y subrayados por espacios.
        - Colapsar espacios múltiples.
        - Convertir a mayúsculas.
        """

        if not raw_code:
            return ""

        tmp = raw_code.replace("_", " ").replace("-", " ")
        tmp = _WHITESPACE_RE.sub(" ", tmp).strip()
        return tmp.upper()


__all__ = ["TerritorialObjectType", "TerritorialIdentity", "TerritorialNormalizer"]
