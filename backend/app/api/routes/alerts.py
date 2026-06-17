from fastapi import APIRouter, Query
from sqlalchemy import select

from app.api.deps import DbSession
from app.models.entities import Olt, Onu
from app.schemas.entities import AlertsResponse

router = APIRouter(prefix="/alerts", tags=["alerts"])


def _base_statement(olt_id: int | None, olt_code: str | None, environment: str | None):
    statement = select(Onu)
    if olt_code:
        statement = statement.join(Olt, Onu.olt_id == Olt.id).where(Olt.olt_code == olt_code.strip().upper())
    if environment:
        if not olt_code:
            statement = statement.join(Olt, Onu.olt_id == Olt.id)
        statement = statement.where(Olt.environment == environment.strip().lower())
    if olt_id is not None:
        statement = statement.where(Onu.olt_id == olt_id)
    return statement


@router.get("", response_model=AlertsResponse)
def alerts(
    db: DbSession,
    olt_id: int | None = Query(default=None),
    olt_code: str | None = Query(default=None),
    environment: str | None = Query(default=None),
) -> dict[str, list[Onu]]:
    base = _base_statement(olt_id, olt_code, environment)
    return {
        "offline": list(db.scalars(base.where(Onu.status == "offline").order_by(Onu.customer_name))),
        "los": list(db.scalars(base.where(Onu.last_down_cause == "LOS").order_by(Onu.customer_name))),
        "dying_gasp": list(
            db.scalars(base.where(Onu.last_down_cause == "DyingGasp").order_by(Onu.customer_name))
        ),
        "rx_warning": list(db.scalars(base.where(Onu.signal_status == "warning").order_by(Onu.customer_name))),
        "rx_critical": list(db.scalars(base.where(Onu.signal_status == "critical").order_by(Onu.customer_name))),
    }
