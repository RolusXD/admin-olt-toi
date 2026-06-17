from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.api.deps import DbSession
from app.models.entities import Olt, OnuType
from app.schemas.entities import OnuTypeCreate, OnuTypeRead, OnuTypeUpdate

router = APIRouter(prefix="/onu-types", tags=["onu-types"])


@router.get("", response_model=list[OnuTypeRead])
def list_onu_types(
    db: DbSession,
    olt_id: int | None = None,
    olt_code: str | None = None,
    technology: str | None = None,
    source: str | None = None,
    is_active: bool | None = Query(default=None),
    name: str | None = None,
) -> list[OnuType]:
    statement = select(OnuType)
    if olt_code:
        statement = statement.join(Olt, OnuType.olt_id == Olt.id).where(Olt.olt_code == olt_code.strip().upper())
    if olt_id is not None:
        statement = statement.where(OnuType.olt_id == olt_id)
    if technology:
        statement = statement.where(OnuType.technology == technology)
    if source:
        statement = statement.where(OnuType.source == source)
    if is_active is not None:
        statement = statement.where(OnuType.is_active.is_(is_active))
    if name:
        statement = statement.where(OnuType.name.ilike(f"%{name}%"))
    return list(db.scalars(statement.order_by(OnuType.olt_id, OnuType.name)))


@router.post("", response_model=OnuTypeRead, status_code=status.HTTP_201_CREATED)
def create_onu_type(payload: OnuTypeCreate, db: DbSession) -> OnuType:
    olt = db.get(Olt, payload.olt_id)
    if not olt:
        raise HTTPException(status_code=404, detail="OLT not found")
    existing = db.scalar(select(OnuType).where(OnuType.olt_id == payload.olt_id, OnuType.name == payload.name))
    if existing:
        raise HTTPException(status_code=409, detail="ONU type already exists for this OLT")
    onu_type = OnuType(**payload.model_dump(), olt_code_snapshot=olt.olt_code)
    db.add(onu_type)
    db.commit()
    db.refresh(onu_type)
    return onu_type


@router.get("/{onu_type_id}", response_model=OnuTypeRead)
def get_onu_type(onu_type_id: int, db: DbSession) -> OnuType:
    onu_type = db.get(OnuType, onu_type_id)
    if not onu_type:
        raise HTTPException(status_code=404, detail="ONU type not found")
    return onu_type


@router.put("/{onu_type_id}", response_model=OnuTypeRead)
def update_onu_type(onu_type_id: int, payload: OnuTypeUpdate, db: DbSession) -> OnuType:
    onu_type = db.get(OnuType, onu_type_id)
    if not onu_type:
        raise HTTPException(status_code=404, detail="ONU type not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(onu_type, key, value)
    db.commit()
    db.refresh(onu_type)
    return onu_type


@router.put("/{onu_type_id}/activate", response_model=OnuTypeRead)
def activate_onu_type(onu_type_id: int, db: DbSession) -> OnuType:
    return _set_active(onu_type_id, True, db)


@router.put("/{onu_type_id}/deactivate", response_model=OnuTypeRead)
def deactivate_onu_type(onu_type_id: int, db: DbSession) -> OnuType:
    return _set_active(onu_type_id, False, db)


def _set_active(onu_type_id: int, active: bool, db: DbSession) -> OnuType:
    onu_type = db.get(OnuType, onu_type_id)
    if not onu_type:
        raise HTTPException(status_code=404, detail="ONU type not found")
    onu_type.is_active = active
    db.commit()
    db.refresh(onu_type)
    return onu_type
