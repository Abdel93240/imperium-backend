"""toolbox socle seeds: parameters, notification channels, job definitions, ai roles

Revision ID: 20260715_0039
Revises: 20260715_0038
Create Date: 2026-07-15

Seeds are idempotent (ON CONFLICT DO NOTHING) and reversible (downgrade removes
exactly the seeded rows, temporarily disabling the parameters append-only guard).
Every job_definition is seeded enabled=false (doc 76 CF-4/CF-6): activation is an
explicit journalised UPDATE, never a merge side effect.
"""

import json
from collections.abc import Sequence

from alembic import op

revision: str = "20260715_0039"
down_revision: str | None = "20260715_0038"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


PARAMETERS: list[tuple[str, str, object, str | None, str]] = [
    # (code, domain, value, unit, rationale_fr)
    ("toolbox.h3_res", "toolbox", 8, None, "Résolution H3 par défaut (spec socle §7)."),
    (
        "toolbox.travel_floor",
        "toolbox",
        1.3,
        "ratio",
        "Plancher dur ×1,3 sur toute estimation de trajet (doublonné en constante code, "
        "le code applique max(param, 1.3)).",
    ),
    ("toolbox.travel_cache_ttl_min", "toolbox", 120, "min", "TTL du cache travel (2 h)."),
    (
        "toolbox.fallback_speed_kmh",
        "toolbox",
        25,
        "km/h",
        "Vitesse du fallback hors-ligne distance/25 × 1,3.",
    ),
    (
        "toolbox.topk_threshold",
        "toolbox",
        0.35,
        "score",
        "Seuil final_score de la recherche top-K (doc 38 §9.2).",
    ),
    (
        "path.calc_method",
        "path",
        "MuslimWorldLeague",
        None,
        "Méthode de calcul fallback (doc 41 §6.4, défaut V1).",
    ),
    ("path.madhhab", "path", "Maliki", None, "Règle Asr / madhhab (doc 41 §6.4, défaut V1)."),
    (
        "path.reference_mosque_id",
        "path",
        None,
        None,
        "UUID path_registered_mosques de la mosquée de référence (doc 41 §6.3 : une seule). "
        "NULL tant que l'utilisateur ne l'a pas enregistrée.",
    ),
    (
        "path.window_before_min",
        "path",
        0,
        "min",
        "Début de fenêtre de prière = adhan + before (spec socle §8).",
    ),
    (
        "path.window_after_min",
        "path",
        30,
        "min",
        "Fin de fenêtre = adhan + after. Doc 41 §7-bis ne fige AUCUNE valeur "
        "(fenêtre contextuelle au planning) : 30 min est un défaut de socle, "
        "révisable par nouvelle version de paramètre.",
    ),
    ("notify.dedup_hours", "system", 24, "h", "Idempotence notifications (spec socle §3)."),
]


NOTIFICATION_CHANNELS = [
    # telegram_prod: bot PRODUIT, distinct du bot d'orchestration de build
    # (/opt/orchestrator/telegram_bot.py, audit F1-11). Les valeurs sont des REFS env,
    # jamais des secrets en dur.
    (
        "telegram_prod",
        "telegram",
        {
            "bot_token_env": "IMPERIUM_TELEGRAM_PROD_BOT_TOKEN",
            "chat_id_env": "IMPERIUM_TELEGRAM_PROD_CHAT_ID",
        },
        False,  # enabled quand le bot produit est créé (action utilisateur)
        True,  # canal primaire (Q3 gravée : Telegram d'abord)
    ),
    # inapp: la table notifications elle-même — les façades lisent les non-lues.
    ("inapp", "inapp", {}, True, False),
]


JOB_DEFINITIONS = [
    # (code, kind, schedule, event_types, handler_ref, timeout_s)
    (
        "system.events_heartbeat",
        "event_subscription",
        None,
        None,  # NULL = tous les types (consommateur de smoke du contrat E2)
        "app.services.runner.jobs:events_heartbeat",
        120,
    ),
    (
        "path.mawaqit_refresh",
        "cron",
        "0 3 * * *",
        None,
        "app.services.path.prayer:mawaqit_refresh_job",
        300,
    ),
    (
        "system.backup_nightly",
        "cron",
        "0 4 * * *",
        None,
        "app.services.runner.jobs:backup_nightly",
        3600,
    ),
]


AI_ROLE_MODELS = [
    # (role_code, provider, model_id, effort, sensitivity_route)
    # Seed = doc 30 §3 ACTUEL avec Fable 5 rétabli (01/07/2026, patch doc 30 §7.8).
    ("local_executor", "local", "qwen3-32b", None, "local_only"),
    ("embedding_service", "local", "qwen3-embedding:8b", None, "local_only"),
    ("first_cloud_tier", "anthropic", "claude-sonnet-4-6", None, "openrouter_allowed"),
    ("high_reasoning", "anthropic", "claude-opus-4-8", None, "openrouter_allowed"),
    # WR re-planning : contenu personnel dense → accès direct, pas d'intermédiaire.
    ("sustained_long_context", "anthropic", "claude-fable-5", None, "direct"),
    ("health_specialist", "openai", "gpt-5.5", None, "direct"),
    ("finance_specialist", "openai", "gpt-5.5", None, "direct"),
    ("web_fresh_data", "openai", "gpt-5.5", None, "openrouter_allowed"),
    # Noms concrets locaux : F10 §5-quater reste propriétaire.
    ("ocr_service", "local", "paddleocr-vl-1.6", None, "local_only"),
    ("transcription_service", "local", "faster-whisper-large-v3", None, "local_only"),
]


def upgrade() -> None:
    conn = op.get_bind()
    for code, domain, value, unit, rationale in PARAMETERS:
        conn.exec_driver_sql(
            """
            INSERT INTO parameters (id, code, domain, value, unit, rationale_fr, origin, version)
            VALUES (gen_random_uuid(), %s, %s, %s::jsonb, %s, %s, 'seed', 1)
            ON CONFLICT ON CONSTRAINT parameters_code_version_unique DO NOTHING
            """,
            (code, domain, json.dumps(value), unit, rationale),
        )
    for code, kind, config, enabled, is_primary in NOTIFICATION_CHANNELS:
        conn.exec_driver_sql(
            """
            INSERT INTO notification_channels (code, kind, config, enabled, is_primary)
            VALUES (%s, %s, %s::jsonb, %s, %s)
            ON CONFLICT (code) DO NOTHING
            """,
            (code, kind, json.dumps(config), enabled, is_primary),
        )
    for code, kind, schedule, event_types, handler_ref, timeout_s in JOB_DEFINITIONS:
        conn.exec_driver_sql(
            """
            INSERT INTO job_definitions
              (id, code, kind, schedule, event_types, handler_ref, enabled, singleton, timeout_s)
            VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, false, true, %s)
            ON CONFLICT ON CONSTRAINT job_definitions_code_unique DO NOTHING
            """,
            (code, kind, schedule, event_types, handler_ref, timeout_s),
        )
    for role_code, provider, model_id, effort, sensitivity_route in AI_ROLE_MODELS:
        conn.exec_driver_sql(
            """
            INSERT INTO ai_role_models
              (id, role_code, provider, model_id, effort, sensitivity_route, version, active)
            VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, 1, true)
            ON CONFLICT ON CONSTRAINT ai_role_models_role_version_unique DO NOTHING
            """,
            (role_code, provider, model_id, effort, sensitivity_route),
        )


def downgrade() -> None:
    conn = op.get_bind()
    role_codes = tuple(role[0] for role in AI_ROLE_MODELS)
    conn.exec_driver_sql(
        "DELETE FROM ai_role_models WHERE role_code = ANY(%s) AND version = 1",
        (list(role_codes),),
    )
    job_codes = [job[0] for job in JOB_DEFINITIONS]
    conn.exec_driver_sql("DELETE FROM job_definitions WHERE code = ANY(%s)", (job_codes,))
    channel_codes = [channel[0] for channel in NOTIFICATION_CHANNELS]
    conn.exec_driver_sql(
        "DELETE FROM notification_channels WHERE code = ANY(%s)", (channel_codes,)
    )
    param_codes = [parameter[0] for parameter in PARAMETERS]
    conn.exec_driver_sql("ALTER TABLE parameters DISABLE TRIGGER parameters_append_only")
    try:
        conn.exec_driver_sql(
            "DELETE FROM parameters WHERE code = ANY(%s) AND version = 1 AND origin = 'seed'",
            (param_codes,),
        )
    finally:
        conn.exec_driver_sql("ALTER TABLE parameters ENABLE TRIGGER parameters_append_only")
