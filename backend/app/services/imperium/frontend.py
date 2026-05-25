from app.schemas.frontend import (
    ImperiumFrontendLayoutRegion,
    ImperiumFrontendLayoutResponse,
    ImperiumFrontendLayoutShell,
    ImperiumFrontendNavigationItem,
    ImperiumFrontendNavigationResponse,
)

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


IMPERIUM_FRONTEND_LAYOUT_REGIONS: tuple[ImperiumFrontendLayoutRegion, ...] = (
    ImperiumFrontendLayoutRegion(
        key="hero",
        purpose="Primary daily focus area.",
        order=10,
        enabled=True,
    ),
    ImperiumFrontendLayoutRegion(
        key="mission",
        purpose="Active mission overview.",
        order=20,
        enabled=True,
    ),
    ImperiumFrontendLayoutRegion(
        key="daily_plan",
        purpose="Daily plan snapshot.",
        order=30,
        enabled=True,
    ),
    ImperiumFrontendLayoutRegion(
        key="path",
        purpose="Path today status.",
        order=40,
        enabled=True,
    ),
    ImperiumFrontendLayoutRegion(
        key="pulse",
        purpose="Pulse today status.",
        order=50,
        enabled=True,
    ),
    ImperiumFrontendLayoutRegion(
        key="vault",
        purpose="Vault summary.",
        order=60,
        enabled=True,
    ),
)


def get_imperium_frontend_layout_metadata() -> ImperiumFrontendLayoutResponse:
    return ImperiumFrontendLayoutResponse(
        layout_version="v1",
        read_only=True,
        **{
            "shell": ImperiumFrontendLayoutShell(
                style="imperium_luxury",
                density="compact",
                navigation_position="bottom",
                primary_surface="dashboard",
            )
        },
        regions=list(IMPERIUM_FRONTEND_LAYOUT_REGIONS),
        safe_explanation="Frontend layout metadata for Imperium V1.",
    )
