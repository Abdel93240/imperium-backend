"""toolbox socle foundations: runner, notifications, shared tables, travel, prayer, roles

Revision ID: 20260715_0038
Revises: 20260710_0037
Create Date: 2026-07-15

Passe 0 (SOCLE TOOLBOX V1): job_definitions/job_runs/job_cursors,
notifications/notification_channels, parameters (+ append-only guard +
v_parameters_current), signal_definitions/signal_values,
ai_slot_transition/ai_audit_samples (+ v_ai_training_pairs), travel_cache,
path_registered_mosques/path_mawaqit_cache/path_calculated_prayer_times,
ai_role_models, and the events NOTIFY trigger (channel events_new).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID

revision: str = "20260715_0038"
down_revision: str | None = "20260710_0037"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- §2 runner ---
    op.create_table(
        "job_definitions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("schedule", sa.Text(), nullable=True),
        sa.Column("event_types", ARRAY(sa.Text()), nullable=True),
        sa.Column("handler_ref", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("singleton", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("timeout_s", sa.Integer(), nullable=False, server_default="900"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.UniqueConstraint("code", name="job_definitions_code_unique"),
        sa.CheckConstraint(
            "kind IN ('cron', 'event_subscription', 'manual')",
            name="job_definitions_kind_check",
        ),
        sa.CheckConstraint(
            "kind != 'cron' OR schedule IS NOT NULL",
            name="job_definitions_cron_schedule_check",
        ),
        sa.CheckConstraint("timeout_s > 0", name="job_definitions_timeout_positive"),
    )
    op.create_table(
        "job_runs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("job_code", sa.Text(), nullable=False),
        sa.Column("trigger", sa.Text(), nullable=False),
        sa.Column("trigger_ref", UUID(as_uuid=True), nullable=True),
        sa.Column("window_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("window_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("skip_reason", sa.Text(), nullable=True),
        sa.Column("items_in", sa.Integer(), nullable=True),
        sa.Column("items_out", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("detail", JSONB(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "trigger IN ('cron', 'event', 'manual', 'fallback')",
            name="job_runs_trigger_check",
        ),
        sa.CheckConstraint(
            "status IN ('running', 'completed', 'failed', 'skipped')",
            name="job_runs_status_check",
        ),
    )
    op.create_index("job_runs_job_code_created_idx", "job_runs", ["job_code", "created_at"])
    op.create_table(
        "job_cursors",
        sa.Column("job_code", sa.Text(), primary_key=True),
        sa.Column("last_processed_event_ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_processed_event_id", UUID(as_uuid=True), nullable=True),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )

    # --- §3 notifications ---
    op.create_table(
        "notifications",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("severity", sa.Text(), nullable=False),
        sa.Column("domain", sa.Text(), nullable=False),
        sa.Column("ref_type", sa.Text(), nullable=True),
        sa.Column("ref_id", UUID(as_uuid=True), nullable=True),
        sa.Column("message_fr", sa.Text(), nullable=False),
        sa.Column("channels_sent", JSONB(), nullable=False, server_default="[]"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "severity IN ('info', 'normal', 'red')", name="notifications_severity_check"
        ),
        sa.CheckConstraint(
            "domain IN ('pulse', 'wr', 'daily', 'vector', 'path', 'vault', 'system')",
            name="notifications_domain_check",
        ),
    )
    op.create_index("notifications_created_idx", "notifications", ["created_at"])
    op.create_index("notifications_ref_idx", "notifications", ["ref_type", "ref_id"])
    op.create_table(
        "notification_channels",
        sa.Column("code", sa.Text(), primary_key=True),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("config", JSONB(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default="false"),
    )

    # --- §4 shared tables ---
    op.create_table(
        "parameters",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("domain", sa.Text(), nullable=False),
        sa.Column("value", JSONB(), nullable=False),
        sa.Column("unit", sa.Text(), nullable=True),
        sa.Column("rationale_fr", sa.Text(), nullable=True),
        sa.Column("sources", JSONB(), nullable=True),
        sa.Column("origin", sa.Text(), nullable=False, server_default="seed"),
        sa.Column(
            "valid_from", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("superseded_by", UUID(as_uuid=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("code", "version", name="parameters_code_version_unique"),
    )
    op.create_foreign_key(
        "fk_parameters_superseded_by_parameters",
        "parameters",
        "parameters",
        ["superseded_by"],
        ["id"],
    )
    op.create_index("parameters_code_idx", "parameters", ["code"])
    op.execute(
        """
        CREATE FUNCTION parameters_append_only_guard() RETURNS trigger AS $$
        BEGIN
          IF TG_OP = 'DELETE' THEN
            RAISE EXCEPTION 'parameters is append-only: rows are never deleted (code=%)',
              OLD.code;
          END IF;
          IF NEW.value IS DISTINCT FROM OLD.value
             OR NEW.code IS DISTINCT FROM OLD.code
             OR NEW.domain IS DISTINCT FROM OLD.domain
             OR NEW.unit IS DISTINCT FROM OLD.unit
             OR NEW.origin IS DISTINCT FROM OLD.origin
             OR NEW.version IS DISTINCT FROM OLD.version
             OR NEW.valid_from IS DISTINCT FROM OLD.valid_from THEN
            RAISE EXCEPTION
              'parameters is append-only: insert a new version instead of updating (code=%)',
              OLD.code;
          END IF;
          IF OLD.superseded_by IS NOT NULL
             AND NEW.superseded_by IS DISTINCT FROM OLD.superseded_by THEN
            RAISE EXCEPTION
              'parameters: superseded_by can only be set once (code=%)', OLD.code;
          END IF;
          RETURN NEW;
        END $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER parameters_append_only
        BEFORE UPDATE OR DELETE ON parameters
        FOR EACH ROW EXECUTE FUNCTION parameters_append_only_guard();
        """
    )
    op.execute(
        """
        CREATE VIEW v_parameters_current AS
        SELECT DISTINCT ON (code) *
        FROM parameters
        WHERE superseded_by IS NULL
        ORDER BY code, version DESC;
        """
    )

    op.create_table(
        "signal_definitions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("domain", sa.Text(), nullable=False),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("label_fr", sa.Text(), nullable=True),
        sa.Column("unit", sa.Text(), nullable=True),
        sa.Column("source", sa.Text(), nullable=True),
        sa.Column("aggregation", sa.Text(), nullable=True),
        sa.Column("baseline_window_days", sa.Integer(), nullable=True),
        sa.Column("bands", JSONB(), nullable=True),
        sa.Column("staleness_hours", sa.Integer(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("code", name="signal_definitions_code_unique"),
    )
    op.create_index("signal_definitions_domain_idx", "signal_definitions", ["domain"])
    op.create_table(
        "signal_values",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("signal_code", sa.Text(), nullable=False),
        sa.Column("measured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("value", sa.Numeric(), nullable=True),
        sa.Column("band", sa.Text(), nullable=True),
        sa.Column("flags", JSONB(), nullable=True),
        sa.Column("stale", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("detail", JSONB(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_foreign_key(
        "fk_signal_values_signal_code_signal_definitions",
        "signal_values",
        "signal_definitions",
        ["signal_code"],
        ["code"],
    )
    op.create_index("signal_values_code_ts_idx", "signal_values", ["signal_code", "measured_at"])

    op.create_table(
        "ai_slot_transition",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("slot_code", sa.Text(), nullable=False),
        sa.Column("domain", sa.Text(), nullable=False),
        sa.Column("tier", sa.Text(), nullable=False, server_default="cloud_forced"),
        sa.Column("audit_sample_pct", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("agreement_target_pct", sa.Integer(), nullable=True),
        sa.Column("output_schema_ref", sa.Text(), nullable=True),
        sa.Column("notes_fr", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("slot_code", name="ai_slot_transition_slot_code_unique"),
        sa.CheckConstraint(
            "tier IN ('local_default', 'cloud_forced', 'routed')",
            name="ai_slot_transition_tier_check",
        ),
        sa.CheckConstraint(
            "audit_sample_pct >= 0 AND audit_sample_pct <= 100",
            name="ai_slot_transition_audit_pct_check",
        ),
    )
    op.create_table(
        "ai_audit_samples",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("slot_code", sa.Text(), nullable=False),
        sa.Column("run_ref", UUID(as_uuid=True), nullable=True),
        sa.Column("input_payload", JSONB(), nullable=True),
        sa.Column("local_output", JSONB(), nullable=True),
        sa.Column("cloud_output", JSONB(), nullable=True),
        sa.Column("agreement", sa.Boolean(), nullable=True),
        sa.Column("disagreement_reason", sa.Text(), nullable=True),
        sa.Column("user_reaction", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_foreign_key(
        "fk_ai_audit_samples_slot_code_ai_slot_transition",
        "ai_audit_samples",
        "ai_slot_transition",
        ["slot_code"],
        ["slot_code"],
    )
    op.create_index(
        "ai_audit_samples_slot_created_idx", "ai_audit_samples", ["slot_code", "created_at"]
    )
    op.execute(
        """
        CREATE VIEW v_ai_training_pairs AS
        SELECT s.id AS sample_id,
               s.slot_code,
               t.domain,
               s.input_payload,
               s.local_output,
               s.cloud_output,
               s.disagreement_reason,
               s.user_reaction,
               s.created_at
        FROM ai_audit_samples s
        JOIN ai_slot_transition t ON t.slot_code = s.slot_code
        WHERE s.agreement IS FALSE AND s.cloud_output IS NOT NULL;
        """
    )

    # --- §7 travel ---
    op.create_table(
        "travel_cache",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("origin_h3", sa.Text(), nullable=False),
        sa.Column("dest_h3", sa.Text(), nullable=False),
        sa.Column("time_slot", sa.Text(), nullable=False),
        sa.Column("profile", sa.Text(), nullable=False, server_default="planning"),
        sa.Column("duration_s", sa.Integer(), nullable=False),
        sa.Column("distance_m", sa.Integer(), nullable=True),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("multiplier_applied", sa.Numeric(), nullable=False),
        sa.Column(
            "computed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "origin_h3", "dest_h3", "time_slot", "profile", name="travel_cache_key_unique"
        ),
    )

    # --- §8 prayer (doc 41 §20 subset) ---
    op.create_table(
        "path_registered_mosques",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("mawaqit_id", sa.Text(), nullable=True),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("latitude", sa.Numeric(), nullable=True),
        sa.Column("longitude", sa.Numeric(), nullable=True),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "added_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_foreign_key(
        "fk_path_registered_mosques_user_id_users",
        "path_registered_mosques",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_table(
        "path_mawaqit_cache",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("mosque_id", UUID(as_uuid=True), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("prayer_times", JSONB(), nullable=False),
        sa.Column(
            "fetched_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("mosque_id", "date", name="path_mawaqit_cache_mosque_date_unique"),
    )
    op.create_foreign_key(
        "fk_path_mawaqit_cache_mosque_id_path_registered_mosques",
        "path_mawaqit_cache",
        "path_registered_mosques",
        ["mosque_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_table(
        "path_calculated_prayer_times",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("fajr", sa.Time(), nullable=True),
        sa.Column("dhuhr", sa.Time(), nullable=True),
        sa.Column("asr", sa.Time(), nullable=True),
        sa.Column("maghrib", sa.Time(), nullable=True),
        sa.Column("isha", sa.Time(), nullable=True),
        sa.Column("calculation_method", sa.Text(), nullable=True),
        sa.Column("madhhab", sa.Text(), nullable=True),
        sa.Column("city_reference", sa.Text(), nullable=True),
        sa.Column(
            "computed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint(
            "user_id", "date", name="path_calculated_prayer_times_user_date_unique"
        ),
    )
    op.create_foreign_key(
        "fk_path_calculated_prayer_times_user_id_users",
        "path_calculated_prayer_times",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # --- §10 roles → models ---
    op.create_table(
        "ai_role_models",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("role_code", sa.Text(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("model_id", sa.Text(), nullable=False),
        sa.Column("effort", sa.Text(), nullable=True),
        sa.Column("sensitivity_route", sa.Text(), nullable=False, server_default="direct"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("role_code", "version", name="ai_role_models_role_version_unique"),
        sa.CheckConstraint(
            "sensitivity_route IN ('direct', 'openrouter_allowed', 'local_only')",
            name="ai_role_models_sensitivity_route_check",
        ),
    )
    op.create_index("ai_role_models_role_active_idx", "ai_role_models", ["role_code", "active"])

    # --- runtime grants (doc 21: default ACL only gives SELECT+INSERT) ---
    # UPDATE stays scoped to what the runtime legitimately mutates; parameters
    # remain append-only (only superseded_by is updatable, guard-enforced above).
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'imperium_user') THEN
            GRANT UPDATE ON job_runs, job_cursors, job_definitions,
                            notifications, notification_channels,
                            ai_slot_transition,
                            path_registered_mosques, path_calculated_prayer_times
              TO imperium_user;
            GRANT UPDATE (superseded_by) ON parameters TO imperium_user;
            GRANT UPDATE, DELETE ON travel_cache, path_mawaqit_cache TO imperium_user;
          END IF;
        END $$;
        """
    )

    # --- §6 events NOTIFY (E2 consumption contract wake-up) ---
    op.execute(
        """
        CREATE FUNCTION events_notify_new() RETURNS trigger AS $$
        BEGIN
          PERFORM pg_notify('events_new', NEW.id::text);
          RETURN NEW;
        END $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER events_notify_new_trigger
        AFTER INSERT ON events
        FOR EACH ROW EXECUTE FUNCTION events_notify_new();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS events_notify_new_trigger ON events")
    op.execute("DROP FUNCTION IF EXISTS events_notify_new()")
    op.drop_index("ai_role_models_role_active_idx", table_name="ai_role_models")
    op.drop_table("ai_role_models")
    op.drop_table("path_calculated_prayer_times")
    op.drop_table("path_mawaqit_cache")
    op.drop_table("path_registered_mosques")
    op.drop_table("travel_cache")
    op.execute("DROP VIEW IF EXISTS v_ai_training_pairs")
    op.drop_index("ai_audit_samples_slot_created_idx", table_name="ai_audit_samples")
    op.drop_table("ai_audit_samples")
    op.drop_table("ai_slot_transition")
    op.drop_index("signal_values_code_ts_idx", table_name="signal_values")
    op.drop_table("signal_values")
    op.drop_index("signal_definitions_domain_idx", table_name="signal_definitions")
    op.drop_table("signal_definitions")
    op.execute("DROP VIEW IF EXISTS v_parameters_current")
    op.execute("DROP TRIGGER IF EXISTS parameters_append_only ON parameters")
    op.execute("DROP FUNCTION IF EXISTS parameters_append_only_guard()")
    op.drop_index("parameters_code_idx", table_name="parameters")
    op.drop_table("parameters")
    op.drop_table("notification_channels")
    op.drop_index("notifications_ref_idx", table_name="notifications")
    op.drop_index("notifications_created_idx", table_name="notifications")
    op.drop_table("notifications")
    op.drop_table("job_cursors")
    op.drop_index("job_runs_job_code_created_idx", table_name="job_runs")
    op.drop_table("job_runs")
    op.drop_table("job_definitions")
