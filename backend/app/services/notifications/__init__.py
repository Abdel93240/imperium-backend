"""toolbox.notifications — notify() multi-canal, Telegram d'abord (Q3 gravée).

Routing policy (graved): red → ALL enabled channels; normal|info → primary
channel only. The inapp channel IS the notifications table (facades read the
unread rows). Idempotence: a same (ref_type, ref_id, severity) notifies at most
once per notify.dedup_hours (24 h) unless severity escalates.

The telegram_prod channel is a PRODUCT bot, strictly distinct from the build
orchestration bot (/opt/orchestrator/telegram_bot.py — dev tooling, audit
F1-11): its config only holds env REFS (IMPERIUM_TELEGRAM_PROD_*), never the
orchestrator's variables, and never secrets in the database.
"""

import json
import logging
import os
import urllib.request
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.toolbox import Notification, NotificationChannel
from app.services.params import get_parameter

logger = logging.getLogger(__name__)

SEVERITY_ORDER = {"info": 0, "normal": 1, "red": 2}

# Env-ref keys the product bot config uses. The orchestrator bot's variables
# (TELEGRAM_BOT_TOKEN & co) are FORBIDDEN here — enforced by tests.
TELEGRAM_PROD_TOKEN_ENV = "IMPERIUM_TELEGRAM_PROD_BOT_TOKEN"  # nosec B105 - env var NAME, not a secret
TELEGRAM_PROD_CHAT_ENV = "IMPERIUM_TELEGRAM_PROD_CHAT_ID"
FORBIDDEN_ORCHESTRATOR_ENV_KEYS = {"TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"}


def notify(
    db: Session,
    *,
    severity: str,
    domain: str,
    message_fr: str,
    ref: tuple[str, UUID | None] | None = None,
) -> Notification | None:
    """Store a notification and fan it out per the graved routing policy.

    Returns None when deduplicated (same ref+severity inside the dedup window
    without a severity escalation).
    """
    if severity not in SEVERITY_ORDER:
        raise ValueError(f"Unknown severity '{severity}'.")

    ref_type, ref_id = ref if ref is not None else (None, None)
    if _is_duplicate(db, severity=severity, ref_type=ref_type, ref_id=ref_id):
        logger.info(
            "Notification deduplicated.",
            extra={"ref_type": ref_type, "ref_id": str(ref_id), "severity": severity},
        )
        return None

    notification = Notification(
        id=uuid4(),
        severity=severity,
        domain=domain,
        ref_type=ref_type,
        ref_id=ref_id,
        message_fr=message_fr,
        channels_sent=[],
    )
    db.add(notification)
    db.flush()

    sent = _route(db, notification)
    notification.channels_sent = sent
    db.flush()
    return notification


def _is_duplicate(
    db: Session, *, severity: str, ref_type: str | None, ref_id: UUID | None
) -> bool:
    if ref_type is None and ref_id is None:
        return False
    dedup_hours = int(get_parameter(db, "notify.dedup_hours", default=24))
    threshold = datetime.now(UTC) - timedelta(hours=dedup_hours)
    previous = db.scalars(
        select(Notification).where(
            Notification.ref_type == ref_type,
            Notification.ref_id == ref_id,
            Notification.created_at >= threshold,
        )
    ).all()
    if not previous:
        return False
    max_previous = max(SEVERITY_ORDER[row.severity] for row in previous)
    # Escalation always goes through; same-or-lower severity is deduplicated.
    return SEVERITY_ORDER[severity] <= max_previous


def _route(db: Session, notification: Notification) -> list[str]:
    """red → all enabled channels; normal|info → primary channel only.

    inapp needs no delivery (the table is the channel); other channels are
    attempted and never raise (a notification failure must not break callers).
    """
    settings = get_settings()
    channels = db.scalars(
        select(NotificationChannel).where(NotificationChannel.enabled.is_(True))
    ).all()
    if notification.severity == "red":
        targets = channels
    else:
        targets = [channel for channel in channels if channel.is_primary]

    sent: list[str] = []
    for channel in targets:
        if channel.kind == "inapp":
            sent.append(channel.code)
            continue
        if not settings.notifications_enabled:
            logger.info(
                "notifications_enabled=False: delivery dry-run.",
                extra={"channel": channel.code, "notification_id": str(notification.id)},
            )
            continue
        try:
            if channel.kind == "telegram":
                _send_telegram(channel, notification.message_fr)
                sent.append(channel.code)
            else:
                logger.warning("Unknown channel kind.", extra={"channel": channel.code})
        except Exception:  # noqa: BLE001 - delivery failure is logged, never raised
            logger.exception("Channel delivery failed.", extra={"channel": channel.code})
    return sent


def validate_telegram_channel_config(config: dict) -> None:
    """Reject any config that could point at the build orchestration bot."""
    keys = set(config.keys())
    if keys & FORBIDDEN_ORCHESTRATOR_ENV_KEYS:
        raise ValueError(
            "telegram_prod must not reuse the build orchestrator bot variables (F1-11)."
        )
    token_env = config.get("bot_token_env")
    chat_env = config.get("chat_id_env")
    if token_env in FORBIDDEN_ORCHESTRATOR_ENV_KEYS or chat_env in FORBIDDEN_ORCHESTRATOR_ENV_KEYS:
        raise ValueError(
            "telegram_prod env refs must be distinct from the orchestrator bot (F1-11)."
        )
    if not token_env or not chat_env:
        raise ValueError("telegram channel config requires bot_token_env and chat_id_env refs.")


def _send_telegram(channel: NotificationChannel, message_fr: str) -> None:
    config = channel.config or {}
    validate_telegram_channel_config(config)
    token = os.environ.get(config["bot_token_env"])
    chat_id = os.environ.get(config["chat_id_env"])
    if not token or not chat_id:
        raise RuntimeError(
            f"Telegram channel '{channel.code}' env refs are not set; cannot deliver."
        )
    body = json.dumps({"chat_id": chat_id, "text": message_fr}).encode("utf-8")
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:  # nosec B310
        response.read()
