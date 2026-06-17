from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.api.deps import DbSession
from app.models.entities import Olt, SpeedProfile
from app.schemas.entities import SpeedProfileCreate, SpeedProfileRead, SpeedProfileUpdate

router = APIRouter(prefix="/speed-profiles", tags=["speed-profiles"])


@router.get("", response_model=list[SpeedProfileRead])
def list_speed_profiles(
    db: DbSession,
    olt_id: int | None = None,
    olt_code: str | None = None,
    technology: str | None = None,
    source: str | None = None,
    is_active: bool | None = Query(default=None),
    name: str | None = None,
) -> list[SpeedProfile]:
    statement = select(SpeedProfile)
    if olt_code:
        statement = statement.join(Olt, SpeedProfile.olt_id == Olt.id).where(Olt.olt_code == olt_code.strip().upper())
    if olt_id is not None:
        statement = statement.where(SpeedProfile.olt_id == olt_id)
    if technology:
        statement = statement.where(SpeedProfile.technology == technology)
    if source:
        statement = statement.where(SpeedProfile.source == source)
    if is_active is not None:
        statement = statement.where(SpeedProfile.is_active.is_(is_active))
    if name:
        statement = statement.where(SpeedProfile.name.ilike(f"%{name}%"))
    return list(db.scalars(statement.order_by(SpeedProfile.olt_id, SpeedProfile.name)))


@router.post("", response_model=SpeedProfileRead, status_code=status.HTTP_201_CREATED)
def create_speed_profile(payload: SpeedProfileCreate, db: DbSession) -> SpeedProfile:
    olt = db.get(Olt, payload.olt_id)
    if not olt:
        raise HTTPException(status_code=404, detail="OLT not found")
    existing = db.scalar(select(SpeedProfile).where(SpeedProfile.olt_id == payload.olt_id, SpeedProfile.profile_code == payload.profile_code))
    if existing:
        raise HTTPException(status_code=409, detail="Speed profile already exists for this OLT")
    profile = SpeedProfile(**payload.model_dump(), olt_code_snapshot=olt.olt_code)
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


@router.get("/{profile_id}", response_model=SpeedProfileRead)
def get_speed_profile(profile_id: int, db: DbSession) -> SpeedProfile:
    profile = db.get(SpeedProfile, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Speed profile not found")
    return profile


@router.put("/{profile_id}", response_model=SpeedProfileRead)
def update_speed_profile(profile_id: int, payload: SpeedProfileUpdate, db: DbSession) -> SpeedProfile:
    profile = db.get(SpeedProfile, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Speed profile not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(profile, key, value)
    db.commit()
    db.refresh(profile)
    return profile


@router.put("/{profile_id}/activate", response_model=SpeedProfileRead)
def activate_speed_profile(profile_id: int, db: DbSession) -> SpeedProfile:
    return _set_active(profile_id, True, db)


@router.put("/{profile_id}/deactivate", response_model=SpeedProfileRead)
def deactivate_speed_profile(profile_id: int, db: DbSession) -> SpeedProfile:
    return _set_active(profile_id, False, db)


def _set_active(profile_id: int, active: bool, db: DbSession) -> SpeedProfile:
    profile = db.get(SpeedProfile, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Speed profile not found")
    profile.is_active = active
    db.commit()
    db.refresh(profile)
    return profile
