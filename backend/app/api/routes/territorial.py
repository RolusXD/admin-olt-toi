from __future__ import annotations

"""API read-only para previews de reconstrucción territorial (P4.4).

Este router expone endpoints de **solo lectura** que devuelven los
previews calculados por los servicios de reconstrucción territorial:

- Zones por OLT (`ZoneReconstructionPreviewService`).
- NAP/ODN/ODB por OLT (`NapReconstructionPreviewService`).

Restricciones (EFO + P4.4):
- No modifica datos.
- No ejecuta "apply".
- No realiza `INSERT/UPDATE/DELETE/commit`.
- No accede a OLTs reales ni ejecuta Telnet.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.entities import (
    NapReconstructionPreview,
    TerritorialAuditCenter,
    ZoneReconstructionPreview,
)
from app.services.nap_reconstruction_preview_service import (
    NapReconstructionPreviewService,
)
from app.services.zone_reconstruction_preview_service import (
    ZoneReconstructionPreviewService,
)
from app.services.territorial_audit_center_service import (
    TerritorialAuditCenterService,
)


router = APIRouter(prefix="/admin/territorial", tags=["territorial-preview"])


@router.get(
    "/zones/preview",
    response_model=ZoneReconstructionPreview,
    summary="Preview de reconstrucción de Zones por OLT",
    description=(
        "Devuelve el preview de reconstrucción territorial de Zones por OLT "
        "(Fase P4.1) calculado por ZoneReconstructionPreviewService.\n\n"
        "Esta operación es estrictamente de solo lectura:\n"
        "- No crea ni actualiza registros.\n"
        "- No ejecuta apply ni confirma cambios.\n"
        "- No accede a OLTs reales ni ejecuta Telnet; trabaja únicamente sobre datos ya importados."
    ),
)
def get_zones_preview(db: Session = Depends(get_db)) -> ZoneReconstructionPreview:
    """Endpoint read-only para obtener el preview de Zones por OLT.

    Internamente sólo instancia `ZoneReconstructionPreviewService` y
    llama a su método `preview()`, que realiza consultas `SELECT` y
    cálculos en memoria.
    """

    service = ZoneReconstructionPreviewService(db)
    return service.preview()


@router.get(
    "/naps/preview",
    response_model=NapReconstructionPreview,
    summary="Preview de reconstrucción de NAP/ODN/ODB por OLT",
    description=(
        "Devuelve el preview de reconstrucción territorial de NAP/ODN/ODB por OLT "
        "(Fase P4.3) calculado por NapReconstructionPreviewService.\n\n"
        "Esta operación es estrictamente de solo lectura:\n"
        "- No crea, actualiza ni borra registros (sin INSERT/UPDATE/DELETE/commit).\n"
        "- No ejecuta apply ni confirma reconstrucciones.\n"
        "- No accede a OLTs reales ni ejecuta Telnet; trabaja únicamente sobre el estado actual en BD."
    ),
)
def get_naps_preview(db: Session = Depends(get_db)) -> NapReconstructionPreview:
    """Endpoint read-only para obtener el preview de NAP/ODN/ODB por OLT.

    Sólo delega en `NapReconstructionPreviewService.preview()`.
    """

    service = NapReconstructionPreviewService(db)
    return service.preview()


@router.get(
    "/audit-center",
    response_model=TerritorialAuditCenter,
    summary="Centro de Auditoría Territorial consolidado",
    description=(
        "Devuelve una vista consolidada de auditoría territorial (P4.5) "
        "construida a partir de los previews de Zones y NAP/ODN/ODB.\n\n"
        "Esta operación es estrictamente de solo lectura:\n"
        "- No crea, actualiza ni borra registros (sin INSERT/UPDATE/DELETE/commit).\n"
        "- No ejecuta apply ni confirma reconstrucciones.\n"
        "- No accede a OLTs reales ni ejecuta Telnet; trabaja únicamente sobre el estado actual en BD."
    ),
)
def get_territorial_audit_center(
    db: Session = Depends(get_db),
) -> TerritorialAuditCenter:
    """Endpoint read-only del Centro de Auditoría Territorial.

    Solo instancia ``TerritorialAuditCenterService`` y devuelve el
    resultado de ``build()``, que a su vez consume en memoria los
    previews territoriales existentes.
    """

    service = TerritorialAuditCenterService(db)
    return service.build()


__all__ = ["router"]
