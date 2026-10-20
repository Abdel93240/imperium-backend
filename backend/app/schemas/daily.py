from datetime import date, datetime, time
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.imperium import MissionCompletionResponse

WeekdayCode = Literal["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


class ScoringParameterRead(BaseModel):
    code: str
    version: int
    value: dict | list
    origin: str
    rationale_fr: str | None
    valid_from: datetime


class ScoringSettingsRead(BaseModel):
    """Barèmes `df.*` courants ; `source=code` si le service retombe sur les constantes (absent ou invalide)."""

    source: Literal["parameters", "code"]
    parameters: list[ScoringParameterRead]


class ScoringParameterVersionsResponse(BaseModel):
    versions: list[ScoringParameterRead]


class ScoringSettingsUpdateRequest(BaseModel):
    """Nouvelle version des paramètres cités (valeur complète de chacun) ; raison obligatoire."""

    model_config = ConfigDict(extra="forbid")

    changes: dict[str, dict | list] = Field(min_length=1, max_length=8)
    reason_fr: str = Field(min_length=3, max_length=500)


class MissionLocation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    label: str | None = Field(default=None, max_length=200)


class MissionConstraints(BaseModel):
    """Attributs lus par les portes (spec Daily §3.2) ; un PUT remplace l'ensemble."""

    model_config = ConfigDict(extra="forbid")

    location: MissionLocation | None = None
    window_start: time | None = None
    window_end: time | None = None
    window_days: list[WeekdayCode] | None = Field(default=None, min_length=1, max_length=7)
    is_fixed_commitment: bool = False
    fixed_at: datetime | None = None
    physical_load: int | None = Field(default=None, ge=1, le=5)
    cognitive_load: int | None = Field(default=None, ge=1, le=5)

    @model_validator(mode="after")
    def coherent(self) -> "MissionConstraints":
        if self.window_start is not None and self.window_end is not None and self.window_start >= self.window_end:
            raise ValueError("window_start must be before window_end")
        if self.is_fixed_commitment and self.fixed_at is None:
            raise ValueError("fixed_at is required for a fixed commitment")
        if self.fixed_at is not None and self.fixed_at.tzinfo is None:
            raise ValueError("fixed_at must carry a timezone")
        return self


class MissionDependencyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    parent_mission_id: UUID
    child_mission_id: UUID
    hard: bool = True


class MissionDependencyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    parent_mission_id: UUID
    child_mission_id: UUID
    hard: bool
    created_at: datetime


class Position(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


class SelectionRequest(BaseModel):
    """Déclenchement manuel ; la position courante sert seulement au départage par trajet."""

    model_config = ConfigDict(extra="forbid")

    position: Position | None = None


class NextMissionRead(BaseModel):
    """« Ta prochaine mission : X. » — aucune justification ni file exposée (spec Daily §1.7)."""

    id: UUID
    title: str
    domain: str | None
    estimated_minutes: int | None
    location_label: str | None
    travel_source: str


class SelectionRead(BaseModel):
    selection_log_id: UUID
    outcome: Literal["next_mission", "arbitration_pending", "day_done"]
    level: int
    condition: str | None
    pulled_forward: bool
    next_mission: NextMissionRead | None


class DailyCompleteResponse(BaseModel):
    completion: MissionCompletionResponse
    selection: SelectionRead | None


class DailyCurrentRead(BaseModel):
    active_mission_id: UUID | None
    last_selection: SelectionRead | None


class SelectionLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    trigger: str
    trigger_ref: UUID | None
    at_ts: datetime
    remaining_min: int
    next_fixed_ref: UUID | None
    next_fixed_kind: str | None
    scope: str
    feasible_set: list
    mandatory_set: list
    chosen_mission_id: UUID | None
    tiebreak_applied: dict | None
    outcome: str
    condition: str | None
    pulled_forward: bool
    level: int
    latency_ms: int


class SelectionLogResponse(BaseModel):
    date: date
    entries: list[SelectionLogRead]


class QueueEntryRead(BaseModel):
    mission_id: UUID
    title: str
    score: float
    mandatory: bool
    blocked_by: str | None
    travel_min: int
    travel_source: str
    duration_min: int


class QueueRead(BaseModel):
    """Admin/debug uniquement : la file reste invisible dans le produit."""

    outcome: str
    scope: str
    condition: str | None
    remaining_min: int
    next_fixed_ref: UUID | None
    next_fixed_kind: str | None
    chosen_mission_id: UUID | None
    ranking: list[UUID]
    entries: list[QueueEntryRead]


class OverrideCreate(BaseModel):
    """Autre mission que la proposée ; sans raison → 400 OVERRIDE_REASON_REQUIRED (mécanique gravée)."""

    model_config = ConfigDict(extra="forbid")

    selection_log_id: UUID
    chosen_mission_id: UUID
    reason: str | None = Field(default=None, max_length=1000)


class OverrideRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    selection_log_id: UUID
    proposed_mission_id: UUID
    chosen_mission_id: UUID
    reason: str
    context: dict
    created_at: datetime


class PrayerPlanRead(BaseModel):
    """Prière du jour vue par Daily : mosquée retenue, départ, bloc (ou prière seul avec sa raison)."""

    prayer: str
    reference_adhan: datetime
    mosque_id: UUID | None
    mosque_name: str | None
    travel_min: int | None
    depart_at: datetime | None
    adhan: datetime
    iqama: datetime | None
    block_end: datetime
    times_source: str
    solo_reason: str | None
    origin_source: str


class PrayerDayPlanRead(BaseModel):
    date: date
    items: list[PrayerPlanRead]
