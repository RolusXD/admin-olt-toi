from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import DbSession
from app.models.entities import Olt, PonPort
from app.schemas.entities import PonPortRead

router = APIRouter(prefix="/pon-ports", tags=["pon-ports"])


@router.get("", response_model=list[PonPortRead])
def list_pon_ports(db: DbSession, olt_id: int | None = None, olt_code: str | None = None) -> list[PonPort]:
    statement = select(PonPort)
    if olt_code:
        statement = statement.join(Olt, PonPort.olt_id == Olt.id).where(Olt.olt_code == olt_code.strip().upper())
    if olt_id is not None:
        statement = statement.where(PonPort.olt_id == olt_id)
    return list(db.scalars(statement.order_by(PonPort.olt_id, PonPort.slot, PonPort.port)))
