from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import DbSession
from app.models.entities import Olt, Vlan
from app.schemas.entities import VlanRead

router = APIRouter(prefix="/vlans", tags=["vlans"])


@router.get("", response_model=list[VlanRead])
def list_vlans(db: DbSession, olt_id: int | None = None, olt_code: str | None = None) -> list[Vlan]:
    statement = select(Vlan)
    if olt_code:
        statement = statement.join(Olt, Vlan.olt_id == Olt.id).where(Olt.olt_code == olt_code.strip().upper())
    if olt_id is not None:
        statement = statement.where(Vlan.olt_id == olt_id)
    return list(db.scalars(statement.order_by(Vlan.olt_id, Vlan.vlan_id)))
