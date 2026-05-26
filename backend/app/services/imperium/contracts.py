from app.schemas.contracts import (
    ContractIndexEndpoint,
    ContractIndexGroup,
    ImperiumContractsComplianceCheck,
    ImperiumContractsComplianceResponse,
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
        name="events",
        endpoints=[
            ContractIndexEndpoint(
                method="GET",
                path="/api/imperium/events",
                purpose="Read Imperium events.",
                read_only=True,
                idempotency_key_required=False,
            ),
            ContractIndexEndpoint(
                method="POST",
                path="/api/imperium/events",
                purpose="Append Imperium event.",
                read_only=False,
                idempotency_key_required=True,
            ),
            ContractIndexEndpoint(
                method="GET",
                path="/api/imperium/events/{event_id}",
                purpose="Read Imperium event detail.",
                read_only=True,
                idempotency_key_required=False,
            ),
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
    ContractIndexGroup(
        name="frontend",
        endpoints=[
            ContractIndexEndpoint(
                method="GET",
                path="/api/imperium/frontend/navigation",
                purpose="Frontend navigation metadata.",
                read_only=True,
                idempotency_key_required=False,
            ),
            ContractIndexEndpoint(
                method="GET",
                path="/api/imperium/frontend/layout",
                purpose="Frontend layout metadata.",
                read_only=True,
                idempotency_key_required=False,
            ),
            ContractIndexEndpoint(
                method="GET",
                path="/api/imperium/frontend/theme-tokens",
                purpose="Frontend theme token metadata.",
                read_only=True,
                idempotency_key_required=False,
            ),
            ContractIndexEndpoint(
                method="GET",
                path="/api/imperium/frontend/empty-states",
                purpose="Frontend empty state metadata.",
                read_only=True,
                idempotency_key_required=False,
            ),
            ContractIndexEndpoint(
                method="GET",
                path="/api/imperium/frontend/actions",
                purpose="Frontend action metadata.",
                read_only=True,
                idempotency_key_required=False,
            ),
            ContractIndexEndpoint(
                method="GET",
                path="/api/imperium/frontend/module-cards",
                purpose="Frontend module cards metadata.",
                read_only=True,
                idempotency_key_required=False,
            ),
            ContractIndexEndpoint(
                method="GET",
                path="/api/imperium/frontend/asset-registry",
                purpose="Frontend asset registry metadata.",
                read_only=True,
                idempotency_key_required=False,
            ),
            ContractIndexEndpoint(
                method="GET",
                path="/api/imperium/frontend/app-manifest",
                purpose="Frontend application manifest metadata.",
                read_only=True,
                idempotency_key_required=False,
            ),
            ContractIndexEndpoint(
                method="GET",
                path="/api/imperium/frontend/design-handoff",
                purpose="Frontend design handoff metadata.",
                read_only=True,
                idempotency_key_required=False,
            ),
        ],
    ),
)

COMPLIANCE_CHECKS: tuple[ImperiumContractsComplianceCheck, ...] = (
    ImperiumContractsComplianceCheck(
        key="metadata_only",
        status="declared",
        safe_explanation="Contracts index is metadata-only.",
    ),
    ImperiumContractsComplianceCheck(
        key="not_openapi",
        status="declared",
        safe_explanation="Contracts index is not a generated OpenAPI document.",
    ),
    ImperiumContractsComplianceCheck(
        key="not_health_check",
        status="declared",
        safe_explanation="Contracts index is not a runtime health check.",
    ),
    ImperiumContractsComplianceCheck(
        key="no_business_data_read",
        status="declared",
        safe_explanation="Contracts index does not read business data.",
    ),
    ImperiumContractsComplianceCheck(
        key="no_dynamic_discovery",
        status="declared",
        safe_explanation="Contracts index is static and deterministic in V1.",
    ),
)


def get_imperium_contracts_index_metadata() -> ImperiumContractsIndexResponse:
    return ImperiumContractsIndexResponse(
        contract_version="v1",
        read_only=True,
        groups=list(CONTRACT_INDEX_GROUPS),
        safe_explanation="Frontend API contract index metadata.",
    )


def get_imperium_contracts_compliance_metadata() -> ImperiumContractsComplianceResponse:
    return ImperiumContractsComplianceResponse(
        contract_version="v1",
        read_only=True,
        checks=list(COMPLIANCE_CHECKS),
        safe_explanation="Frontend contracts compliance metadata.",
    )
