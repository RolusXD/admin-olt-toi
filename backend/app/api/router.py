from fastapi import APIRouter

from app.api.routes import (
    admin,
    alerts,
    auth,
    dashboard,
    events,
    monitoring,
    nap_ports,
    naps,
    olts,
    onus,
    onu_service_modes,
    onu_types,
    pon_ports,
    profile_catalogs,
    provisioning,
    provisioning_templates,
    speed_profiles,
    territorial,
    unauthorized_onus,
    vlans,
    zones,
)
from app.api.routes.import_jobs import router as import_jobs_router

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(dashboard.router)
api_router.include_router(alerts.router)
api_router.include_router(admin.router)
api_router.include_router(olts.router)
api_router.include_router(zones.router)
api_router.include_router(naps.router)
api_router.include_router(nap_ports.router)
api_router.include_router(onus.router)
api_router.include_router(onu_service_modes.router)
api_router.include_router(onu_types.router)
api_router.include_router(vlans.router)
api_router.include_router(pon_ports.router)
api_router.include_router(profile_catalogs.router)
api_router.include_router(provisioning.router)
api_router.include_router(provisioning_templates.router)
api_router.include_router(speed_profiles.router)
api_router.include_router(unauthorized_onus.router)
api_router.include_router(events.router)
api_router.include_router(monitoring.router)
api_router.include_router(import_jobs_router)
api_router.include_router(territorial.router)
