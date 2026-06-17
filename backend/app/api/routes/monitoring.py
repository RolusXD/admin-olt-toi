from datetime import datetime

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.api.deps import DbSession
from app.models.entities import MonitoringExecution, Olt
from app.schemas.entities import MonitoringExecutionRead, MonitoringLatestResponse

router = APIRouter(prefix="/monitoring", tags=["monitoring"])


@router.get("/executions", response_model=list[MonitoringExecutionRead])
def list_monitoring_executions(
    db: DbSession,
    olt_id: int | None = Query(default=None),
    olt_code: str | None = Query(default=None),
    environment: str | None = Query(default=None),
    task_type: str | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[MonitoringExecution]:
    statement = select(MonitoringExecution)
    if olt_code:
        statement = statement.join(Olt, MonitoringExecution.olt_id == Olt.id).where(Olt.olt_code == olt_code.strip().upper())
    if environment:
        if not olt_code:
            statement = statement.join(Olt, MonitoringExecution.olt_id == Olt.id)
        statement = statement.where(Olt.environment == environment.strip().lower())
    if olt_id is not None:
        statement = statement.where(MonitoringExecution.olt_id == olt_id)
    if task_type:
        statement = statement.where(MonitoringExecution.task_type == task_type)
    if date_from is not None:
        statement = statement.where(MonitoringExecution.started_at >= date_from)
    if date_to is not None:
        statement = statement.where(MonitoringExecution.started_at <= date_to)
    return list(db.scalars(statement.order_by(MonitoringExecution.started_at.desc()).limit(limit)))


@router.get("/latest", response_model=MonitoringLatestResponse)
def latest_monitoring_executions(
    db: DbSession,
    olt_id: int | None = Query(default=None),
    olt_code: str | None = Query(default=None),
    environment: str | None = Query(default=None),
) -> dict:
    def latest(task_type: str) -> MonitoringExecution | None:
        statement = select(MonitoringExecution).where(MonitoringExecution.task_type == task_type)
        if olt_code:
            statement = statement.join(Olt, MonitoringExecution.olt_id == Olt.id).where(Olt.olt_code == olt_code.strip().upper())
        if environment:
            if not olt_code:
                statement = statement.join(Olt, MonitoringExecution.olt_id == Olt.id)
            statement = statement.where(Olt.environment == environment.strip().lower())
        if olt_id is not None:
            statement = statement.where(MonitoringExecution.olt_id == olt_id)
        return db.scalar(statement.order_by(MonitoringExecution.started_at.desc()).limit(1))

    return {
        "sync_onus": latest("sync_onus"),
        "sync_power": latest("sync_power"),
    }
