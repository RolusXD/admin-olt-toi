from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "toi_olt_manager",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks.monitoring"],
)
celery_app.conf.timezone = "America/La_Paz"
