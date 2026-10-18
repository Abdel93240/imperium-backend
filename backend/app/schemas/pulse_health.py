"""Santé sensible Pulse : consentement par domaine et relevé corporel (doc 40 §14, doc 05)."""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from app.schemas.imperium import ReplanRead
from pydantic import BaseModel, ConfigDict, Field, model_validator

HealthDomain = Literal["body", "pain", "medical"]


class ConsentRead(BaseModel):
    domain: str
    granted: bool
    granted_at: datetime | None
    revoked_at: datetime | None  # dernier retrait, si le consentement n'est plus actif
    text_version: str  # version du texte à accepter (celle du texte affiché)
    text_fr: str


class ConsentListResponse(BaseModel):
    items: list[ConsentRead]


class ConsentGrantRequest(BaseModel):
    """L'écran renvoie la version du texte affiché : un texte changé demande un nouvel accord."""

    model_config = ConfigDict(extra="forbid")

    text_version: str = Field(min_length=1, max_length=40)


_CM = {"gt": Decimal("0"), "le": Decimal("400"), "max_digits": 4, "decimal_places": 1}


class BodySnapshotCreate(BaseModel):
    """Mesures seulement : un champ photo est refusé (photo locale au téléphone, doc 40 §14)."""

    model_config = ConfigDict(extra="forbid")

    measured_at: datetime
    weight_kg: Decimal | None = Field(default=None, gt=Decimal("0"), le=Decimal("500"), max_digits=5, decimal_places=2)
    body_fat_percent: Decimal | None = Field(default=None, ge=Decimal("1"), le=Decimal("70"), max_digits=4, decimal_places=2)
    waist_cm: Decimal | None = Field(default=None, **_CM)
    chest_cm: Decimal | None = Field(default=None, **_CM)
    arm_cm: Decimal | None = Field(default=None, **_CM)
    notes: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def one_measure(self) -> "BodySnapshotCreate":
        if all(getattr(self, field) is None for field in ("weight_kg", "body_fat_percent", "waist_cm", "chest_cm", "arm_cm")):
            raise ValueError("At least one measurement is required.")
        return self


class BodySnapshotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    measured_at: datetime
    weight_kg: Decimal | None
    body_fat_percent: Decimal | None
    waist_cm: Decimal | None
    chest_cm: Decimal | None
    arm_cm: Decimal | None
    notes: str | None
    created_at: datetime


class BodySnapshotListResponse(BaseModel):
    """Plus récent d'abord ; `weight_change_kg` = dernier poids − premier poids de la liste (aucune interprétation)."""

    items: list[BodySnapshotRead]
    weight_change_kg: Decimal | None


class DeletedCountRead(BaseModel):
    deleted: int


PainZone = Literal[
    "head", "neck", "shoulder", "upper_back", "lower_back", "chest", "abdomen", "arm", "elbow", "wrist", "hand", "hip",
    "thigh", "knee", "calf", "ankle", "foot", "other",
]


class PainLogCreate(BaseModel):
    """Saisie PUL-09 (ou proposée par le chatbot puis validée) ; aucune photo."""

    model_config = ConfigDict(extra="forbid")

    body_zone: PainZone
    side: Literal["left", "right", "both"] | None = None
    severity: int = Field(ge=0, le=10)
    pain_type: str | None = Field(default=None, max_length=80)
    limitation_notes: str | None = Field(default=None, max_length=1000)
    workout_impact: bool = False
    workout_id: UUID | None = None
    noted_at: datetime | None = None


class PainLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    body_zone: str
    side: str | None
    severity: int
    pain_type: str | None
    limitation_notes: str | None
    workout_impact: bool
    workout_id: UUID | None
    noted_at: datetime
    resolved_at: datetime | None
    created_at: datetime
    suggest_replan: bool = False  # douleur forte : l'écran propose de replanifier, rien n'est fait seul
    replan_message: str | None = None
    replan_event_id: UUID | None = None  # replan demandé depuis cette douleur


class PainReplanResponse(BaseModel):
    pain_log: PainLogRead
    replan: ReplanRead


class PainLogListResponse(BaseModel):
    items: list[PainLogRead]


MedicalDocType = Literal[
    "prescription", "blood_test", "imaging_report", "certificate", "physio_note", "allergy_note",
    "consultation_summary", "vaccination", "other",
]
MedicalRuleType = Literal[
    "workout_limit", "nutrition_constraint", "fasting_caution", "pain_watch", "medication_note", "general_context",
]


class MedicalDocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    doc_type: str
    doc_date: date | None
    original_name: str
    mime_type: str
    size_bytes: int
    status: str
    consent_version: str
    consented_at: datetime
    retention_delete_after: datetime
    created_at: datetime
    message: str | None = None


class MedicalDocumentListResponse(BaseModel):
    items: list[MedicalDocumentRead]


class MedicalRuleCreate(BaseModel):
    """Règle saisie par l'utilisateur (V1 : l'extraction automatique n'est pas encore active)."""

    model_config = ConfigDict(extra="forbid")

    rule_type: MedicalRuleType
    rule_text: str = Field(min_length=1, max_length=1000)
    severity: Literal["info", "warning", "critical"]
    source_document_id: UUID | None = None
    source_quote: str | None = Field(default=None, max_length=500)
    expires_at: date | None = None

    @model_validator(mode="after")
    def text_not_blank(self) -> "MedicalRuleCreate":
        if not self.rule_text.strip():
            raise ValueError("rule_text is empty.")
        return self


class MedicalRuleActivateRequest(BaseModel):
    """Doc 34 §10.1 : source relue, texte confirmé, règle encore valable — les trois sont obligatoires."""

    model_config = ConfigDict(extra="forbid")

    reviewed_source: Literal[True]
    confirmed_text: Literal[True]
    still_relevant: Literal[True]
    acknowledge_critical: bool = False
    supersedes_rule_id: UUID | None = None


class MedicalRuleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source_document_id: UUID | None
    rule_type: str
    rule_text: str
    source_quote: str | None
    severity: str
    status: str
    expires_at: date | None
    validated_at: datetime | None
    critical_acknowledged_at: datetime | None
    deactivated_at: datetime | None
    superseded_by: UUID | None
    created_at: datetime


class MedicalRuleListResponse(BaseModel):
    items: list[MedicalRuleRead]
