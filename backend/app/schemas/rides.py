"""Sessions VTC Vector (doc 59 §14) : démarrage, saisies, dépose, revue, clôture."""

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.schemas.imperium import ReplanRead

ExpenseCategory = Literal["carburant", "peage", "parking", "entretien", "plateformes", "autre"]


class SessionStart(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_ca_cents: int | None = Field(default=None, ge=1, le=10_000_000, strict=True)
    strategic_direction: str | None = Field(default=None, max_length=120)
    mission_id: UUID | None = None


class SessionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = Field(ge=1)
    target_ca_cents: int | None = Field(default=None, ge=1, le=10_000_000, strict=True)
    strategic_direction: str | None = Field(default=None, max_length=120)


class ManualRevenueCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount_cents: int = Field(gt=0, le=10_000_000, strict=True)
    occurred_at: datetime | None = None
    zone: str | None = Field(default=None, max_length=120)
    note: str | None = Field(default=None, max_length=300)
    wallet: str = Field(default="cash", min_length=1, max_length=80)


class ManualExpenseCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount_cents: int = Field(gt=0, le=10_000_000, strict=True)
    category: ExpenseCategory
    occurred_at: datetime | None = None
    note: str | None = Field(default=None, max_length=300)
    wallet: str = Field(default="cash", min_length=1, max_length=80)


class DropZoneCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    zone: str = Field(min_length=1, max_length=120)
    latitude: Decimal | None = Field(default=None, ge=-90, le=90, decimal_places=6)
    longitude: Decimal | None = Field(default=None, ge=-180, le=180, decimal_places=6)
    gps_confidence: Decimal | None = Field(default=None, ge=0, le=1, decimal_places=2)
    real_duration_minutes: int | None = Field(default=None, ge=1, le=600)

    @model_validator(mode="after")
    def coordinates_pair(self):
        if not self.zone.strip():
            raise ValueError("zone is empty.")
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude go together.")
        return self


class DropZoneRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    zone: str
    latitude: Decimal | None
    longitude: Decimal | None
    gps_confidence: Decimal | None
    real_duration_minutes: int | None
    recorded_at: datetime


class SessionComplete(BaseModel):
    model_config = ConfigDict(extra="forbid")

    review_note: str | None = Field(default=None, max_length=2000)


class SessionKpis(BaseModel):
    revenue_cents: int
    expense_cents: int
    net_cents: int
    revenue_entries: int
    expense_entries: int
    drop_zones: int
    elapsed_minutes: int
    active_minutes: int = 0  # écoulé moins les pauses (kit Vector)
    rides_done: int = 0  # offres acceptées dont le résultat réel est enregistré (accepté ≠ réalisé)
    rides_refused: int = 0  # offres refusées par l'utilisateur
    target_progress: Decimal | None  # CA / cible, None sans cible
    objective_reached: bool | None  # None sans cible


class SessionRead(BaseModel):
    id: UUID
    status: Literal["active", "paused", "completed"]
    started_at: datetime
    ended_at: datetime | None
    paused_at: datetime | None = None
    target_ca_cents: int | None
    strategic_direction: str | None
    mission_id: UUID | None
    review_note: str | None
    version: int
    kpis: SessionKpis
    replan_event_id: UUID | None = None  # replan Imperium demandé après la clôture (VEC-11)


class SessionReplanResponse(BaseModel):
    session: SessionRead
    replan: ReplanRead


class CurrentSessionRead(BaseModel):
    session: SessionRead | None


class SessionListResponse(BaseModel):
    items: list[SessionRead]


class SessionEntryResult(BaseModel):
    transaction_id: UUID
    session: SessionRead


class RecommendationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_zone: str | None = Field(default=None, max_length=120)


class ZoneStatRead(BaseModel):
    zone: str
    rides: int
    sessions: int
    average_ride_cents: int


class RecommendationRead(BaseModel):
    id: UUID
    session_id: UUID | None
    requested_at: datetime
    current_zone: str | None
    recommendation: Literal["stay_here", "move_to_zone", "abstain"]
    zone: str | None
    reason: str
    confidence: Decimal
    hourly_rate_estimate_cents: int | None  # pas encore : le temps passé par zone n'est pas mesuré
    slot: str  # ex. « semaine, 18 h–20 h »
    zones: list[ZoneStatRead]  # zones comparées, meilleure d'abord
    missing_context: list[str]  # signaux non pris en compte (événements, trains, aéroports, trafic)
    feedback_useful: bool | None
    ride_user_action: Literal["accepted", "refused", "missed", "ignored"] | None
    feedback_reason: str | None
    feedback_at: datetime | None


class RecommendationFeedback(BaseModel):
    model_config = ConfigDict(extra="forbid")

    useful: bool
    ride_user_action: Literal["accepted", "refused", "missed", "ignored"] | None = None
    reason: str | None = Field(default=None, max_length=500)


class RideOfferCreate(BaseModel):
    """Course proposée, saisie à la main (l'OCR des captures viendra remplir les mêmes champs)."""

    model_config = ConfigDict(extra="forbid")

    price_cents: int = Field(ge=1, le=1_000_000, strict=True)
    offered_at: datetime | None = None
    platform: Literal["bolt", "uber", "heetch", "other"] = "bolt"
    distance_km: Decimal | None = Field(default=None, gt=0, le=1000, decimal_places=2)
    estimated_duration_min: int | None = Field(default=None, ge=1, le=600)
    approach_distance_km: Decimal | None = Field(default=None, ge=0, le=200, decimal_places=2)
    approach_duration_min: int | None = Field(default=None, ge=0, le=180)
    surge_multiplier: Decimal | None = Field(default=None, ge=1, le=10, decimal_places=2)
    pickup_zone: str | None = Field(default=None, max_length=120)
    destination_zone: str | None = Field(default=None, max_length=120)
    pickup_zone_code: str | None = Field(default=None, pattern=r"^\d{5}$")  # code postal, ex. 75008
    destination_zone_code: str | None = Field(default=None, pattern=r"^\d{5}$")
    payment_type: Literal["card", "cash", "pro"] | None = None
    ride_type: Literal["immediate", "scheduled"] = "immediate"
    # manual : saisie ; assistant : lue à l'écran par l'assistant de prise de course (capture + OCR embarqué).
    source: Literal["manual", "assistant"] = "manual"
    # Majoration sous ses autres formes (« +20 % », « +2,40 € ») ; le multiplicateur reste surge_multiplier.
    surge_percent: int | None = Field(default=None, ge=1, le=500)
    surge_bonus_cents: int | None = Field(default=None, ge=1, le=100_000)
    toll_cents: int | None = Field(default=None, ge=1, le=100_000)  # péage payé par le client, hors prix (doc 37 §4)
    ride_class: Literal["standard", "comfort", "xl", "pet", "other"] | None = None
    # Position de la tablette quand l'offre arrive (doc 57 §5.3) ; reste dans la base de l'utilisateur.
    driver_lat: Decimal | None = Field(default=None, ge=-90, le=90, decimal_places=6)
    driver_lng: Decimal | None = Field(default=None, ge=-180, le=180, decimal_places=6)


class RideDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = Field(ge=1)
    decision: Literal["accepted", "refused", "missed"]
    note: str | None = Field(default=None, max_length=300)


class RideOutcomeRequest(BaseModel):
    """Résultat réel d'une course acceptée : temps mobilisé à la minute (doc 33 §8)."""

    model_config = ConfigDict(extra="forbid")

    version: int = Field(ge=1)
    actual_earning_cents: int = Field(ge=1, le=1_000_000, strict=True)
    approach_minutes: int = Field(ge=0, le=180)
    wait_minutes: int = Field(default=0, ge=0, le=180)  # attente au point de prise en charge
    ride_minutes: int = Field(ge=1, le=600)
    return_minutes: int = Field(default=0, ge=0, le=300)  # retour estimé après la dépose
    record_revenue: bool = True  # écrit aussi le revenu au Vault (évite une double saisie)
    wallet: str = Field(default="cash", min_length=1, max_length=80)


class RideOfferRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    session_id: UUID
    offered_at: datetime
    source: str
    platform: str
    price_cents: int
    distance_km: Decimal | None
    estimated_duration_min: int | None
    approach_distance_km: Decimal | None
    approach_duration_min: int | None
    surge_multiplier: Decimal | None
    pickup_zone: str | None
    destination_zone: str | None
    payment_type: str | None
    ride_type: str
    features: dict
    decision: Literal["accepted", "refused", "missed"] | None
    decided_at: datetime | None
    decision_note: str | None
    actual_earning_cents: int | None
    mobilized_minutes: int | None
    actual_hourly_rate_cents: int | None
    revenue_transaction_id: UUID | None
    pickup_zone_code: str | None
    destination_zone_code: str | None
    version: int
    signal: Literal["green", "red"] | None  # règles seules (doc 57 §3.1) ; aucun = à toi de juger
    signal_source: str | None
    signal_reason: str | None
    triggered_rules: list[str]


class RideOfferListResponse(BaseModel):
    items: list[RideOfferRead]


class TrainingSummaryRead(BaseModel):
    offers: int
    decided: int
    accepted: int
    refused: int
    missed: int
    with_outcome: int  # courses utilisables pour l'apprentissage
    median_hourly_rate_cents: int | None
    phase: Literal["cold_start", "transition", "autonomous"]
    message: str


RideTimeBlock = Literal["night", "morning", "daytime", "evening", "late_evening"]


class RuleConditions(BaseModel):
    """Conditions d'une règle ; toutes celles données doivent être vraies pour qu'elle se déclenche."""

    model_config = ConfigDict(extra="forbid")

    zone_codes: list[Annotated[str, StringConstraints(pattern=r"^\d{5}$")]] | None = Field(default=None, max_length=50)
    applies_to: list[Literal["pickup", "destination"]] | None = None  # côté(s) testés pour zone_codes
    destination_prefixes: list[Annotated[str, StringConstraints(pattern=r"^\d{2,5}$")]] | None = Field(default=None, max_length=50)
    time_blocks: list[RideTimeBlock] | None = None
    ride_types: list[Literal["immediate", "scheduled"]] | None = None
    # R3 : arrivée hors des préfixes et hors des codes autorisés (communes en deçà des limites) ; code absent → non déclenchée.
    destination_outside_prefixes: list[Annotated[str, StringConstraints(pattern=r"^\d{2,5}$")]] | None = Field(
        default=None, max_length=50)
    destination_allowed_codes: list[Annotated[str, StringConstraints(pattern=r"^\d{5}$")]] | None = Field(
        default=None, max_length=300)

    @model_validator(mode="after")
    def coherent(self):
        if (self.zone_codes is None) != (self.applies_to is None):
            raise ValueError("zone_codes and applies_to go together.")
        if self.destination_allowed_codes is not None and self.destination_outside_prefixes is None:
            raise ValueError("destination_allowed_codes needs destination_outside_prefixes.")
        if all(value is None for value in self.model_dump().values()):
            raise ValueError("At least one condition is required.")
        return self


class BusinessRuleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    rule_code: str
    name: str
    description: str
    conditions: dict
    action: Literal["red", "green"]
    is_active: bool
    is_hard_rule: bool
    times_applied: int
    revision_count: int
    version: int
    last_revised_at: datetime | None


class BusinessRuleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = Field(ge=1)
    reason: str = Field(min_length=3, max_length=500)
    is_active: bool | None = None
    is_hard_rule: bool | None = None
    conditions: RuleConditions | None = None


class BusinessRuleListResponse(BaseModel):
    items: list[BusinessRuleRead]
    not_coded: list[str]  # règles du doc 57 §4 qui attendent des données (géographie, flux externes)


class WeatherNow(BaseModel):
    temperature_c: float | None = None
    precipitation_mm: float | None = None
    weather_code: int | None = None
    wind_kmh: float | None = None


class WeatherHour(BaseModel):
    time: str
    temperature_c: float | None = None
    precipitation_mm: float | None = None
    precipitation_probability: int | None = None
    weather_code: int | None = None


class WeatherFeedRead(BaseModel):
    """Flux météo de Vector (grille) : ok, stale (dernière passe de plus de 45 min) ou unavailable (aucune)."""

    status: Literal["ok", "stale", "unavailable"]
    fetched_at: datetime | None = None
    message: str | None = None
    now: WeatherNow | None = None  # centre de Paris
    hours: list[WeatherHour] = []  # quarts d'heure au centre de Paris (2 passés, 8 à venir)
    cells: int = 0
    raining_cells_paris: int = 0  # cases de Paris et petite couronne sous la pluie
    cells_paris: int = 0
