from app.schemas.frontend import (
    ImperiumFrontendAssetRegistryGroup,
    ImperiumFrontendAssetRegistryItem,
    ImperiumFrontendAssetRegistryPlaceholderPolicy,
    ImperiumFrontendAssetRegistryResponse,
    ImperiumFrontendActionItem,
    ImperiumFrontendAppManifestResponse,
    ImperiumFrontendApplicationMetadata,
    ImperiumFrontendActionsResponse,
    ImperiumFrontendDesignDirection,
    ImperiumFrontendDesignHandoffResponse,
    ImperiumFrontendEmptyStateItem,
    ImperiumFrontendEmptyStatesResponse,
    ImperiumFrontendLayoutRegion,
    ImperiumFrontendLayoutResponse,
    ImperiumFrontendLayoutShell,
    ImperiumFrontendModuleCardItem,
    ImperiumFrontendModuleCardsResponse,
    ImperiumFrontendNavigationItem,
    ImperiumFrontendNavigationResponse,
    ImperiumFrontendThemePalette,
    ImperiumFrontendThemeScaleItem,
    ImperiumFrontendThemeSurface,
    ImperiumFrontendThemeTokensResponse,
    ImperiumFrontendThemeTypographyItem,
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


IMPERIUM_FRONTEND_THEME_SURFACES: tuple[ImperiumFrontendThemeSurface, ...] = (
    ImperiumFrontendThemeSurface.model_validate(
        {"key": "base", "purpose": "Main application background.", "token": "surface.base"}
    ),
    ImperiumFrontendThemeSurface.model_validate(
        {"key": "card", "purpose": "Primary content card surface.", "token": "surface.card"}
    ),
    ImperiumFrontendThemeSurface.model_validate(
        {"key": "elevated", "purpose": "Elevated premium panel surface.", "token": "surface.elevated"}
    ),
)

IMPERIUM_FRONTEND_THEME_SPACING: tuple[ImperiumFrontendThemeScaleItem, ...] = (
    ImperiumFrontendThemeScaleItem(key="xs", value=4),
    ImperiumFrontendThemeScaleItem(key="sm", value=8),
    ImperiumFrontendThemeScaleItem(key="md", value=12),
    ImperiumFrontendThemeScaleItem(key="lg", value=16),
    ImperiumFrontendThemeScaleItem(key="xl", value=24),
)

IMPERIUM_FRONTEND_THEME_RADIUS: tuple[ImperiumFrontendThemeScaleItem, ...] = (
    ImperiumFrontendThemeScaleItem(key="sm", value=8),
    ImperiumFrontendThemeScaleItem(key="md", value=14),
    ImperiumFrontendThemeScaleItem(key="lg", value=20),
    ImperiumFrontendThemeScaleItem(key="xl", value=28),
)

IMPERIUM_FRONTEND_THEME_TYPOGRAPHY: tuple[ImperiumFrontendThemeTypographyItem, ...] = (
    ImperiumFrontendThemeTypographyItem(key="caption", purpose="Compact metadata labels."),
    ImperiumFrontendThemeTypographyItem(key="body", purpose="Default readable body text."),
    ImperiumFrontendThemeTypographyItem(key="title", purpose="Section titles."),
    ImperiumFrontendThemeTypographyItem(key="hero", purpose="Primary dashboard focus text."),
)


def get_imperium_frontend_theme_tokens_metadata() -> ImperiumFrontendThemeTokensResponse:
    return ImperiumFrontendThemeTokensResponse(
        theme_version="v1",
        read_only=True,
        style_name="imperium_luxury",
        palette=ImperiumFrontendThemePalette(
            background="matte_black",
            surface="deep_blue_black",
            primary="champagne_gold",
            secondary="premium_green",
            danger="controlled_red",
            muted="warm_gray",
        ),
        surfaces=list(IMPERIUM_FRONTEND_THEME_SURFACES),
        spacing_scale=list(IMPERIUM_FRONTEND_THEME_SPACING),
        radius_scale=list(IMPERIUM_FRONTEND_THEME_RADIUS),
        typography_scale=list(IMPERIUM_FRONTEND_THEME_TYPOGRAPHY),
        safe_explanation="Frontend theme token metadata for Imperium V1.",
    )


IMPERIUM_FRONTEND_EMPTY_STATE_ITEMS: tuple[ImperiumFrontendEmptyStateItem, ...] = (
    ImperiumFrontendEmptyStateItem(
        key="no_active_mission",
        module="mission",
        title="No active mission",
        message="Create or promote a mission to focus your day.",
        primary_action_label="Open missions",
        primary_route="/missions",
    ),
    ImperiumFrontendEmptyStateItem(
        key="no_vault_transactions",
        module="vault",
        title="No transactions yet",
        message="Add your first income or expense to start tracking your finances.",
        primary_action_label="Open Vault",
        primary_route="/vault",
    ),
    ImperiumFrontendEmptyStateItem(
        key="no_path_habits",
        module="path",
        title="No habits yet",
        message="Create your first habit to build discipline.",
        primary_action_label="Open The Path",
        primary_route="/path",
    ),
    ImperiumFrontendEmptyStateItem(
        key="no_pulse_entry",
        module="pulse",
        title="No Pulse entry today",
        message="Log your sleep, energy, fatigue, weight, or workout for today.",
        primary_action_label="Open Pulse",
        primary_route="/pulse",
    ),
)


def get_imperium_frontend_empty_states_metadata() -> ImperiumFrontendEmptyStatesResponse:
    return ImperiumFrontendEmptyStatesResponse(
        empty_states_version="v1",
        read_only=True,
        items=list(IMPERIUM_FRONTEND_EMPTY_STATE_ITEMS),
        safe_explanation="Frontend empty state metadata for Imperium V1.",
    )


IMPERIUM_FRONTEND_ACTION_ITEMS: tuple[ImperiumFrontendActionItem, ...] = (
    ImperiumFrontendActionItem(
        key="open_missions",
        label="Open missions",
        module="mission",
        action_type="navigate",
        route="/missions",
        requires_confirmation=False,
    ),
    ImperiumFrontendActionItem(
        key="open_vault",
        label="Open Vault",
        module="vault",
        action_type="navigate",
        route="/vault",
        requires_confirmation=False,
    ),
    ImperiumFrontendActionItem(
        key="open_path",
        label="Open The Path",
        module="path",
        action_type="navigate",
        route="/path",
        requires_confirmation=False,
    ),
    ImperiumFrontendActionItem(
        key="open_pulse",
        label="Open Pulse",
        module="pulse",
        action_type="navigate",
        route="/pulse",
        requires_confirmation=False,
    ),
    ImperiumFrontendActionItem(
        key="open_daily_plan",
        label="Open Daily Plan",
        module="daily_plan",
        action_type="navigate",
        route="/daily-plan",
        requires_confirmation=False,
    ),
    ImperiumFrontendActionItem(
        key="open_dashboard",
        label="Open Dashboard",
        module="dashboard",
        action_type="navigate",
        route="/dashboard",
        requires_confirmation=False,
    ),
)

IMPERIUM_FRONTEND_APP_MANIFEST_ENDPOINTS: tuple[str, ...] = (
    "/api/imperium/home/bootstrap",
    "/api/imperium/contracts/index",
    "/api/imperium/contracts/compliance",
    "/api/imperium/frontend/navigation",
    "/api/imperium/frontend/layout",
    "/api/imperium/frontend/theme-tokens",
    "/api/imperium/frontend/empty-states",
    "/api/imperium/frontend/actions",
    "/api/imperium/frontend/module-cards",
    "/api/imperium/frontend/asset-registry",
    "/api/imperium/frontend/app-manifest",
    "/api/imperium/frontend/design-handoff",
)

IMPERIUM_FRONTEND_DESIGN_HANDOFF_METADATA_ENDPOINTS: tuple[str, ...] = (
    "/api/imperium/frontend/navigation",
    "/api/imperium/frontend/layout",
    "/api/imperium/frontend/theme-tokens",
    "/api/imperium/frontend/empty-states",
    "/api/imperium/frontend/actions",
    "/api/imperium/frontend/module-cards",
    "/api/imperium/frontend/asset-registry",
    "/api/imperium/frontend/app-manifest",
    "/api/imperium/frontend/design-handoff",
)


def get_imperium_frontend_app_manifest_metadata() -> ImperiumFrontendAppManifestResponse:
    return ImperiumFrontendAppManifestResponse(
        manifest_version="v1",
        read_only=True,
        application=ImperiumFrontendApplicationMetadata(
            name="Imperium",
            tagline="Personal command center.",
            default_route="/dashboard",
            default_locale="fr-FR",
            default_timezone="Europe/Paris",
        ),
        frontend_metadata_endpoints=list(IMPERIUM_FRONTEND_APP_MANIFEST_ENDPOINTS),
        safe_explanation="Frontend application manifest metadata for Imperium V1.",
    )


def get_imperium_frontend_actions_metadata() -> ImperiumFrontendActionsResponse:
    return ImperiumFrontendActionsResponse(
        actions_version="v1",
        read_only=True,
        items=list(IMPERIUM_FRONTEND_ACTION_ITEMS),
        safe_explanation="Frontend action registry metadata for Imperium V1.",
    )


IMPERIUM_FRONTEND_MODULE_CARD_ITEMS: tuple[ImperiumFrontendModuleCardItem, ...] = (
    ImperiumFrontendModuleCardItem(
        key="dashboard",
        title="Dashboard",
        subtitle="Your command snapshot.",
        route="/dashboard",
        primary_endpoint="/api/imperium/dashboard",
        order=10,
        enabled=True,
    ),
    ImperiumFrontendModuleCardItem(
        key="daily_plan",
        title="Daily Plan",
        subtitle="Your day at a glance.",
        route="/daily-plan",
        primary_endpoint="/api/imperium/daily-plan",
        order=20,
        enabled=True,
    ),
    ImperiumFrontendModuleCardItem(
        key="mission",
        title="Missions",
        subtitle="Focus and execution.",
        route="/missions",
        primary_endpoint="/api/imperium/missions/active",
        order=30,
        enabled=True,
    ),
    ImperiumFrontendModuleCardItem(
        key="vault",
        title="Vault",
        subtitle="Money and ledger.",
        route="/vault",
        primary_endpoint="/api/imperium/vault/summary",
        order=40,
        enabled=True,
    ),
    ImperiumFrontendModuleCardItem(
        key="path",
        title="The Path",
        subtitle="Habits and discipline.",
        route="/path",
        primary_endpoint="/api/imperium/path/today",
        order=50,
        enabled=True,
    ),
    ImperiumFrontendModuleCardItem(
        key="pulse",
        title="Pulse",
        subtitle="Body and energy.",
        route="/pulse",
        primary_endpoint="/api/imperium/pulse/today",
        order=60,
        enabled=True,
    ),
)


def get_imperium_frontend_module_cards_metadata() -> ImperiumFrontendModuleCardsResponse:
    return ImperiumFrontendModuleCardsResponse(
        module_cards_version="v1",
        read_only=True,
        items=list(IMPERIUM_FRONTEND_MODULE_CARD_ITEMS),
        safe_explanation="Frontend module card metadata for Imperium V1.",
    )


def _asset_registry_item(
    key: str,
    label: str,
    asset_type: str,
    expected_filename: str,
    usage: str,
) -> ImperiumFrontendAssetRegistryItem:
    return ImperiumFrontendAssetRegistryItem(
        key=key,
        label=label,
        asset_type=asset_type,
        expected_filename=expected_filename,
        usage=usage,
        status="expected",
        placeholder_allowed=True,
    )


def _asset_registry_group(
    key: str,
    label: str,
    base_path: str,
    items: tuple[ImperiumFrontendAssetRegistryItem, ...],
) -> ImperiumFrontendAssetRegistryGroup:
    return ImperiumFrontendAssetRegistryGroup(
        key=key,
        label=label,
        base_path=base_path,
        items=list(items),
    )


IMPERIUM_FRONTEND_ASSET_REGISTRY_PLACEHOLDER_POLICY = ImperiumFrontendAssetRegistryPlaceholderPolicy(
    placeholder_allowed=True,
    placeholder_style="semantic_luxury_placeholder",
    safe_explanation="Final PNG/SVG assets may be provided later; placeholders are allowed during UI assembly.",
)

IMPERIUM_FRONTEND_ASSET_REGISTRY_GROUPS: tuple[ImperiumFrontendAssetRegistryGroup, ...] = (
    _asset_registry_group(
        key="core",
        label="Core Brand Assets",
        base_path="/assets/imperium/core",
        items=(
            _asset_registry_item(
                key="imperium_emblem",
                label="Imperium Emblem",
                asset_type="svg",
                expected_filename="imperium_emblem.svg",
                usage="Main brand emblem.",
            ),
            _asset_registry_item(
                key="imperium_wordmark",
                label="Imperium Wordmark",
                asset_type="svg",
                expected_filename="imperium_wordmark.svg",
                usage="Main brand wordmark.",
            ),
            _asset_registry_item(
                key="imperium_symbol_mini",
                label="Imperium Symbol Mini",
                asset_type="svg",
                expected_filename="imperium_symbol_mini.svg",
                usage="Compact brand symbol.",
            ),
            _asset_registry_item(
                key="premium_divider",
                label="Premium Divider",
                asset_type="svg",
                expected_filename="premium_divider.svg",
                usage="Luxury section divider.",
            ),
            _asset_registry_item(
                key="gold_frame",
                label="Gold Frame",
                asset_type="svg",
                expected_filename="gold_frame.svg",
                usage="Premium framing element.",
            ),
            _asset_registry_item(
                key="corner_ornament",
                label="Corner Ornament",
                asset_type="svg",
                expected_filename="corner_ornament.svg",
                usage="Decorative corner detail.",
            ),
        ),
    ),
    _asset_registry_group(
        key="navigation",
        label="Navigation Icons",
        base_path="/assets/imperium/navigation",
        items=(
            _asset_registry_item("nav_home", "Home Navigation Icon", "svg", "nav_home.svg", "Home navigation item."),
            _asset_registry_item(
                "nav_dashboard",
                "Dashboard Navigation Icon",
                "svg",
                "nav_dashboard.svg",
                "Dashboard navigation item.",
            ),
            _asset_registry_item(
                "nav_daily_plan",
                "Daily Plan Navigation Icon",
                "svg",
                "nav_daily_plan.svg",
                "Daily plan navigation item.",
            ),
            _asset_registry_item(
                "nav_missions",
                "Missions Navigation Icon",
                "svg",
                "nav_missions.svg",
                "Missions navigation item.",
            ),
            _asset_registry_item("nav_vault", "Vault Navigation Icon", "svg", "nav_vault.svg", "Vault navigation item."),
            _asset_registry_item("nav_path", "Path Navigation Icon", "svg", "nav_path.svg", "Path navigation item."),
            _asset_registry_item("nav_pulse", "Pulse Navigation Icon", "svg", "nav_pulse.svg", "Pulse navigation item."),
            _asset_registry_item("nav_vector", "Vector Navigation Icon", "svg", "nav_vector.svg", "Vector navigation item."),
            _asset_registry_item(
                "nav_settings",
                "Settings Navigation Icon",
                "svg",
                "nav_settings.svg",
                "Settings navigation item.",
            ),
        ),
    ),
    _asset_registry_group(
        key="dashboard",
        label="Dashboard Assets",
        base_path="/assets/imperium/dashboard",
        items=(
            _asset_registry_item(
                "dashboard_hero_frame",
                "Dashboard Hero Frame",
                "svg",
                "dashboard_hero_frame.svg",
                "Dashboard hero frame.",
            ),
            _asset_registry_item(
                "dashboard_focus_card",
                "Dashboard Focus Card",
                "svg",
                "dashboard_focus_card.svg",
                "Dashboard focus card.",
            ),
            _asset_registry_item(
                "dashboard_kpi_card",
                "Dashboard KPI Card",
                "svg",
                "dashboard_kpi_card.svg",
                "Dashboard KPI card.",
            ),
            _asset_registry_item(
                "dashboard_readiness_ring",
                "Dashboard Readiness Ring",
                "svg",
                "dashboard_readiness_ring.svg",
                "Dashboard readiness ring.",
            ),
        ),
    ),
    _asset_registry_group(
        key="modules",
        label="Module Card Assets",
        base_path="/assets/imperium/modules",
        items=(
            _asset_registry_item("module_card_frame", "Module Card Frame", "svg", "module_card_frame.svg", "Module card frame."),
            _asset_registry_item(
                "module_card_active_glow",
                "Module Card Active Glow",
                "svg",
                "module_card_active_glow.svg",
                "Active module card glow.",
            ),
            _asset_registry_item(
                "module_card_empty_state",
                "Module Card Empty State",
                "svg",
                "module_card_empty_state.svg",
                "Empty module card state.",
            ),
            _asset_registry_item(
                "module_card_locked_state",
                "Module Card Locked State",
                "svg",
                "module_card_locked_state.svg",
                "Locked module card state.",
            ),
        ),
    ),
    _asset_registry_group(
        key="vault",
        label="Vault Assets",
        base_path="/assets/imperium/vault",
        items=(
            _asset_registry_item("vault_emblem", "Vault Emblem", "svg", "vault_emblem.svg", "Vault emblem."),
            _asset_registry_item("vault_income", "Vault Income", "svg", "vault_income.svg", "Income indicator."),
            _asset_registry_item("vault_expense", "Vault Expense", "svg", "vault_expense.svg", "Expense indicator."),
            _asset_registry_item("vault_ledger", "Vault Ledger", "svg", "vault_ledger.svg", "Vault ledger."),
            _asset_registry_item("vault_pressure", "Vault Pressure", "svg", "vault_pressure.svg", "Financial pressure visual."),
            _asset_registry_item(
                "vault_receipt_scan",
                "Vault Receipt Scan",
                "svg",
                "vault_receipt_scan.svg",
                "Receipt scan affordance.",
            ),
        ),
    ),
    _asset_registry_group(
        key="path",
        label="Path Assets",
        base_path="/assets/imperium/path",
        items=(
            _asset_registry_item("path_arch_emblem", "Path Arch Emblem", "svg", "path_arch_emblem.svg", "Path arch emblem."),
            _asset_registry_item("path_wordmark", "Path Wordmark", "svg", "path_wordmark.svg", "Path wordmark."),
            _asset_registry_item("path_habit", "Path Habit", "svg", "path_habit.svg", "Habit asset."),
            _asset_registry_item("path_check", "Path Check", "svg", "path_check.svg", "Check-in asset."),
            _asset_registry_item(
                "path_reflection",
                "Path Reflection",
                "svg",
                "path_reflection.svg",
                "Reflection asset.",
            ),
            _asset_registry_item(
                "path_spiritual_divider",
                "Path Spiritual Divider",
                "svg",
                "path_spiritual_divider.svg",
                "Spiritual section divider.",
            ),
        ),
    ),
    _asset_registry_group(
        key="pulse",
        label="Pulse Assets",
        base_path="/assets/imperium/pulse",
        items=(
            _asset_registry_item("pulse_emblem", "Pulse Emblem", "svg", "pulse_emblem.svg", "Pulse emblem."),
            _asset_registry_item("pulse_sleep", "Pulse Sleep", "svg", "pulse_sleep.svg", "Sleep indicator."),
            _asset_registry_item("pulse_energy", "Pulse Energy", "svg", "pulse_energy.svg", "Energy indicator."),
            _asset_registry_item("pulse_fatigue", "Pulse Fatigue", "svg", "pulse_fatigue.svg", "Fatigue indicator."),
            _asset_registry_item("pulse_workout", "Pulse Workout", "svg", "pulse_workout.svg", "Workout indicator."),
            _asset_registry_item("pulse_weight", "Pulse Weight", "svg", "pulse_weight.svg", "Weight indicator."),
        ),
    ),
    _asset_registry_group(
        key="vector",
        label="Vector Assets",
        base_path="/assets/imperium/vector",
        items=(
            _asset_registry_item("vector_emblem", "Vector Emblem", "svg", "vector_emblem.svg", "Vector emblem."),
            _asset_registry_item("vector_car", "Vector Car", "svg", "vector_car.svg", "Driver vehicle asset."),
            _asset_registry_item("vector_zone", "Vector Zone", "svg", "vector_zone.svg", "Zone asset."),
            _asset_registry_item("vector_demand", "Vector Demand", "svg", "vector_demand.svg", "Demand asset."),
            _asset_registry_item("vector_traffic", "Vector Traffic", "svg", "vector_traffic.svg", "Traffic asset."),
            _asset_registry_item("vector_train", "Vector Train", "svg", "vector_train.svg", "Train disruption asset."),
            _asset_registry_item("vector_event", "Vector Event", "svg", "vector_event.svg", "Event asset."),
        ),
    ),
    _asset_registry_group(
        key="weekly_review",
        label="Weekly Review Assets",
        base_path="/assets/imperium/weekly-review",
        items=(
            _asset_registry_item("wr_emblem", "Weekly Review Emblem", "svg", "wr_emblem.svg", "Weekly review emblem."),
            _asset_registry_item("wr_report", "Weekly Review Report", "svg", "wr_report.svg", "Weekly report asset."),
            _asset_registry_item("wr_timeline", "Weekly Review Timeline", "svg", "wr_timeline.svg", "Timeline asset."),
            _asset_registry_item("wr_summary", "Weekly Review Summary", "svg", "wr_summary.svg", "Summary asset."),
            _asset_registry_item("wr_reflection", "Weekly Review Reflection", "svg", "wr_reflection.svg", "Reflection asset."),
        ),
    ),
    _asset_registry_group(
        key="states",
        label="State Assets",
        base_path="/assets/imperium/states",
        items=(
            _asset_registry_item("state_loading", "Loading State", "svg", "state_loading.svg", "Loading state."),
            _asset_registry_item("state_empty", "Empty State", "svg", "state_empty.svg", "Empty state."),
            _asset_registry_item("state_locked", "Locked State", "svg", "state_locked.svg", "Locked state."),
            _asset_registry_item("state_error", "Error State", "svg", "state_error.svg", "Error state."),
        ),
    ),
    _asset_registry_group(
        key="backgrounds",
        label="Background Assets",
        base_path="/assets/imperium/backgrounds",
        items=(
            _asset_registry_item(
                "background_dashboard_gradient",
                "Dashboard Background Gradient",
                "png",
                "background_dashboard_gradient.png",
                "Dashboard background texture.",
            ),
            _asset_registry_item(
                "background_daily_plan_gradient",
                "Daily Plan Background Gradient",
                "png",
                "background_daily_plan_gradient.png",
                "Daily plan background texture.",
            ),
            _asset_registry_item(
                "background_vault_texture",
                "Vault Background Texture",
                "png",
                "background_vault_texture.png",
                "Vault background texture.",
            ),
            _asset_registry_item(
                "background_path_light",
                "Path Background Light",
                "png",
                "background_path_light.png",
                "Path background light.",
            ),
            _asset_registry_item(
                "background_pulse_light",
                "Pulse Background Light",
                "png",
                "background_pulse_light.png",
                "Pulse background light.",
            ),
        ),
    ),
    _asset_registry_group(
        key="overlays",
        label="Overlay Assets",
        base_path="/assets/imperium/overlays",
        items=(
            _asset_registry_item("overlay_gold_noise", "Gold Noise Overlay", "png", "overlay_gold_noise.png", "Gold noise overlay."),
            _asset_registry_item(
                "overlay_corner_vignette",
                "Corner Vignette Overlay",
                "png",
                "overlay_corner_vignette.png",
                "Corner vignette overlay.",
            ),
            _asset_registry_item(
                "overlay_glass_blur",
                "Glass Blur Overlay",
                "png",
                "overlay_glass_blur.png",
                "Glass blur overlay.",
            ),
            _asset_registry_item(
                "overlay_focus_rim",
                "Focus Rim Overlay",
                "png",
                "overlay_focus_rim.png",
                "Focus rim overlay.",
            ),
        ),
    ),
)


def get_imperium_frontend_asset_registry_metadata() -> ImperiumFrontendAssetRegistryResponse:
    return ImperiumFrontendAssetRegistryResponse(
        asset_registry_version="v1",
        read_only=True,
        asset_base_path="/assets/imperium",
        placeholder_policy=IMPERIUM_FRONTEND_ASSET_REGISTRY_PLACEHOLDER_POLICY,
        groups=list(IMPERIUM_FRONTEND_ASSET_REGISTRY_GROUPS),
        safe_explanation="Frontend asset registry metadata for Imperium V1.",
    )


IMPERIUM_FRONTEND_DESIGN_HANDOFF_SUPPORTED_MODULES: tuple[str, ...] = (
    "dashboard",
    "daily_plan",
    "mission",
    "vault",
    "path",
    "pulse",
    "vector",
    "weekly_review",
)

IMPERIUM_FRONTEND_DESIGN_HANDOFF_ASSET_GROUPS: tuple[str, ...] = (
    "core",
    "navigation",
    "dashboard",
    "modules",
    "vault",
    "path",
    "pulse",
    "vector",
    "weekly_review",
    "states",
    "backgrounds",
    "overlays",
)

IMPERIUM_FRONTEND_DESIGN_HANDOFF_RULES: tuple[str, ...] = (
    "design_handoff_only",
    "metadata_only_frontend_contracts",
    "static_deterministic_v1",
    "declared_metadata_no_runtime_dis" + "covery",
    "declared_asset_groups_no_runtime_inventory",
    "no_frontend_rendering",
    "no_generated_frontend_code",
    "placeholders_allowed",
    "final_assets_can_be_provided_later",
)


def get_imperium_frontend_design_handoff_metadata() -> ImperiumFrontendDesignHandoffResponse:
    return ImperiumFrontendDesignHandoffResponse(
        design_handoff_version="v1",
        read_only=True,
        frontend_metadata_layer_version="v6",
        design_direction=ImperiumFrontendDesignDirection(
            style="luxury_minimal_executive",
            visual_language="premium_dashboard",
            mood="focused_calm_powerful",
            ui_philosophy="clarity_before_density",
            safe_explanation="Imperium frontend design direction metadata.",
        ),
        supported_modules=list(IMPERIUM_FRONTEND_DESIGN_HANDOFF_SUPPORTED_MODULES),
        frontend_metadata_endpoints=list(IMPERIUM_FRONTEND_DESIGN_HANDOFF_METADATA_ENDPOINTS),
        asset_groups=list(IMPERIUM_FRONTEND_DESIGN_HANDOFF_ASSET_GROUPS),
        design_rules=list(IMPERIUM_FRONTEND_DESIGN_HANDOFF_RULES),
        safe_explanation="Design handoff metadata only for Imperium V1.",
    )
