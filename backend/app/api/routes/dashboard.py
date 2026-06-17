from fastapi import APIRouter, Query
from sqlalchemy import select

from app.api.deps import DbSession
from app.models.entities import MonitoringExecution, Olt
from app.repositories.entities import dashboard_counts, dashboard_environment_stats
from app.schemas.entities import DashboardEnvironmentSummary, DashboardSummary
from app.services.onu_service import OnuService

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummary)
def summary(
    db: DbSession,
    olt_id: int | None = Query(default=None),
    olt_code: str | None = Query(default=None),
    environment: str | None = Query(default=None),
) -> DashboardSummary:
    counts = dashboard_counts(db, olt_id=olt_id, olt_code=olt_code, environment=environment)
    onu_service = OnuService(db)
    def latest(task_type: str):
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

    last_sync_onus = latest("sync_onus")
    last_sync_power = latest("sync_power")
    return DashboardSummary(
        **counts,
        low_signal=onu_service.low_signal_count(),
        last_sync_onus=last_sync_onus,
        last_sync_power=last_sync_power,
    )


@router.get("/environment-summary", response_model=DashboardEnvironmentSummary)
def environment_summary(db: DbSession) -> dict:
    return {
        "production": dashboard_environment_stats(db, "production"),
        "lab": dashboard_environment_stats(db, "lab"),
    }
