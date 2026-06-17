from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.entities import (
    BackupFile,
    ConfigSnapshot,
    DriverCommandLog,
    EventLog,
    GponProfile,
    ImportJob,
    MonitoringExecution,
    Nap,
    NapPort,
    Olt,
    Onu,
    OnuEventHistory,
    OnuPowerHistory,
    OnuType,
    PonPort,
    ProfileCatalog,
    ProvisioningPlan,
    ProvisioningTemplate,
    ProvisioningValidationResult,
    SpeedProfile,
    UnauthorizedOnu,
    Vlan,
    Zone,
)
from app.repositories.base import Repository


class OltRepository(Repository[Olt]):
    model = Olt


class ZoneRepository(Repository[Zone]):
    model = Zone


class ConfigSnapshotRepository(Repository[ConfigSnapshot]):
    model = ConfigSnapshot


class ImportJobRepository(Repository[ImportJob]):
    model = ImportJob


class VlanRepository(Repository[Vlan]):
    model = Vlan


class GponProfileRepository(Repository[GponProfile]):
    model = GponProfile


class OnuTypeRepository(Repository[OnuType]):
    model = OnuType


class SpeedProfileRepository(Repository[SpeedProfile]):
    model = SpeedProfile


class ProfileCatalogRepository(Repository[ProfileCatalog]):
    model = ProfileCatalog


class NapRepository(Repository[Nap]):
    model = Nap


class NapPortRepository(Repository[NapPort]):
    model = NapPort


class PonPortRepository(Repository[PonPort]):
    model = PonPort


class OnuRepository(Repository[Onu]):
    model = Onu

    def search(self, query: str | None = None) -> list[Onu]:
        statement = select(Onu)
        if query:
            like = f"%{query}%"
            statement = statement.where(
                Onu.customer_name.ilike(like) | Onu.serial_number.ilike(like) | Onu.onu_interface.ilike(like)
            )
        return list(self.db.scalars(statement))


class PowerRepository(Repository[OnuPowerHistory]):
    model = OnuPowerHistory


class UnauthorizedOnuRepository(Repository[UnauthorizedOnu]):
    model = UnauthorizedOnu


class OnuEventHistoryRepository(Repository[OnuEventHistory]):
    model = OnuEventHistory


class ProvisioningTemplateRepository(Repository[ProvisioningTemplate]):
    model = ProvisioningTemplate


class ProvisioningPlanRepository(Repository[ProvisioningPlan]):
    model = ProvisioningPlan


class ProvisioningValidationResultRepository(Repository[ProvisioningValidationResult]):
    model = ProvisioningValidationResult


class DriverCommandLogRepository(Repository[DriverCommandLog]):
    model = DriverCommandLog


class MonitoringExecutionRepository(Repository[MonitoringExecution]):
    model = MonitoringExecution


class EventRepository(Repository[EventLog]):
    model = EventLog


class BackupRepository(Repository[BackupFile]):
    model = BackupFile


def dashboard_counts(
    db: Session,
    olt_id: int | None = None,
    olt_code: str | None = None,
    environment: str | None = None,
) -> dict[str, int]:
    onu_statement = select(Onu)
    unauthorized_statement = select(UnauthorizedOnu)
    if olt_code:
        onu_statement = onu_statement.join(Olt, Onu.olt_id == Olt.id).where(Olt.olt_code == olt_code.strip().upper())
        unauthorized_statement = unauthorized_statement.join(Olt, UnauthorizedOnu.olt_id == Olt.id).where(Olt.olt_code == olt_code.strip().upper())
    if olt_id is not None:
        onu_statement = onu_statement.where(Onu.olt_id == olt_id)
        unauthorized_statement = unauthorized_statement.where(UnauthorizedOnu.olt_id == olt_id)
    if environment:
        env = environment.strip().lower()
        if olt_code:
            onu_statement = onu_statement.where(Olt.environment == env)
            unauthorized_statement = unauthorized_statement.where(Olt.environment == env)
        else:
            onu_statement = onu_statement.join(Olt, Onu.olt_id == Olt.id).where(Olt.environment == env)
            unauthorized_statement = unauthorized_statement.join(Olt, UnauthorizedOnu.olt_id == Olt.id).where(Olt.environment == env)

    total_online = db.scalar(select(func.count()).select_from(onu_statement.where(Onu.status == "online").subquery())) or 0
    total_offline = db.scalar(select(func.count()).select_from(onu_statement.where(Onu.status == "offline").subquery())) or 0
    total_unauthorized = db.scalar(select(func.count()).select_from(onu_statement.where(Onu.status == "unauthorized").subquery())) or 0
    los = db.scalar(select(func.count()).select_from(onu_statement.where(Onu.last_down_cause == "LOS").subquery())) or 0
    dying_gasp = db.scalar(select(func.count()).select_from(onu_statement.where(Onu.last_down_cause == "DyingGasp").subquery())) or 0
    pwr_fail = db.scalar(select(func.count()).select_from(onu_statement.where(Onu.last_down_cause == "PWRFail").subquery())) or 0
    rx_warning = db.scalar(select(func.count()).select_from(onu_statement.where(Onu.signal_status == "warning").subquery())) or 0
    rx_critical = db.scalar(select(func.count()).select_from(onu_statement.where(Onu.signal_status == "critical").subquery())) or 0
    unauthorized_pending = db.scalar(select(func.count()).select_from(unauthorized_statement.where(UnauthorizedOnu.status == "pending").subquery())) or 0
    unauthorized_ignored = db.scalar(select(func.count()).select_from(unauthorized_statement.where(UnauthorizedOnu.status == "ignored").subquery())) or 0
    unauthorized_ready = db.scalar(select(func.count()).select_from(unauthorized_statement.where(UnauthorizedOnu.status == "ready_for_provisioning").subquery())) or 0
    plan_statement = select(ProvisioningPlan)
    if olt_code:
        plan_statement = plan_statement.join(Olt, ProvisioningPlan.olt_id == Olt.id).where(Olt.olt_code == olt_code.strip().upper())
    if olt_id is not None:
        plan_statement = plan_statement.where(ProvisioningPlan.olt_id == olt_id)
    if environment:
        env = environment.strip().lower()
        if not olt_code:
            plan_statement = plan_statement.join(Olt, ProvisioningPlan.olt_id == Olt.id)
        plan_statement = plan_statement.where(Olt.environment == env)
    provisioning_draft = db.scalar(select(func.count()).select_from(plan_statement.where(ProvisioningPlan.status == "draft").subquery())) or 0
    provisioning_validated = db.scalar(select(func.count()).select_from(plan_statement.where(ProvisioningPlan.status == "validated").subquery())) or 0
    provisioning_approved = db.scalar(select(func.count()).select_from(plan_statement.where(ProvisioningPlan.status == "approved").subquery())) or 0
    provisioning_failed = db.scalar(select(func.count()).select_from(plan_statement.where(ProvisioningPlan.status == "validation_failed").subquery())) or 0
    provisioning_cancelled = db.scalar(select(func.count()).select_from(plan_statement.where(ProvisioningPlan.status == "cancelled").subquery())) or 0
    return {
        "online": total_online,
        "offline": total_offline,
        "unauthorized": total_unauthorized,
        "los": los,
        "dying_gasp": dying_gasp,
        "pwr_fail": pwr_fail,
        "rx_warning": rx_warning,
        "rx_critical": rx_critical,
        "unauthorized_pending": unauthorized_pending,
        "unauthorized_ignored": unauthorized_ignored,
        "unauthorized_ready_for_provisioning": unauthorized_ready,
        "provisioning_draft": provisioning_draft,
        "provisioning_validated": provisioning_validated,
        "provisioning_approved": provisioning_approved,
        "provisioning_validation_failed": provisioning_failed,
        "provisioning_cancelled": provisioning_cancelled,
    }


def dashboard_environment_stats(db: Session, environment: str) -> dict[str, int | str]:
    env = environment.strip().lower()
    olts = db.scalar(select(func.count()).select_from(Olt).where(Olt.environment == env)) or 0
    onus = db.scalar(select(func.count()).select_from(Onu).join(Olt, Onu.olt_id == Olt.id).where(Olt.environment == env)) or 0
    online = (
        db.scalar(
            select(func.count())
            .select_from(Onu)
            .join(Olt, Onu.olt_id == Olt.id)
            .where(Olt.environment == env, Onu.status == "online")
        )
        or 0
    )
    return {"environment": env, "olts": olts, "onus": onus, "online": online}
