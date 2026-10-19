"""Digest du WR : instantané figé assemblé par le code à l'ouverture (spec WR §3.6, §9 P1).

Contenu : les items ouverts du docket, groupés par type, chaque type plafonné par
`wr.digest_caps` (un type sans plafond n'est limité que par le plafond de tokens), puis
plafond dur `wr.digest_token_cap` : on retire les items les moins prioritaires d'abord,
jamais au hasard ; rouges et décisions forcées ne sortent qu'en dernier recours. Rollups (W1) et état du plan (plan_versions) ne sont pas encore codés :
ils figurent dans `unavailable`.

Whitelist assembleur : seules les sections listées peuvent entrer, et jamais de brut
device, de contenu conversationnel ni de document médical — les références suffisent.
Une tentative lève DigestWhitelistError.
"""

import json
import math
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.enums import PrivacyLevel, SourceApp
from app.models.imperium import ImperiumWeeklyReviewSession
from app.models.wr import WrDigest
from app.services.events.emitter import build_event
from app.services.params import get_parameter
from app.services.wr import docket

ALLOWED_SECTIONS = frozenset({"window", "docket", "counts", "truncated", "unavailable"})
FORBIDDEN_KEYS = frozenset({
    "conversation", "messages", "transcript", "raw", "raw_text", "device_raw", "sensor_samples",
    "document_text", "ocr_text", "medical_document", "medical_text", "file_bytes", "image", "audio",
})
ENTRY_FIELDS = (
    "id", "item_type", "domain", "title_fr", "payload", "evidence_refs", "confidence", "impact_estimate",
    "severity", "priority", "force_decision", "consecutive_defers",
)
CLOSED_SESSION_STATUSES = ("stored", "cancelled", "failed")
UNAVAILABLE = ["rollups", "plan_state"]


class DigestWhitelistError(ValueError):
    pass


class DigestStateError(RuntimeError):
    def __init__(self, message: str, code: str) -> None:
        super().__init__(message)
        self.code = code


def check_section(name: str) -> None:
    if name not in ALLOWED_SECTIONS:
        raise DigestWhitelistError(f"Section '{name}' is not allowed in the WR digest.")


def current_digest(db: Session, *, current_user: User) -> WrDigest | None:
    session = _open_session(db, current_user)
    if session is None:
        return None
    return db.scalar(select(WrDigest).where(WrDigest.review_session_id == session.id))


def assemble_digest(db: Session, *, current_user: User) -> tuple[WrDigest, bool]:
    """Assemble le digest de la session WR ouverte ; rend l'existant s'il est déjà figé."""
    session = _open_session(db, current_user)
    if session is None:
        raise DigestStateError("No open weekly review: launch it before assembling the digest.", "WR_NOT_OPEN")
    existing = db.scalar(select(WrDigest).where(WrDigest.review_session_id == session.id))
    if existing is not None:
        return existing, False

    caps: dict[str, int] = get_parameter(db, "wr.digest_caps", default={})
    token_cap = int(get_parameter(db, "wr.digest_token_cap", default=40000))
    open_items = [
        item for item in docket.list_items(db, current_user=current_user) if item.status in docket.OPEN_STATUSES
    ]
    open_counts: dict[str, int] = {}
    selected: list[dict[str, Any]] = []
    for item in open_items:  # déjà triés : décisions forcées puis priorité
        open_counts[item.item_type] = open_counts.get(item.item_type, 0) + 1
        cap = caps.get(item.item_type)
        if cap is not None and open_counts[item.item_type] > cap:
            continue
        entry = item.model_dump(mode="json", include=set(ENTRY_FIELDS))
        _check_no_raw(entry["payload"])
        _check_no_raw(entry["evidence_refs"])
        selected.append(entry)

    content = _build(session, selected, open_counts, truncated=False)
    while selected and _estimate(content) > token_cap:
        selected.remove(_least_priority(selected))
        content = _build(session, selected, open_counts, truncated=True)
    for name in content:
        check_section(name)

    row = WrDigest(
        id=uuid4(), user_id=current_user.id, review_session_id=session.id, window_from=session.week_start,
        window_to=session.week_end, digest=content, token_estimate=_estimate(content),
    )
    db.add(row)
    db.flush()
    db.add(build_event(
        db, user_id=current_user.id, event_type="planning.wr_digest.assembled",
        payload={"digest_id": str(row.id), "review_session_id": str(session.id),
                 "token_estimate": row.token_estimate, "items": len(selected)},
        idempotency_key=f"planning.wr_digest.assembled.{row.id}", source_app=SourceApp.imperium,
        privacy_level=PrivacyLevel.medium,
    ))
    db.commit()
    db.refresh(row)
    return row, True


def _open_session(db: Session, current_user: User) -> ImperiumWeeklyReviewSession | None:
    session = db.scalar(
        select(ImperiumWeeklyReviewSession)
        .where(ImperiumWeeklyReviewSession.user_id == current_user.id)
        .order_by(ImperiumWeeklyReviewSession.created_at.desc())
        .limit(1)
    )
    if session is None or session.launched_at is None or session.status in CLOSED_SESSION_STATUSES:
        return None
    return session


def _build(session: ImperiumWeeklyReviewSession, selected: list[dict], open_counts: dict[str, int], *,
           truncated: bool) -> dict:
    sections: dict[str, list[dict]] = {}
    for entry in selected:
        sections.setdefault(entry["item_type"], []).append(entry)
    return {
        "window": {"from": session.week_start.isoformat(), "to": session.week_end.isoformat()},
        "docket": sections,
        "counts": {
            item_type: {"open": total, "included": len(sections.get(item_type, []))}
            for item_type, total in sorted(open_counts.items())
        },
        "truncated": truncated,
        "unavailable": list(UNAVAILABLE),
    }


def _least_priority(selected: list[dict]) -> dict:
    """Le moins prioritaire sort d'abord ; rouges et décisions forcées sortent en dernier."""
    unprotected = [entry for entry in selected if not (entry["severity"] == "red" or entry["force_decision"])]
    return (unprotected or selected)[-1]


def _estimate(content: dict) -> int:
    return math.ceil(len(json.dumps(content, ensure_ascii=False)) / 4)


def _check_no_raw(value: Any) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if key in FORBIDDEN_KEYS:
                raise DigestWhitelistError(f"Raw content key '{key}' is not allowed in the WR digest.")
            _check_no_raw(nested)
    elif isinstance(value, list):
        for nested in value:
            _check_no_raw(nested)
