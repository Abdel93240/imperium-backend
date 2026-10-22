"""Contrats de Nourrir l'IA (doc 70)."""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.pulse_labs import LabResultIn


class InboxItemCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, max_length=200)
    context_text: str | None = Field(default=None, max_length=20000)
    entry_app: Literal["imperium", "vector", "vault", "pulse", "path"] = "imperium"

    @field_validator("title", "context_text")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class InboxSourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    original_filename: str
    kind: str
    mime_type: str
    size_bytes: int
    storage_pointer: str | None
    created_at: datetime


class InboxItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    entry_app: str
    context_text: str | None
    status: str
    ui_state: str = ""
    error_message: str | None
    extraction_draft: dict | None
    extraction_final: dict | None
    destination: str | None
    created_entity_type: str | None
    created_entity_id: UUID | None
    created_at: datetime
    analyzed_at: datetime | None
    validated_at: datetime | None
    vectorized_at: datetime | None
    sources: list[InboxSourceRead] = Field(default_factory=list)


class InboxItemListResponse(BaseModel):
    items: list[InboxItemRead]


class ZipExpansionRead(BaseModel):
    created_items: list[InboxItemRead]
    rejected: list[dict]


class ExtractionUpdate(BaseModel):
    """Correction du brouillon par l'utilisateur avant validation (doc 70 §7 étape 10)."""

    model_config = ConfigDict(extra="forbid")

    summary: str | None = Field(default=None, max_length=20000)
    facts: list[str] | None = Field(default=None, max_length=200)
    lab_results: list[LabResultIn] | None = Field(default=None, max_length=80)  # prise de sang : valeurs corrigées
    measured_on: date | None = None  # date du prélèvement
    recipe: dict | None = None  # recette corrigée (champs de RecipeCreate), relue à la validation


class InboxValidateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    destination: Literal["memory", "project", "lab_results", "recipe"] = "memory"
    project_title: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def project_needs_title(self) -> "InboxValidateRequest":
        if self.destination == "project" and not (self.project_title or "").strip():
            raise ValueError("project_title is required to create a project.")
        return self
