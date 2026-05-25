from pydantic import BaseModel, ConfigDict


class ContractIndexEndpoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    method: str
    path: str
    purpose: str
    read_only: bool
    idempotency_key_required: bool


class ContractIndexGroup(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    endpoints: list[ContractIndexEndpoint]


class ImperiumContractsIndexResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_version: str
    read_only: bool
    groups: list[ContractIndexGroup]
    safe_explanation: str


class ImperiumContractsComplianceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_version: str
    read_only: bool
    metadata_only: bool
    no_db_migration: bool
    no_business_data_read: bool
    not_health_check: bool
    not_dynamic_discovery: bool
    no_ai_n8n_ocr_scoring_coaching_recommendations: bool
    no_cross_module_writes: bool
    safe_explanation: str
