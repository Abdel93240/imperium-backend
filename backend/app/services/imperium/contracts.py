from app.schemas.contracts import (
    ContractIndexEndpoint,
    ContractIndexGroup,
    ImperiumContractsIndexResponse,
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
