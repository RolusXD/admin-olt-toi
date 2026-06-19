from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.api.deps import DbSession
from app.models.entities import Nap, NapPort
from app.schemas.entities import NapPortCreate, NapPortRead, NapPortUpdate

router = APIRouter(prefix="/nap-ports", tags=["nap-ports"])


@router.get("", response_model=list[NapPortRead])
def list_nap_ports(
    db: DbSession,
    nap_id: int | None = None,
    status: str | None = None,
    port_number: int | None = Query(default=None),
    olt_id: int | None = None,
) -> list[NapPort]:
    statement = select(NapPort)
    if olt_id is not None:
        statement = statement.where(NapPort.olt_id == olt_id)
    if nap_id is not None:
        statement = statement.where(NapPort.nap_id == nap_id)
    if status:
        statement = statement.where(NapPort.status == status)
    if port_number is not None:
        statement = statement.where(NapPort.port_number == port_number)
    return list(db.scalars(statement.order_by(NapPort.nap_id, NapPort.port_number)))


@router.post("", response_model=NapPortRead, status_code=status.HTTP_201_CREATED)
def create_nap_port(payload: NapPortCreate, db: DbSession) -> NapPort:
    nap = db.get(Nap, payload.nap_id)
    if not nap:
        raise HTTPException(status_code=404, detail="NAP not found")
    existing = db.scalar(select(NapPort).where(NapPort.nap_id == payload.nap_id, NapPort.port_number == payload.port_number))
    if existing:
        raise HTTPException(status_code=409, detail="NAP port already exists")
    port = NapPort(
        **payload.model_dump(exclude={"olt_id", "olt_code_snapshot"}),
        olt_id=nap.olt_id,
        olt_code_snapshot=nap.olt_code_snapshot,
    )
    db.add(port)
    db.commit()
    db.refresh(port)
    return port


@router.get("/{port_id}", response_model=NapPortRead)
def get_nap_port(port_id: int, db: DbSession) -> NapPort:
    port = db.get(NapPort, port_id)
    if not port:
        raise HTTPException(status_code=404, detail="NAP port not found")
    return port


@router.put("/{port_id}", response_model=NapPortRead)
def update_nap_port(port_id: int, payload: NapPortUpdate, db: DbSession) -> NapPort:
    port = db.get(NapPort, port_id)
    if not port:
        raise HTTPException(status_code=404, detail="NAP port not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(port, key, value)
    db.commit()
    db.refresh(port)
    return port


@router.put("/{port_id}/reserve", response_model=NapPortRead)
def reserve_nap_port(port_id: int, db: DbSession) -> NapPort:
    return _set_status(port_id, "reserved", db)


@router.put("/{port_id}/release", response_model=NapPortRead)
def release_nap_port(port_id: int, db: DbSession) -> NapPort:
    port = _set_status(port_id, "free", db, commit=False)
    port.onu_id = None
    port.customer_name_snapshot = None
    db.commit()
    db.refresh(port)
    return port


@router.put("/{port_id}/mark-damaged", response_model=NapPortRead)
def mark_nap_port_damaged(port_id: int, db: DbSession) -> NapPort:
    return _set_status(port_id, "damaged", db)


def _set_status(port_id: int, status_value: str, db: DbSession, commit: bool = True) -> NapPort:
    port = db.get(NapPort, port_id)
    if not port:
        raise HTTPException(status_code=404, detail="NAP port not found")
    port.status = status_value
    if commit:
        db.commit()
        db.refresh(port)
    return port
