from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.api.deps import DbSession
from app.models.entities import Nap, Olt, Onu, OnuEventHistory, OnuPowerHistory, Zone
from app.repositories.entities import OnuRepository, PowerRepository
from app.schemas.entities import OnuEventRead, OnuInternalInfoUpdate, OnuRead, OnuSchema, PowerSampleCreate, PowerSampleRead
from app.services.onu_service import OnuService

router = APIRouter(prefix="/onus", tags=["onus"])


@router.get("", response_model=list[OnuRead])
def list_onus(
    db: DbSession,
    q: str | None = Query(default=None),
    olt_id: int | None = None,
    olt_code: str | None = None,
    environment: str | None = None,
    zone_id: int | None = None,
    nap_id: int | None = None,
    status: str | None = None,
    serial_number: str | None = None,
    customer_name: str | None = None,
    onu_interface: str | None = None,
) -> list[Onu]:
    statement = select(Onu)
    if olt_code:
        statement = statement.join(Olt, Onu.olt_id == Olt.id).where(Olt.olt_code == olt_code.strip().upper())
    if environment:
        if not olt_code:
            statement = statement.join(Olt, Onu.olt_id == Olt.id)
        statement = statement.where(Olt.environment == environment.strip().lower())
    if q:
        like = f"%{q}%"
        statement = statement.where(
            Onu.customer_name.ilike(like) | Onu.serial_number.ilike(like) | Onu.onu_interface.ilike(like)
        )
    if olt_id is not None:
        statement = statement.where(Onu.olt_id == olt_id)
    if zone_id is not None:
        statement = statement.where(Onu.zone_id == zone_id)
    if nap_id is not None:
        statement = statement.where(Onu.nap_id == nap_id)
    if status:
        statement = statement.where(Onu.status == status)
    if serial_number:
        statement = statement.where(Onu.serial_number.ilike(f"%{serial_number}%"))
    if customer_name:
        statement = statement.where(Onu.customer_name.ilike(f"%{customer_name}%"))
    if onu_interface:
        statement = statement.where(Onu.onu_interface.ilike(f"%{onu_interface}%"))
    return list(db.scalars(statement.order_by(Onu.customer_name, Onu.serial_number)))


@router.post("", response_model=OnuRead, status_code=status.HTTP_201_CREATED)
def create_onu(payload: OnuSchema, db: DbSession) -> Onu:
    return OnuRepository(db).create(payload.model_dump())


@router.patch("/{onu_id}", response_model=OnuRead)
def update_onu(onu_id: int, payload: OnuSchema, db: DbSession) -> Onu:
    onu = db.get(Onu, onu_id)
    if not onu:
        raise HTTPException(status_code=404, detail="ONU not found")
    return OnuRepository(db).update(onu, payload.model_dump())


@router.patch("/{onu_id}/internal-info", response_model=OnuRead)
def update_onu_internal_info(onu_id: int, payload: OnuInternalInfoUpdate, db: DbSession) -> Onu:
    onu = db.get(Onu, onu_id)
    if not onu:
        raise HTTPException(status_code=404, detail="ONU not found")
    data = payload.model_dump(exclude_unset=True)
    if data.get("zone_id") is not None:
        zone = db.get(Zone, data["zone_id"])
        if not zone or zone.olt_id != onu.olt_id:
            raise HTTPException(status_code=422, detail="Zone does not belong to ONU OLT")
    if data.get("nap_id") is not None:
        nap = db.get(Nap, data["nap_id"])
        if not nap or nap.olt_id != onu.olt_id:
            raise HTTPException(status_code=422, detail="NAP does not belong to ONU OLT")
    for key, value in data.items():
        setattr(onu, key, value)
    db.commit()
    db.refresh(onu)
    return onu


@router.get("/{onu_id}", response_model=OnuRead)
def get_onu(onu_id: int, db: DbSession) -> Onu:
    onu = db.get(Onu, onu_id)
    if not onu:
        raise HTTPException(status_code=404, detail="ONU not found")
    return onu


@router.delete("/{onu_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_onu(onu_id: int, db: DbSession) -> None:
    onu = db.get(Onu, onu_id)
    if not onu:
        raise HTTPException(status_code=404, detail="ONU not found")
    OnuRepository(db).delete(onu)


@router.post("/{onu_id}/power", response_model=PowerSampleRead)
def add_power(onu_id: int, payload: PowerSampleCreate, db: DbSession):
    return OnuService(db).add_power_sample(onu_id, payload.rx_power, payload.tx_power)


@router.get("/{onu_id}/power", response_model=list[PowerSampleRead])
def power_history(onu_id: int, db: DbSession):
    return [sample for sample in PowerRepository(db).list() if sample.onu_id == onu_id]


@router.get("/{onu_id}/power-history", response_model=list[PowerSampleRead])
def onu_power_history(onu_id: int, db: DbSession) -> list[OnuPowerHistory]:
    return list(
        db.scalars(
            select(OnuPowerHistory)
            .where(OnuPowerHistory.onu_id == onu_id)
            .order_by(OnuPowerHistory.created_at.desc())
        )
    )


@router.get("/{onu_id}/events", response_model=list[OnuEventRead])
def onu_events(onu_id: int, db: DbSession) -> list[OnuEventHistory]:
    return list(
        db.scalars(
            select(OnuEventHistory)
            .where(OnuEventHistory.onu_id == onu_id)
            .order_by(OnuEventHistory.created_at.desc())
            .limit(50)
        )
    )
