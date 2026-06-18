from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from app.api.deps import DbSession
from app.models.entities import Olt, Onu, ProfileCatalog
from app.schemas.entities import ProfileCatalogCreate, ProfileCatalogRead, ProfileCatalogReadWithUsage, ProfileCatalogUpdate

router = APIRouter(prefix="/profile-catalogs", tags=["profile-catalogs"])


@router.get("", response_model=list[ProfileCatalogReadWithUsage])
def list_profile_catalogs(
    db: DbSession,
    olt_id: int | None = None,
    olt_code: str | None = None,
    vendor: str | None = None,
    model: str | None = None,
    firmware: str | None = None,
    direction: str | None = None,
    profile_kind: str | None = None,
    source: str | None = None,
    is_active: bool | None = Query(default=None),
    name: str | None = None,
) -> list[dict]:
    statement = select(ProfileCatalog)
    if olt_code:
        statement = statement.join(Olt, ProfileCatalog.olt_id == Olt.id).where(Olt.olt_code == olt_code.strip().upper())
    if olt_id is not None:
        statement = statement.where(ProfileCatalog.olt_id == olt_id)
    if vendor:
        statement = statement.where(ProfileCatalog.vendor == vendor)
    if model:
        statement = statement.where(ProfileCatalog.model == model)
    if firmware:
        statement = statement.where(ProfileCatalog.firmware == firmware)
    if direction:
        statement = statement.where(ProfileCatalog.direction == direction)
    if profile_kind:
        statement = statement.where(ProfileCatalog.profile_kind == profile_kind)
    if source:
        statement = statement.where(ProfileCatalog.source == source)
    if is_active is not None:
        statement = statement.where(ProfileCatalog.is_active.is_(is_active))
    if name:
        statement = statement.where(ProfileCatalog.name.ilike(f"%{name}%"))
    profiles = list(db.scalars(statement.order_by(ProfileCatalog.olt_id, ProfileCatalog.direction, ProfileCatalog.name)))
    return [_with_usage(db, profile) for profile in profiles]


@router.post("", response_model=ProfileCatalogRead, status_code=status.HTTP_201_CREATED)
def create_profile_catalog(payload: ProfileCatalogCreate, db: DbSession) -> ProfileCatalog:
    olt = db.get(Olt, payload.olt_id)
    if not olt:
        raise HTTPException(status_code=404, detail="OLT not found")
    existing = db.scalar(
        select(ProfileCatalog).where(
            ProfileCatalog.olt_id == payload.olt_id,
            ProfileCatalog.profile_kind == payload.profile_kind,
            ProfileCatalog.name == payload.name,
        )
    )
    if existing:
        raise HTTPException(status_code=409, detail="Profile catalog already exists")
    if payload.is_default and payload.is_active:
        _clear_default(db, payload.olt_id, payload.direction, payload.service_type)
    data = payload.model_dump()
    data["speed_kbps"] = data.get("speed_kbps") or _speed_from_payload(data)
    profile = ProfileCatalog(**payload.model_dump(), olt_code_snapshot=olt.olt_code)
    for key, value in data.items():
        setattr(profile, key, value)
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


@router.get("/{profile_id}", response_model=ProfileCatalogRead)
def get_profile_catalog(profile_id: int, db: DbSession) -> ProfileCatalog:
    profile = db.get(ProfileCatalog, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile catalog not found")
    return profile


@router.put("/{profile_id}", response_model=ProfileCatalogRead)
def update_profile_catalog(profile_id: int, payload: ProfileCatalogUpdate, db: DbSession) -> ProfileCatalog:
    profile = db.get(ProfileCatalog, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile catalog not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(profile, key, value)
    if profile.speed_kbps is None:
        profile.speed_kbps = _speed_from_payload(
            {
                "direction": profile.direction,
                "maximum_kbps": profile.maximum_kbps,
                "pir_kbps": profile.pir_kbps,
            }
        )
    if profile.is_default and profile.is_active:
        _clear_default(db, profile.olt_id, profile.direction, profile.service_type, exclude_id=profile.id)
    db.commit()
    db.refresh(profile)
    return profile


@router.put("/{profile_id}/activate", response_model=ProfileCatalogRead)
def activate_profile_catalog(profile_id: int, db: DbSession) -> ProfileCatalog:
    return _set_active(profile_id, True, db)


@router.put("/{profile_id}/deactivate", response_model=ProfileCatalogRead)
def deactivate_profile_catalog(profile_id: int, db: DbSession) -> ProfileCatalog:
    return _set_active(profile_id, False, db)


def _set_active(profile_id: int, active: bool, db: DbSession) -> ProfileCatalog:
    profile = db.get(ProfileCatalog, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile catalog not found")
    profile.is_active = active
    if not active:
        profile.is_default = False
    db.commit()
    db.refresh(profile)
    return profile


def _speed_from_payload(data: dict) -> int | None:
    if data.get("direction") == "upload":
        return data.get("maximum_kbps")
    return data.get("pir_kbps")


def _clear_default(db: DbSession, olt_id: int, direction: str, service_type: str, exclude_id: int | None = None) -> None:
    statement = select(ProfileCatalog).where(
        ProfileCatalog.olt_id == olt_id,
        ProfileCatalog.direction == direction,
        ProfileCatalog.service_type == service_type,
        ProfileCatalog.is_default.is_(True),
    )
    if exclude_id is not None:
        statement = statement.where(ProfileCatalog.id != exclude_id)
    for profile in db.scalars(statement):
        profile.is_default = False


def _with_usage(db: DbSession, profile: ProfileCatalog) -> dict:
    field = Onu.speed_profile_up if profile.direction == "upload" else Onu.speed_profile_down
    count = db.scalar(select(func.count()).select_from(Onu).where(Onu.olt_id == profile.olt_id, field == profile.name)) or 0
    data = ProfileCatalogRead.model_validate(profile).model_dump()
    data["onu_count"] = count
    return data
