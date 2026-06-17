from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.api.deps import DbSession
from app.models.entities import Olt, Vlan
from app.schemas.entities import VlanCreate, VlanRead, VlanUpdate

router = APIRouter(prefix="/vlans", tags=["vlans"])


@router.get("", response_model=list[VlanRead])
def list_vlans(
    db: DbSession,
    olt_id: int | None = None,
    olt_code: str | None = None,
    service_type: str | None = None,
    source: str | None = None,
    is_active: bool | None = Query(default=None),
) -> list[Vlan]:
    statement = select(Vlan)
    if olt_code:
        statement = statement.join(Olt, Vlan.olt_id == Olt.id).where(Olt.olt_code == olt_code.strip().upper())
    if olt_id is not None:
        statement = statement.where(Vlan.olt_id == olt_id)
    if service_type:
        statement = statement.where(Vlan.service_type == service_type)
    if source:
        statement = statement.where(Vlan.source == source)
    if is_active is not None:
        statement = statement.where(Vlan.is_active.is_(is_active))
    return list(db.scalars(statement.order_by(Vlan.olt_id, Vlan.vlan_id)))


@router.post("", response_model=VlanRead, status_code=status.HTTP_201_CREATED)
def create_vlan(payload: VlanCreate, db: DbSession) -> Vlan:
    olt = db.get(Olt, payload.olt_id)
    if not olt:
        raise HTTPException(status_code=404, detail="OLT not found")
    existing = db.scalar(select(Vlan).where(Vlan.olt_id == payload.olt_id, Vlan.vlan_id == payload.vlan_id))
    if existing:
        raise HTTPException(status_code=409, detail="VLAN already exists for this OLT")
    vlan = Vlan(**payload.model_dump(), olt_code_snapshot=olt.olt_code)
    db.add(vlan)
    db.commit()
    db.refresh(vlan)
    return vlan


@router.get("/{vlan_id}", response_model=VlanRead)
def get_vlan(vlan_id: int, db: DbSession) -> Vlan:
    vlan = db.get(Vlan, vlan_id)
    if not vlan:
        raise HTTPException(status_code=404, detail="VLAN not found")
    return vlan


@router.put("/{vlan_id}", response_model=VlanRead)
def update_vlan(vlan_id: int, payload: VlanUpdate, db: DbSession) -> Vlan:
    vlan = db.get(Vlan, vlan_id)
    if not vlan:
        raise HTTPException(status_code=404, detail="VLAN not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(vlan, key, value)
    db.commit()
    db.refresh(vlan)
    return vlan


@router.put("/{vlan_id}/activate", response_model=VlanRead)
def activate_vlan(vlan_id: int, db: DbSession) -> Vlan:
    return _set_active(vlan_id, True, db)


@router.put("/{vlan_id}/deactivate", response_model=VlanRead)
def deactivate_vlan(vlan_id: int, db: DbSession) -> Vlan:
    return _set_active(vlan_id, False, db)


def _set_active(vlan_id: int, active: bool, db: DbSession) -> Vlan:
    vlan = db.get(Vlan, vlan_id)
    if not vlan:
        raise HTTPException(status_code=404, detail="VLAN not found")
    vlan.is_active = active
    db.commit()
    db.refresh(vlan)
    return vlan
