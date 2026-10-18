"""Chronologie de l'historique Imperium (IMP.HISTORY.MAIN, doc 65 §7, doc 69 §3.5)."""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

HistoryFilter = Literal["all", "missions", "decisions", "weekly", "failed"]
HistorySource = Literal["mission", "day", "plan", "decision", "project", "weekly"]


class HistoryEventRead(BaseModel):
    id: str
    type: str
    title: str
    status: str
    occurred_at: datetime
    source: HistorySource
    reason: str | None = None
    linked_mission_id: UUID | None = None
    linked_route: str


class HistoryEventListResponse(BaseModel):
    items: list[HistoryEventRead]
    count: int
    limit: int
    offset: int
    has_more: bool
    filter: HistoryFilter
    query: str | None


class HistoryEventDetailResponse(BaseModel):
    event: HistoryEventRead
    details: dict


class HistoryDayRead(BaseModel):
    """Journée opérationnelle (démarrage → clôture) et ses missions (doc 65 §7.5 « Historique des journées »)."""

    planning_day_id: UUID
    start_local_date: date
    started_at: datetime
    finished_at: datetime | None
    status: Literal["open", "finished"]
    duration_minutes: int
    felt_energy: int
    missions_completed: int
    missions_failed: int
    missions_cancelled: int
    annexes_completed: int  # missions annexes faites (bonus, doc 53 §8)
    day_review_id: UUID | None


class HistoryDayListResponse(BaseModel):
    items: list[HistoryDayRead]
    count: int
    limit: int
    offset: int
    has_more: bool


HistoryPeriod = Literal["week", "month", "3months", "year", "all"]


class FinancePointRead(BaseModel):
    day: date
    net_cents: int


class HistoryFinancesResponse(BaseModel):
    """Bloc Finances (doc 65 §7.5) : courbe du résultat net par jour, écart avec la période précédente."""

    period: HistoryPeriod
    from_day: date | None
    to_day: date
    currency: Literal["EUR"]
    points: list[FinancePointRead]
    period_net_cents: int
    previous_period_net_cents: int | None  # « Tout » : pas de période précédente
    delta_cents: int  # « Tout » : depuis le début
    balance_cents: int | None  # solde prévu du jour (dernier relevé + mouvements), hors période
