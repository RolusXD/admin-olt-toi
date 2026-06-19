from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.api.deps import DbSession
from app.models.entities import Olt, Zone
from app.schemas.entities import ZoneRead, ZoneSchema

router = APIRouter(prefix="/zones", tags=["zones"])


@router.get("", response_model=list[ZoneRead])
def list_zones(
    db: DbSession,
    name: str | None = None,
    code: str | None = None,
    source: str | None = None,
    is_active: bool | None = Query(default=None),
    olt_id: int | None = None,
) -> list[Zone]:
    statement = select(Zone)
    if olt_id is not None:
        statement = statement.where(Zone.olt_id == olt_id)
    if name:
        statement = statement.where(Zone.name.ilike(f"%{name}%"))
    if code:
        statement = statement.where(Zone.code == code)
    if source:
        statement = statement.where(Zone.source == source)
    if is_active is not None:
        statement = statement.where(Zone.is_active.is_(is_active))
    return list(db.scalars(statement.order_by(Zone.name)))


@router.post("", response_model=ZoneRead, status_code=status.HTTP_201_CREATED)
def create_zone(payload: ZoneSchema, db: DbSession) -> Zone:
    if payload.olt_id is None:
        raise HTTPException(status_code=422, detail="olt_id is required")
    olt = db.get(Olt, payload.olt_id)
    if not olt:
        raise HTTPException(status_code=404, detail="OLT not found")
    existing = db.scalar(select(Zone).where(Zone.olt_id == payload.olt_id, Zone.name == payload.name))
    if existing:
        raise HTTPException(status_code=409, detail="Zone already exists")
    zone = Zone(**payload.model_dump(exclude={"olt_code_snapshot"}), olt_code_snapshot=olt.olt_code)
    db.add(zone)
    db.commit()
    db.refresh(zone)
    return zone


@router.get("/{zone_id}", response_model=ZoneRead)
def get_zone(zone_id: int, db: DbSession) -> Zone:
    zone = db.get(Zone, zone_id)
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")
    return zone


@router.put("/{zone_id}", response_model=ZoneRead)
@router.patch("/{zone_id}", response_model=ZoneRead)
def update_zone(zone_id: int, payload: ZoneSchema, db: DbSession) -> Zone:
    zone = db.get(Zone, zone_id)
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")
    for key, value in payload.model_dump().items():
        setattr(zone, key, value)
    db.commit()
    db.refresh(zone)
    return zone


@router.put("/{zone_id}/activate", response_model=ZoneRead)
def activate_zone(zone_id: int, db: DbSession) -> Zone:
    return _set_active(zone_id, True, db)


@router.put("/{zone_id}/deactivate", response_model=ZoneRead)
def deactivate_zone(zone_id: int, db: DbSession) -> Zone:
    return _set_active(zone_id, False, db)


def _set_active(zone_id: int, active: bool, db: DbSession) -> Zone:
    zone = db.get(Zone, zone_id)
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")
    zone.is_active = active
    db.commit()
    db.refresh(zone)
    return zone
