from fastapi import APIRouter

from app.api.deps import DbSession
from app.schemas.entities import OnuOperationalSanityPreview
from app.services.onu_operational_sanity_service import OnuOperationalSanityService


router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/onu-sanity/preview", response_model=OnuOperationalSanityPreview)
def onu_sanity_preview(db: DbSession) -> OnuOperationalSanityPreview:
    """Endpoint interno de auditoría de saneamiento operacional ONU.

    Solo lectura: ejecuta `OnuOperationalSanityService.preview()` y
    devuelve un resumen + listado de cambios propuestos sin modificar
    ninguna entidad en base de datos.
    """

    service = OnuOperationalSanityService(db)
    return service.preview()
