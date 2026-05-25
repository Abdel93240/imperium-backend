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
