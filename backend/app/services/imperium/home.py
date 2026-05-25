from app.schemas.home import (
    ContractIndexEndpoint,
    ContractIndexGroup,
    HomeBootstrapModule,
    HomeBootstrapResponse,
    ImperiumContractsIndexResponse,
)

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


CONTRACT_INDEX_GROUPS: tuple[ContractIndexGroup, ...] = (
    ContractIndexGroup(
        name="home",
        endpoints=[
            ContractIndexEndpoint(
                method="GET",
                path="/api/imperium/home/bootstrap",
                purpose="Frontend bootstrap metadata.",
                read_only=True,
                idempotency_key_required=False,
            )
        ],
    ),
    ContractIndexGroup(
        name="dashboard",
        endpoints=[
            ContractIndexEndpoint(
                method="GET",
                path="/api/imperium/dashboard",
                purpose="Dashboard read-only snapshot.",
                read_only=True,
                idempotency_key_required=False,
            )
        ],
    ),
    ContractIndexGroup(
        name="daily_plan",
        endpoints=[
            ContractIndexEndpoint(
                method="GET",
                path="/api/imperium/daily-plan",
                purpose="Daily plan read-only snapshot.",
                read_only=True,
                idempotency_key_required=False,
            )
        ],
    ),
    ContractIndexGroup(
        name="mission",
        endpoints=[
            ContractIndexEndpoint(
                method="GET",
                path="/api/imperium/missions/active",
                purpose="Read active mission.",
                read_only=True,
                idempotency_key_required=False,
            ),
            ContractIndexEndpoint(
                method="GET",
                path="/api/imperium/missions/history",
                purpose="Read mission history.",
                read_only=True,
                idempotency_key_required=False,
            ),
            ContractIndexEndpoint(
                method="POST",
                path="/api/imperium/missions/backlog",
                purpose="Create backlog mission.",
                read_only=False,
                idempotency_key_required=True,
            ),
        ],
    ),
    ContractIndexGroup(
        name="vault",
        endpoints=[
            ContractIndexEndpoint(
                method="GET",
                path="/api/imperium/vault/transactions",
                purpose="Read ledger transactions.",
                read_only=True,
                idempotency_key_required=False,
            ),
            ContractIndexEndpoint(
                method="POST",
                path="/api/imperium/vault/transactions",
                purpose="Create ledger transaction.",
                read_only=False,
                idempotency_key_required=True,
            ),
            ContractIndexEndpoint(
                method="GET",
                path="/api/imperium/vault/summary",
                purpose="Read vault summary.",
                read_only=True,
                idempotency_key_required=False,
            ),
        ],
    ),
    ContractIndexGroup(
        name="path",
        endpoints=[
            ContractIndexEndpoint(
                method="GET",
                path="/api/imperium/path/today",
                purpose="Read Path today view.",
                read_only=True,
                idempotency_key_required=False,
            ),
            ContractIndexEndpoint(
                method="GET",
                path="/api/imperium/path/habits",
                purpose="Read Path habits.",
                read_only=True,
                idempotency_key_required=False,
            ),
            ContractIndexEndpoint(
                method="POST",
                path="/api/imperium/path/habits",
                purpose="Create Path habit.",
                read_only=False,
                idempotency_key_required=True,
            ),
        ],
    ),
    ContractIndexGroup(
        name="pulse",
        endpoints=[
            ContractIndexEndpoint(
                method="GET",
                path="/api/imperium/pulse/today",
                purpose="Read Pulse today entry.",
                read_only=True,
                idempotency_key_required=False,
            ),
            ContractIndexEndpoint(
                method="GET",
                path="/api/imperium/pulse/stats/summary",
                purpose="Read Pulse summary stats.",
                read_only=True,
                idempotency_key_required=False,
            ),
            ContractIndexEndpoint(
                method="POST",
                path="/api/imperium/pulse/entries",
                purpose="Create Pulse daily entry.",
                read_only=False,
                idempotency_key_required=True,
            ),
        ],
    ),
)


def get_imperium_contracts_index_metadata() -> ImperiumContractsIndexResponse:
    return ImperiumContractsIndexResponse(
        contract_version="v1",
        read_only=True,
        groups=list(CONTRACT_INDEX_GROUPS),
        safe_explanation="Frontend API contract index metadata.",
    )
