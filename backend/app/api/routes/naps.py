from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.api.deps import DbSession
from app.models.entities import Nap, NapPort, Olt, Zone
from app.schemas.entities import NapRead, NapSchema

router = APIRouter(prefix="/naps", tags=["naps"])


@router.get("", response_model=list[NapRead])
def list_naps(
    db: DbSession,
    zone_id: int | None = None,
    name: str | None = None,
    code: str | None = None,
    is_active: bool | None = Query(default=None),
    olt_id: int | None = None,
) -> list[Nap]:
    statement = select(Nap)
    if olt_id is not None:
        statement = statement.where(Nap.olt_id == olt_id)
    if zone_id is not None:
        statement = statement.where(Nap.zone_id == zone_id)
    if name:
        statement = statement.where(Nap.name.ilike(f"%{name}%"))
    if code:
        statement = statement.where(Nap.code == code)
    if is_active is not None:
        statement = statement.where(Nap.is_active.is_(is_active))
    return list(db.scalars(statement.order_by(Nap.zone_id, Nap.name)))


@router.post("", response_model=NapRead, status_code=status.HTTP_201_CREATED)
def create_nap(payload: NapSchema, db: DbSession) -> Nap:
    if payload.olt_id is None:
        raise HTTPException(status_code=422, detail="olt_id is required")
    olt = db.get(Olt, payload.olt_id)
    zone = db.get(Zone, payload.zone_id)
    if not olt or not zone or zone.olt_id != olt.id:
        raise HTTPException(status_code=422, detail="OLT and zone association is invalid")
    existing = db.scalar(select(Nap).where(Nap.olt_id == olt.id, Nap.zone_id == payload.zone_id, Nap.name == payload.name))
    if existing:
        raise HTTPException(status_code=409, detail="NAP already exists in this zone")
    nap = Nap(**payload.model_dump(exclude={"olt_code_snapshot"}), olt_code_snapshot=olt.olt_code)
    db.add(nap)
    db.flush()
    ensure_nap_ports(db, nap)
    db.commit()
    db.refresh(nap)
    return nap


@router.get("/{nap_id}", response_model=NapRead)
def get_nap(nap_id: int, db: DbSession) -> Nap:
    nap = db.get(Nap, nap_id)
    if not nap:
        raise HTTPException(status_code=404, detail="NAP not found")
    return nap


@router.put("/{nap_id}", response_model=NapRead)
@router.patch("/{nap_id}", response_model=NapRead)
def update_nap(nap_id: int, payload: NapSchema, db: DbSession) -> Nap:
    nap = db.get(Nap, nap_id)
    if not nap:
        raise HTTPException(status_code=404, detail="NAP not found")
    for key, value in payload.model_dump().items():
        setattr(nap, key, value)
    ensure_nap_ports(db, nap)
    db.commit()
    db.refresh(nap)
    return nap


@router.put("/{nap_id}/activate", response_model=NapRead)
def activate_nap(nap_id: int, db: DbSession) -> Nap:
    return _set_active(nap_id, True, db)


@router.put("/{nap_id}/deactivate", response_model=NapRead)
def deactivate_nap(nap_id: int, db: DbSession) -> Nap:
    return _set_active(nap_id, False, db)


def _set_active(nap_id: int, active: bool, db: DbSession) -> Nap:
    nap = db.get(Nap, nap_id)
    if not nap:
        raise HTTPException(status_code=404, detail="NAP not found")
    nap.is_active = active
    db.commit()
    db.refresh(nap)
    return nap


def ensure_nap_ports(db, nap: Nap) -> None:
    existing = set(db.scalars(select(NapPort.port_number).where(NapPort.nap_id == nap.id)))
    for port in range(1, (nap.capacity or 0) + 1):
        if port not in existing:
            db.add(NapPort(olt_id=nap.olt_id, olt_code_snapshot=nap.olt_code_snapshot, nap_id=nap.id, port_number=port, label=f"Puerto {port}", status="free"))
