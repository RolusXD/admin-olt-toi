from fastapi import APIRouter, HTTPException, status

from app.api.deps import DbSession
from app.models.entities import Zone
from app.repositories.entities import ZoneRepository
from app.schemas.entities import ZoneRead, ZoneSchema

router = APIRouter(prefix="/zones", tags=["zones"])


@router.get("", response_model=list[ZoneRead])
def list_zones(db: DbSession) -> list[Zone]:
    return ZoneRepository(db).list()


@router.post("", response_model=ZoneRead, status_code=status.HTTP_201_CREATED)
def create_zone(payload: ZoneSchema, db: DbSession) -> Zone:
    return ZoneRepository(db).create(payload.model_dump())


@router.patch("/{zone_id}", response_model=ZoneRead)
def update_zone(zone_id: int, payload: ZoneSchema, db: DbSession) -> Zone:
    zone = db.get(Zone, zone_id)
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")
    return ZoneRepository(db).update(zone, payload.model_dump())


@router.delete("/{zone_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_zone(zone_id: int, db: DbSession) -> None:
    zone = db.get(Zone, zone_id)
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")
    ZoneRepository(db).delete(zone)
