from app.core.database import SessionLocal
from app.models.entities import Olt
from app.services.olt_cli_service import OltCliService
from app.services.operation_log_service import OperationLogService
from app.services.operator_context_service import OperatorContext
from app.tasks.celery_app import celery_app


@celery_app.task
def poll_olt_power() -> str:
    with SessionLocal() as _db:
        # Tarea placeholder; cuando evolucione a una operaci\u00f3n real de
        # monitoreo podr\u00e1 envolver su l\u00f3gica con OperationLogService.
        return "poll scheduled"


@celery_app.task
def sync_onu_states_task(olt_id: int) -> dict:
    with SessionLocal() as db:
        olt = db.get(Olt, olt_id)
        if not olt:
            return {"olt_id": olt_id, "error": "OLT not found"}

        # En tareas de Scheduler el origin debe ser ``SCHEDULER`` y el rol
        # l\u00f3gico es ``SYSTEM``. No hay usuario humano asociado.
        operator = OperatorContext(user_id=None, user_name="scheduler", role_code="SYSTEM", origin="SCHEDULER")
        log = OperationLogService(db, origin="SCHEDULER")
        ctx = log.start(
            event_type="SCHEDULER_SYNC_ONU_STATES",
            entity_type="olt",
            entity_id=olt.id,
            description=f"Inicio de sincronizacion automatica de estados ONU para OLT {olt.olt_code} - {olt.name}",
            operator=operator,
            action="SCHEDULER.SYNC_ONU_STATES",
        )

        try:
            result = OltCliService(db).sync_onus(olt)
        except Exception as exc:  # pragma: no cover - errores concretos cubiertos en tests de servicio
            log.error(
                ctx,
                event_type="SCHEDULER_SYNC_ONU_STATES",
                entity_type="olt",
                entity_id=olt.id,
                description=(
                    f"Error en sincronizacion automatica de estados ONU "
                    f"para OLT {olt.olt_code} - {olt.name}"
                ),
                action="SCHEDULER.SYNC_ONU_STATES",
                error=str(exc),
            )
            raise

        log.success(
            ctx,
            event_type="SCHEDULER_SYNC_ONU_STATES",
            entity_type="olt",
            entity_id=olt.id,
            description=(
                f"Sincronizacion automatica de estados ONU completada "
                f"para OLT {olt.olt_code} - {olt.name}"
            ),
            action="SCHEDULER.SYNC_ONU_STATES",
        )

        return result


@celery_app.task
def sync_onu_power_task(olt_id: int) -> dict:
    with SessionLocal() as db:
        olt = db.get(Olt, olt_id)
        if not olt:
            return {"olt_id": olt_id, "error": "OLT not found"}

        operator = OperatorContext(user_id=None, user_name="scheduler", role_code="SYSTEM", origin="SCHEDULER")
        log = OperationLogService(db, origin="SCHEDULER")
        ctx = log.start(
            event_type="SCHEDULER_SYNC_ONU_POWER",
            entity_type="olt",
            entity_id=olt.id,
            description=f"Inicio de sincronizacion automatica de potencia ONU para OLT {olt.olt_code} - {olt.name}",
            operator=operator,
            action="SCHEDULER.SYNC_ONU_POWER",
        )

        try:
            result = OltCliService(db).sync_power(olt)
        except Exception as exc:  # pragma: no cover - errores concretos cubiertos en tests de servicio
            log.error(
                ctx,
                event_type="SCHEDULER_SYNC_ONU_POWER",
                entity_type="olt",
                entity_id=olt.id,
                description=(
                    f"Error en sincronizacion automatica de potencia ONU "
                    f"para OLT {olt.olt_code} - {olt.name}"
                ),
                action="SCHEDULER.SYNC_ONU_POWER",
                error=str(exc),
            )
            raise

        log.success(
            ctx,
            event_type="SCHEDULER_SYNC_ONU_POWER",
            entity_type="olt",
            entity_id=olt.id,
            description=(
                f"Sincronizacion automatica de potencia ONU completada "
                f"para OLT {olt.olt_code} - {olt.name}"
            ),
            action="SCHEDULER.SYNC_ONU_POWER",
        )

        return result
