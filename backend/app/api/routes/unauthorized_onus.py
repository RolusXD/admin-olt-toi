from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from app.api.deps import DbSession
from app.models.entities import UnauthorizedOnuEvent
from app.schemas.entities import UnauthorizedOnuEventRead, UnauthorizedOnuRead
from app.services.onu_discovery_service import OnuDiscoveryService

router = APIRouter(prefix="/unauthorized-onus", tags=["unauthorized-onus"])


@router.get("", response_model=list[UnauthorizedOnuRead])
def list_unauthorized_onus(
    db: DbSession,
    olt_id: int | None = Query(default=None),
    olt_code: str | None = Query(default=None),
    status: str | None = Query(default=None),
    serial_number: str | None = Query(default=None),
    pon_port_interface: str | None = Query(default=None),
    detected_type: str | None = Query(default=None),
    detected_vendor: str | None = Query(default=None),
    environment: str | None = Query(default="production"),
) -> list:
    return OnuDiscoveryService(db).list(
        olt_id=olt_id,
        olt_code=olt_code,
        status=status,
        serial_number=serial_number,
        pon_port_interface=pon_port_interface,
        detected_type=detected_type,
        detected_vendor=detected_vendor,
        environment=environment,
    )


@router.get("/{unauthorized_onu_id}", response_model=UnauthorizedOnuRead)
def get_unauthorized_onu(unauthorized_onu_id: int, db: DbSession):
    onu = OnuDiscoveryService(db).get(unauthorized_onu_id)
    if not onu:
        raise HTTPException(status_code=404, detail="Unauthorized ONU not found")
    return onu


@router.get("/{unauthorized_onu_id}/events", response_model=list[UnauthorizedOnuEventRead])
def unauthorized_onu_events(unauthorized_onu_id: int, db: DbSession) -> list[UnauthorizedOnuEvent]:
    if not OnuDiscoveryService(db).get(unauthorized_onu_id):
        raise HTTPException(status_code=404, detail="Unauthorized ONU not found")
    return list(
        db.scalars(
            select(UnauthorizedOnuEvent)
            .where(UnauthorizedOnuEvent.unauthorized_onu_id == unauthorized_onu_id)
            .order_by(UnauthorizedOnuEvent.created_at.desc())
        )
    )


@router.put("/{unauthorized_onu_id}/ignore", response_model=UnauthorizedOnuRead)
def ignore_unauthorized_onu(unauthorized_onu_id: int, db: DbSession):
    onu = OnuDiscoveryService(db).get(unauthorized_onu_id)
    if not onu:
        raise HTTPException(status_code=404, detail="Unauthorized ONU not found")
    return OnuDiscoveryService(db).set_status(onu, "ignored")


@router.put("/{unauthorized_onu_id}/restore", response_model=UnauthorizedOnuRead)
def restore_unauthorized_onu(unauthorized_onu_id: int, db: DbSession):
    onu = OnuDiscoveryService(db).get(unauthorized_onu_id)
    if not onu:
        raise HTTPException(status_code=404, detail="Unauthorized ONU not found")
    return OnuDiscoveryService(db).set_status(onu, "pending")


@router.put("/{unauthorized_onu_id}/ready", response_model=UnauthorizedOnuRead)
def ready_unauthorized_onu(unauthorized_onu_id: int, db: DbSession):
    onu = OnuDiscoveryService(db).get(unauthorized_onu_id)
    if not onu:
        raise HTTPException(status_code=404, detail="Unauthorized ONU not found")
    return OnuDiscoveryService(db).set_status(onu, "ready_for_provisioning")
