from fastapi import APIRouter

from app.api.v1.routes import (
    ai,
    ai_advanced,
    ai_logs,
    auth,
    daily,
    devices,
    events,
    imperium_frontend,
    health,
    imperium_daily_plan,
    imperium_contracts,
    imperium_home,
    imperium_operations,
    imperium_history,
    imperium_settings,
    imperium,
    imperium_dashboard,
    imperium_path,
    imperium_path_calendar,
    imperium_path_dashboard,
    imperium_path_devotion,
    imperium_path_ghusl,
    imperium_path_invocations,
    imperium_path_mosques,
    imperium_path_settings,
    imperium_path_sadaqa,
    imperium_path_worship,
    imperium_pulse,
    imperium_pulse_dashboard,
    imperium_pulse_equipment,
    imperium_pulse_health,
    imperium_pulse_hydration,
    imperium_pulse_meals,
    imperium_pulse_signals,
    imperium_pulse_stock,
    imperium_pulse_training,
    imperium_pulse_workouts,
    imperium_vault,
    imperium_vector,
    imperium_vault_categories,
    imperium_vault_receipts,
    internal,
    knowledge_inbox,
    vault,
    wr,
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(ai.router, prefix="/ai", tags=["ai"])
api_router.include_router(ai_logs.router, prefix="/ai", tags=["ai-logs"])
api_router.include_router(ai_advanced.router, prefix="/ai/advanced", tags=["ai-advanced"])
api_router.include_router(knowledge_inbox.router, prefix="/ai/knowledge-inbox", tags=["knowledge-inbox"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(devices.router, prefix="/auth/devices", tags=["devices"])
api_router.include_router(events.router, prefix="/events", tags=["events"])
api_router.include_router(imperium_dashboard.router, prefix="/imperium", tags=["imperium-dashboard"])
api_router.include_router(imperium_daily_plan.router, prefix="/imperium", tags=["imperium-daily-plan"])
api_router.include_router(imperium_contracts.router, prefix="/imperium", tags=["imperium-contracts"])
api_router.include_router(imperium_home.router, prefix="/imperium", tags=["imperium-home"])
api_router.include_router(imperium_frontend.router, prefix="/imperium", tags=["imperium-frontend"])
api_router.include_router(imperium_path.router, prefix="/imperium/path", tags=["imperium-path"])
api_router.include_router(imperium_path_worship.router, prefix="/imperium/path", tags=["imperium-path"])
api_router.include_router(imperium_path_sadaqa.router, prefix="/imperium/path", tags=["imperium-path"])
api_router.include_router(imperium_path_ghusl.router, prefix="/imperium/path", tags=["imperium-path"])
api_router.include_router(imperium_path_mosques.router, prefix="/imperium/path", tags=["imperium-path"])
api_router.include_router(imperium_path_invocations.router, prefix="/imperium/path", tags=["imperium-path"])
api_router.include_router(imperium_path_settings.router, prefix="/imperium/path", tags=["imperium-path"])
api_router.include_router(imperium_path_devotion.router, prefix="/imperium/path", tags=["imperium-path"])
api_router.include_router(imperium_path_dashboard.router, prefix="/imperium/path", tags=["imperium-path"])
api_router.include_router(imperium_path_calendar.router, prefix="/imperium/path", tags=["imperium-path"])
api_router.include_router(imperium_pulse.router, prefix="/imperium/pulse", tags=["imperium-pulse"])
api_router.include_router(imperium_pulse_stock.router, prefix="/imperium/pulse", tags=["imperium-pulse-stock"])
api_router.include_router(imperium_pulse_meals.router, prefix="/imperium/pulse", tags=["imperium-pulse-meals"])
api_router.include_router(imperium_pulse_hydration.router, prefix="/imperium/pulse", tags=["imperium-pulse-hydration"])
api_router.include_router(imperium_pulse_dashboard.router, prefix="/imperium/pulse", tags=["imperium-pulse-dashboard"])
api_router.include_router(imperium_pulse_workouts.router, prefix="/imperium/pulse", tags=["imperium-pulse-workouts"])
api_router.include_router(imperium_pulse_equipment.router, prefix="/imperium/pulse", tags=["imperium-pulse-equipment"])
api_router.include_router(imperium_pulse_health.router, prefix="/imperium/pulse", tags=["imperium-pulse-health"])
api_router.include_router(imperium_pulse_signals.router, prefix="/imperium/pulse", tags=["imperium-pulse-signals"])
api_router.include_router(imperium_pulse_training.router, prefix="/imperium/pulse", tags=["imperium-pulse-training"])
api_router.include_router(imperium.router, prefix="/imperium", tags=["imperium"])
api_router.include_router(imperium_operations.router, prefix="/imperium", tags=["imperium-operations"])
api_router.include_router(imperium_settings.router, prefix="/imperium", tags=["imperium-settings"])
api_router.include_router(imperium_history.router, prefix="/imperium", tags=["imperium-history"])
api_router.include_router(imperium_vault.router, prefix="/imperium/vault", tags=["imperium-vault"])
api_router.include_router(imperium_vector.router, prefix="/imperium/vector", tags=["imperium-vector"])
api_router.include_router(imperium_vault_categories.router, prefix="/imperium/vault", tags=["imperium-vault-categories"])
api_router.include_router(imperium_vault_receipts.router, prefix="/imperium/vault", tags=["imperium-vault-receipts"])
api_router.include_router(vault.router, prefix="/vault", tags=["vault"])
api_router.include_router(wr.router, prefix="/wr", tags=["wr"])
api_router.include_router(daily.router, prefix="/daily", tags=["daily"])
api_router.include_router(internal.router, prefix="/internal", tags=["internal"])
