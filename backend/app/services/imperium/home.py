from app.schemas.home import HomeBootstrapModule, HomeBootstrapResponse

HOME_BOOTSTRAP_MODULES: tuple[HomeBootstrapModule, ...] = (
    HomeBootstrapModule(name="dashboard", status="available", primary_endpoint="/api/imperium/dashboard"),
    HomeBootstrapModule(name="daily_plan", status="available", primary_endpoint="/api/imperium/daily-plan"),
    HomeBootstrapModule(name="mission", status="available", primary_endpoint="/api/imperium/missions/active"),
    HomeBootstrapModule(name="vault", status="available", primary_endpoint="/api/imperium/vault/summary"),
    HomeBootstrapModule(name="path", status="available", primary_endpoint="/api/imperium/path/today"),
    HomeBootstrapModule(name="pulse", status="available", primary_endpoint="/api/imperium/pulse/today"),
)


def get_home_bootstrap_metadata() -> HomeBootstrapResponse:
    return HomeBootstrapResponse(
        backend_version="v1",
        read_only=True,
        modules=list(HOME_BOOTSTRAP_MODULES),
        safe_explanation="Imperium home bootstrap metadata for the current user.",
    )
