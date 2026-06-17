from app.core.database import SessionLocal
from app.models.entities import Olt
from app.services.olt_cli_service import OltCliService
from app.tasks.celery_app import celery_app


@celery_app.task
def poll_olt_power() -> str:
    with SessionLocal() as _db:
        return "poll scheduled"


@celery_app.task
def sync_onu_states_task(olt_id: int) -> dict:
    with SessionLocal() as db:
        olt = db.get(Olt, olt_id)
        if not olt:
            return {"olt_id": olt_id, "error": "OLT not found"}
        return OltCliService(db).sync_onus(olt)


@celery_app.task
def sync_onu_power_task(olt_id: int) -> dict:
    with SessionLocal() as db:
        olt = db.get(Olt, olt_id)
        if not olt:
            return {"olt_id": olt_id, "error": "OLT not found"}
        return OltCliService(db).sync_power(olt)
