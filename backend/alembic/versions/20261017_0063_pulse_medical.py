"""pulse medical documents + rules (doc 34) sous consentement « medical » + job de rétention

Documents envoyés sous double consentement (domaine + envoi, doc 34 §5), fichier hors
base (droits 0600, nom interne), conservés 90 jours par défaut (§11). Règles saisies
à la main en V1 (extraction automatique pas encore), proposées puis activées avec
confirmation explicite (§10.1) ; une règle critique demande un accusé de lecture.
Job `pulse.medical_retention` (semé désactivé) : purge des documents arrivés au
terme et passage des règles échues en expired (§11, §15.3).

Revision ID: 20261017_0063
Revises: 20261017_0062
Create Date: 2026-10-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261017_0063"
down_revision: str | None = "20261017_0062"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
DOC_TYPES = ("prescription", "blood_test", "imaging_report", "certificate", "physio_note", "allergy_note",
             "consultation_summary", "vaccination", "other")
RULE_TYPES = ("workout_limit", "nutrition_constraint", "fasting_caution", "pain_watch", "medication_note", "general_context")
JOB_CODE = "pulse.medical_retention"
HANDLER_REF = "app.services.pulse.medical:medical_retention_job"


def _in(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def upgrade() -> None:
    op.create_table(
        "pulse_medical_documents",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("doc_type", sa.Text(), nullable=False),
        sa.Column("doc_date", sa.Date(), nullable=True),
        sa.Column("original_name", sa.Text(), nullable=False),
        sa.Column("mime_type", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.Text(), nullable=False),
        sa.Column("storage_name", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("consent_version", sa.Text(), nullable=False),
        sa.Column("consent_scope", sa.Text(), nullable=False),
        sa.Column("consented_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("retention_delete_after", sa.DateTime(timezone=True), nullable=False),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("request_hash", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(f"doc_type IN ({_in(DOC_TYPES)})", name="doc_type_check"),
        sa.CheckConstraint(
            "status IN ('uploaded', 'extracting', 'needs_validation', 'validated', 'failed')", name="status_check"
        ),
        sa.CheckConstraint("size_bytes > 0", name="size_positive"),
    )
    op.create_index("pulse_medical_documents_user_created_idx", "pulse_medical_documents", ["user_id", "created_at"])
    op.create_index(
        "pulse_medical_documents_user_idempotency_idx", "pulse_medical_documents", ["user_id", "idempotency_key"],
        unique=True,
    )
    op.create_index("pulse_medical_documents_retention_idx", "pulse_medical_documents", ["retention_delete_after"])
    op.create_table(
        "pulse_medical_rules",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_document_id", UUID, sa.ForeignKey("pulse_medical_documents.id", ondelete="SET NULL"), nullable=True),
        sa.Column("rule_type", sa.Text(), nullable=False),
        sa.Column("rule_text", sa.Text(), nullable=False),
        sa.Column("source_quote", sa.Text(), nullable=True),
        sa.Column("severity", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.Date(), nullable=True),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("critical_acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("superseded_by", UUID, sa.ForeignKey("pulse_medical_rules.id", ondelete="SET NULL"), nullable=True),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("request_hash", sa.Text(), nullable=False),
        sa.Column("activation_idempotency_key", sa.Text(), nullable=True),
        sa.Column("activation_request_hash", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(f"rule_type IN ({_in(RULE_TYPES)})", name="rule_type_check"),
        sa.CheckConstraint("severity IN ('info', 'warning', 'critical')", name="severity_check"),
        sa.CheckConstraint(
            "status IN ('proposed', 'active', 'inactive', 'expired', 'superseded')", name="status_check"
        ),
        sa.CheckConstraint("length(btrim(rule_text)) > 0", name="rule_text_not_blank"),
    )
    op.create_index(
        "pulse_medical_rules_active_idx", "pulse_medical_rules", ["user_id", "rule_type", "status"],
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_index(
        "pulse_medical_rules_user_idempotency_idx", "pulse_medical_rules", ["user_id", "idempotency_key"], unique=True
    )
    op.get_bind().exec_driver_sql(
        """
        INSERT INTO job_definitions
          (id, code, kind, schedule, event_types, handler_ref, enabled, singleton, timeout_s)
        VALUES (gen_random_uuid(), %s, 'cron', '0 3 * * *', NULL, %s, false, true, 300)
        ON CONFLICT ON CONSTRAINT job_definitions_code_unique DO NOTHING
        """,
        (JOB_CODE, HANDLER_REF),
    )


def downgrade() -> None:
    op.get_bind().exec_driver_sql("DELETE FROM job_definitions WHERE code = %s", (JOB_CODE,))
    op.drop_index("pulse_medical_rules_user_idempotency_idx", table_name="pulse_medical_rules")
    op.drop_index("pulse_medical_rules_active_idx", table_name="pulse_medical_rules")
    op.drop_table("pulse_medical_rules")
    op.drop_index("pulse_medical_documents_retention_idx", table_name="pulse_medical_documents")
    op.drop_index("pulse_medical_documents_user_idempotency_idx", table_name="pulse_medical_documents")
    op.drop_index("pulse_medical_documents_user_created_idx", table_name="pulse_medical_documents")
    op.drop_table("pulse_medical_documents")
