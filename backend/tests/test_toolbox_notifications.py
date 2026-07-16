"""§13.3 notifications: routing, 24 h dedup + escalation, bot ≠ orchestrator bot."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select, text

from _postgres import require_test_database_url

pytest.importorskip("psycopg")

from sqlalchemy.orm import Session  # noqa: E402

from app.models.toolbox import Notification, NotificationChannel  # noqa: E402
from app.services.notifications import (  # noqa: E402
    FORBIDDEN_ORCHESTRATOR_ENV_KEYS,
    notify,
    validate_telegram_channel_config,
)


@pytest.fixture(scope="module")
def engine():
    engine = create_engine(require_test_database_url("toolbox notifications tests"), future=True)
    yield engine
    engine.dispose()


@pytest.fixture()
def db(engine):
    with Session(engine) as session:
        yield session
        session.rollback()


def _enable_channels(db: Session) -> None:
    for code, enabled in (("telegram_prod", True), ("inapp", True)):
        channel = db.get(NotificationChannel, code)
        channel.enabled = enabled
    db.flush()


def test_red_routes_to_all_enabled_channels_normal_to_primary_only(db, monkeypatch) -> None:
    _enable_channels(db)
    sent_messages = []
    monkeypatch.setattr(
        "app.services.notifications._send_telegram",
        lambda channel, message: sent_messages.append((channel.code, message)),
    )
    from types import SimpleNamespace

    monkeypatch.setattr(
        "app.services.notifications.get_settings",
        lambda: SimpleNamespace(notifications_enabled=True),
    )

    red = notify(db, severity="red", domain="system", message_fr="Alerte rouge test.")
    assert set(red.channels_sent) == {"telegram_prod", "inapp"}

    # normal|info → primary channel only (telegram_prod is seeded primary).
    normal = notify(db, severity="normal", domain="system", message_fr="Info normale test.")
    assert normal.channels_sent == ["telegram_prod"]
    assert [code for code, _ in sent_messages] == ["telegram_prod", "telegram_prod"]


def test_dedup_24h_same_ref_unless_severity_escalates(db) -> None:
    _enable_channels(db)
    ref = ("docket_item", uuid4())

    first = notify(db, severity="normal", domain="wr", message_fr="Premier signal.", ref=ref)
    assert first is not None

    duplicate = notify(db, severity="normal", domain="wr", message_fr="Répétition.", ref=ref)
    assert duplicate is None  # deduplicated inside the 24 h window

    lower = notify(db, severity="info", domain="wr", message_fr="Moins grave.", ref=ref)
    assert lower is None  # lower severity is deduplicated too

    escalated = notify(db, severity="red", domain="wr", message_fr="Montée en rouge.", ref=ref)
    assert escalated is not None  # severity escalation always goes through

    rows = db.scalars(
        select(Notification).where(Notification.ref_id == ref[1])
    ).all()
    assert len(rows) == 2


def test_notifications_disabled_flag_keeps_row_but_skips_delivery(db, monkeypatch) -> None:
    _enable_channels(db)
    from types import SimpleNamespace

    monkeypatch.setattr(
        "app.services.notifications.get_settings",
        lambda: SimpleNamespace(notifications_enabled=False),
    )
    monkeypatch.setattr(
        "app.services.notifications._send_telegram",
        lambda channel, message: pytest.fail("delivery must be dry-run when flag is off"),
    )

    stored = notify(db, severity="red", domain="system", message_fr="Rouge sans canal externe.")
    # inapp = the table itself, so the row still counts as delivered in-app.
    assert stored.channels_sent == ["inapp"]


def test_telegram_prod_config_is_distinct_from_orchestrator_bot(db) -> None:
    channel = db.get(NotificationChannel, "telegram_prod")
    config = channel.config
    # The seeded config uses env REFS only, never the orchestrator's variables
    # (audit F1-11: /opt/orchestrator/telegram_bot.py is dev tooling).
    validate_telegram_channel_config(config)
    assert config["bot_token_env"].startswith("IMPERIUM_TELEGRAM_PROD_")
    assert config["chat_id_env"].startswith("IMPERIUM_TELEGRAM_PROD_")
    assert not set(config.values()) & FORBIDDEN_ORCHESTRATOR_ENV_KEYS

    with pytest.raises(ValueError):
        validate_telegram_channel_config(
            {"bot_token_env": "TELEGRAM_BOT_TOKEN", "chat_id_env": "IMPERIUM_TELEGRAM_PROD_CHAT_ID"}
        )
    with pytest.raises(ValueError):
        validate_telegram_channel_config({"TELEGRAM_BOT_TOKEN": "x", "chat_id_env": "y"})


def test_notification_rows_expose_inapp_read_state(db) -> None:
    stored = notify(db, severity="info", domain="path", message_fr="Bannière in-app.")
    assert stored.read_at is None and stored.acked_at is None
    unread = db.execute(
        text("SELECT count(*) FROM notifications WHERE read_at IS NULL")
    ).scalar()
    assert unread >= 1
