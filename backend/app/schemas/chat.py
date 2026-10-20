"""Chatbot V1 (doc 72) : session, messages, proposition d'action à valider."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ChatSessionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    context_kind: Literal["general", "project", "mission", "intervention"] = "general"
    context_ref: str | None = Field(default=None, max_length=200)


class ChatMessageCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=4000)

    @field_validator("text")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Message vide.")
        return value.strip()


class ChatMessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    role: str
    content: str
    degraded: bool
    created_at: datetime


class ChatProposalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    action: str
    params: dict
    summary_fr: str
    status: str
    result: dict | None
    created_at: datetime
    decided_at: datetime | None


class ChatSessionRead(BaseModel):
    id: UUID
    status: str
    context_kind: str
    context_ref: str | None
    agent: str
    started_at: datetime
    closed_at: datetime | None
    messages: list[ChatMessageRead]
    open_proposal: ChatProposalRead | None


class ChatTurnRead(BaseModel):
    """Un tour : le message de l'utilisateur, la réponse, et la proposition éventuelle (jamais exécutée)."""

    user_message: ChatMessageRead
    assistant_message: ChatMessageRead
    proposal: ChatProposalRead | None
