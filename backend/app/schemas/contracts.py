from typing import Literal

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


class ImperiumContractsComplianceCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    status: Literal["declared"]
    safe_explanation: str


class ImperiumContractsComplianceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_version: str
    read_only: bool
    checks: list[ImperiumContractsComplianceCheck]
    safe_explanation: str
