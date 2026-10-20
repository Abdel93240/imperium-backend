"""chatbot V1 on the local executor: sessions, messages, proposals (doc 72 §2, §4, §5, §9, §10 ; décision : IA locale seulement)

1. `chat_sessions` / `chat_messages` : journal texte de la conversation (doc 72 §9), suppression réelle.
2. `chat_proposals` : action proposée par le modèle, JAMAIS exécutée sans validation explicite (doc 72 §4-5,
   doc 08) ; une nouvelle proposition remplace la précédente encore ouverte (`superseded`).
3. Slot `chat.converse` (local_default) dans `ai_slot_transition` ; paramètre `chat.enabled` semé false.
   Pas d'escalade (doc 72 §3) ni d'extraction à la fermeture (§6) dans cette V1 : aucun appel cloud.

Revision ID: 20261020_0115
Revises: 20261020_0114
Create Date: 2026-10-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261020_0115"
down_revision: str | None = "20261020_0114"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
ACTIONS = "('create_project', 'add_project_mission', 'create_routine')"


def upgrade() -> None:
    op.create_table(
        "chat_sessions",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("context_kind", sa.Text(), nullable=False, server_default="general"),
        sa.Column("context_ref", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="open"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('open', 'closed')", name="chat_sessions_status_check"),
        sa.CheckConstraint("context_kind IN ('general', 'project', 'mission', 'intervention')", name="chat_sessions_context_check"),
        sa.CheckConstraint("(status = 'closed') = (closed_at IS NOT NULL)", name="chat_sessions_closed_check"),
    )
    op.create_index("chat_sessions_user_started_idx", "chat_sessions", ["user_id", "started_at"])
    op.create_table(
        "chat_messages",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("session_id", UUID, sa.ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("model_used", sa.Text(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("degraded", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("role IN ('user', 'assistant')", name="chat_messages_role_check"),
        sa.CheckConstraint("length(content) <= 8000", name="chat_messages_length_check"),
    )
    op.create_index("chat_messages_session_created_idx", "chat_messages", ["session_id", "created_at"])
    op.create_table(
        "chat_proposals",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("session_id", UUID, sa.ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("message_id", UUID, sa.ForeignKey("chat_messages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("params", postgresql.JSONB(), nullable=False),
        sa.Column("summary_fr", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="proposed"),
        sa.Column("result", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(f"action IN {ACTIONS}", name="chat_proposals_action_check"),
        sa.CheckConstraint("status IN ('proposed', 'validated', 'rejected', 'superseded', 'failed')", name="chat_proposals_status_check"),
        sa.CheckConstraint("(status = 'proposed') = (decided_at IS NULL)", name="chat_proposals_decided_check"),
    )
    op.create_index("chat_proposals_session_open_idx", "chat_proposals", ["session_id"], unique=True,
                    postgresql_where=sa.text("status = 'proposed'"))
    op.execute(
        """
        INSERT INTO ai_slot_transition (id, slot_code, domain, tier, audit_sample_pct, agreement_target_pct, notes_fr)
        VALUES (gen_random_uuid(), 'chat.converse', 'imperium', 'local_default', 100, 92,
                'Chatbot : réponse et proposition d''action, toujours soumise à validation (doc 72).')
        ON CONFLICT ON CONSTRAINT ai_slot_transition_slot_code_unique DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO parameters (id, code, domain, value, unit, rationale_fr, origin, version)
        VALUES (gen_random_uuid(), 'chat.enabled', 'imperium', 'false'::jsonb, 'bool',
                'Routes du chatbot servies (doc 72) ; moteur local seulement.', 'seed', 1)
        ON CONFLICT ON CONSTRAINT parameters_code_version_unique DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE parameters DISABLE TRIGGER parameters_append_only")
    op.execute("DELETE FROM parameters WHERE code = 'chat.enabled'")
    op.execute("ALTER TABLE parameters ENABLE TRIGGER parameters_append_only")
    op.execute("DELETE FROM ai_audit_samples WHERE slot_code = 'chat.converse'")
    op.execute("DELETE FROM ai_slot_transition WHERE slot_code = 'chat.converse'")
    op.drop_table("chat_proposals")
    op.drop_table("chat_messages")
    op.drop_table("chat_sessions")
