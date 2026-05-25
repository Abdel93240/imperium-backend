from app.schemas.frontend import ImperiumFrontendNavigationItem, ImperiumFrontendNavigationResponse

IMPERIUM_FRONTEND_NAVIGATION_ITEMS: tuple[ImperiumFrontendNavigationItem, ...] = (
    ImperiumFrontendNavigationItem(
        key="home",
        label="Home",
        route="/home",
        api_endpoint="/api/imperium/home/bootstrap",
        order=10,
        enabled=True,
    ),
    ImperiumFrontendNavigationItem(
        key="dashboard",
        label="Dashboard",
        route="/dashboard",
        api_endpoint="/api/imperium/dashboard",
        order=20,
        enabled=True,
    ),
    ImperiumFrontendNavigationItem(
        key="daily_plan",
        label="Daily Plan",
        route="/daily-plan",
        api_endpoint="/api/imperium/daily-plan",
        order=30,
        enabled=True,
    ),
    ImperiumFrontendNavigationItem(
        key="missions",
        label="Missions",
        route="/missions",
        api_endpoint="/api/imperium/missions/active",
        order=40,
        enabled=True,
    ),
    ImperiumFrontendNavigationItem(
        key="vault",
        label="Vault",
        route="/vault",
        api_endpoint="/api/imperium/vault/summary",
        order=50,
        enabled=True,
    ),
    ImperiumFrontendNavigationItem(
        key="path",
        label="The Path",
        route="/path",
        api_endpoint="/api/imperium/path/today",
        order=60,
        enabled=True,
    ),
    ImperiumFrontendNavigationItem(
        key="pulse",
        label="Pulse",
        route="/pulse",
        api_endpoint="/api/imperium/pulse/today",
        order=70,
        enabled=True,
    ),
)


def get_imperium_frontend_navigation_metadata() -> ImperiumFrontendNavigationResponse:
    return ImperiumFrontendNavigationResponse(
        navigation_version="v1",
        read_only=True,
        items=list(IMPERIUM_FRONTEND_NAVIGATION_ITEMS),
        safe_explanation="Frontend navigation metadata for Imperium.",
    )
