from fastapi import APIRouter

from app.api.routes import alerts, auth, dashboard, events, monitoring, naps, olts, onus, pon_ports, provisioning, unauthorized_onus, vlans, zones
from app.api.routes.import_jobs import router as import_jobs_router

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(dashboard.router)
api_router.include_router(alerts.router)
api_router.include_router(olts.router)
api_router.include_router(zones.router)
api_router.include_router(naps.router)
api_router.include_router(onus.router)
api_router.include_router(vlans.router)
api_router.include_router(pon_ports.router)
api_router.include_router(provisioning.router)
api_router.include_router(unauthorized_onus.router)
api_router.include_router(events.router)
api_router.include_router(monitoring.router)
api_router.include_router(import_jobs_router)
