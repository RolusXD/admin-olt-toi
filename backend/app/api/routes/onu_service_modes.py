from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.api.deps import DbSession
from app.models.entities import Olt, OnuServiceModeTemplate
from app.schemas.entities import (
    OnuServiceModeTemplateCreate,
    OnuServiceModeTemplateRead,
    OnuServiceModeTemplateUpdate,
)

router = APIRouter(prefix="/onu-service-modes", tags=["onu-service-modes"])


@router.get("", response_model=list[OnuServiceModeTemplateRead])
def list_onu_service_modes(
    db: DbSession,
    olt_id: int | None = None,
    mode_code: str | None = None,
    is_active: bool | None = Query(default=None),
) -> list[OnuServiceModeTemplate]:
    statement = select(OnuServiceModeTemplate)
    if olt_id is not None:
        statement = statement.where(OnuServiceModeTemplate.olt_id == olt_id)
    if mode_code:
        statement = statement.where(OnuServiceModeTemplate.mode_code == mode_code)
    if is_active is not None:
        statement = statement.where(OnuServiceModeTemplate.is_active.is_(is_active))
    return list(db.scalars(statement.order_by(OnuServiceModeTemplate.olt_id, OnuServiceModeTemplate.name)))


@router.post("", response_model=OnuServiceModeTemplateRead, status_code=status.HTTP_201_CREATED)
def create_onu_service_mode(payload: OnuServiceModeTemplateCreate, db: DbSession) -> OnuServiceModeTemplate:
    if not db.get(Olt, payload.olt_id):
        raise HTTPException(status_code=404, detail="OLT not found")
    existing = db.scalar(
        select(OnuServiceModeTemplate).where(
            OnuServiceModeTemplate.olt_id == payload.olt_id,
            OnuServiceModeTemplate.mode_code == payload.mode_code,
        )
    )
    if existing:
        raise HTTPException(status_code=409, detail="ONU service mode already exists for this OLT")
    if payload.default_for_provisioning:
        _clear_default(db, payload.olt_id)
    item = OnuServiceModeTemplate(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.put("/{mode_id}", response_model=OnuServiceModeTemplateRead)
def update_onu_service_mode(
    mode_id: int,
    payload: OnuServiceModeTemplateUpdate,
    db: DbSession,
) -> OnuServiceModeTemplate:
    item = db.get(OnuServiceModeTemplate, mode_id)
    if not item:
        raise HTTPException(status_code=404, detail="ONU service mode not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    if item.default_for_provisioning and item.is_active:
        _clear_default(db, item.olt_id, exclude_id=item.id)
    if not item.is_active:
        item.default_for_provisioning = False
    db.commit()
    db.refresh(item)
    return item


def _clear_default(db: DbSession, olt_id: int, exclude_id: int | None = None) -> None:
    statement = select(OnuServiceModeTemplate).where(
        OnuServiceModeTemplate.olt_id == olt_id,
        OnuServiceModeTemplate.default_for_provisioning.is_(True),
    )
    if exclude_id is not None:
        statement = statement.where(OnuServiceModeTemplate.id != exclude_id)
    for item in db.scalars(statement):
        item.default_for_provisioning = False
