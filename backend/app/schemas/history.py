"""Chronologie de l'historique Imperium (IMP.HISTORY.MAIN, doc 65 §7, doc 69 §3.5)."""

from datetime import datetime
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
