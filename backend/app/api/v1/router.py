from fastapi import APIRouter

from app.api.v1.routes import (
    ai,
    auth,
    devices,
    events,
    health,
    imperium_daily_plan,
    imperium,
    imperium_dashboard,
    imperium_path,
    imperium_pulse,
    imperium_vault,
    internal,
    vault,
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(ai.router, prefix="/ai", tags=["ai"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(devices.router, prefix="/auth/devices", tags=["devices"])
api_router.include_router(events.router, prefix="/events", tags=["events"])
api_router.include_router(imperium_dashboard.router, prefix="/imperium", tags=["imperium-dashboard"])
api_router.include_router(imperium_daily_plan.router, prefix="/imperium", tags=["imperium-daily-plan"])
api_router.include_router(imperium_path.router, prefix="/imperium/path", tags=["imperium-path"])
api_router.include_router(imperium_pulse.router, prefix="/imperium/pulse", tags=["imperium-pulse"])
api_router.include_router(imperium.router, prefix="/imperium", tags=["imperium"])
api_router.include_router(imperium_vault.router, prefix="/imperium/vault", tags=["imperium-vault"])
api_router.include_router(vault.router, prefix="/vault", tags=["vault"])
api_router.include_router(internal.router, prefix="/internal", tags=["internal"])
