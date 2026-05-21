"""allow weekly review chatbot flow states

Revision ID: 20260501_0016
Revises: 20260501_0015
Create Date: 2026-05-01
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260501_0016"
down_revision: str | None = "20260501_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


SESSION_STATUS_CHECK = (
    "status IN ("
    "'ready', 'launched', 'preparing_initial_summary', 'initial_summary_ready', "
    "'waiting_for_user_answer', 'conversation_active', 'integrating_answers', 'draft_ready', "
    "'revision_requested', 'final_ready', 'approved', 'stored', 'cancelled', 'failed'"
    ")"
)
OLD_SESSION_STATUS_CHECK = (
    "status IN ("
    "'ready', 'launched', 'preparing_initial_summary', 'initial_summary_ready', "
    "'waiting_for_user_answer', 'integrating_answers', 'draft_ready', "
    "'revision_requested', 'final_ready', 'approved', 'stored', 'cancelled', 'failed'"
    ")"
)
MESSAGE_TYPE_CHECK = (
    "message_type IN ("
    "'user_answer', 'clarification_question', 'initial_summary', 'draft', "
    "'revision_request', 'final_report', 'system_note', "
    "'chat_message', 'assistant_followup', 'final_report_draft'"
    ")"
)
OLD_MESSAGE_TYPE_CHECK = (
    "message_type IN ("
    "'user_answer', 'clarification_question', 'initial_summary', 'draft', "
    "'revision_request', 'final_report', 'system_note'"
    ")"
)


def upgrade() -> None:
    op.drop_constraint(
        "imperium_weekly_review_sessions_status_check",
        "imperium_weekly_review_sessions",
        type_="check",
    )
    op.create_check_constraint(
        "imperium_weekly_review_sessions_status_check",
        "imperium_weekly_review_sessions",
        SESSION_STATUS_CHECK,
    )
    op.drop_constraint(
        "imperium_weekly_review_messages_type_check",
        "imperium_weekly_review_messages",
        type_="check",
    )
    op.create_check_constraint(
        "imperium_weekly_review_messages_type_check",
        "imperium_weekly_review_messages",
        MESSAGE_TYPE_CHECK,
    )


def downgrade() -> None:
    # Downgrade requires removing rows that use chatbot-only statuses/types first.
    op.drop_constraint(
        "imperium_weekly_review_messages_type_check",
        "imperium_weekly_review_messages",
        type_="check",
    )
    op.create_check_constraint(
        "imperium_weekly_review_messages_type_check",
        "imperium_weekly_review_messages",
        OLD_MESSAGE_TYPE_CHECK,
    )
    op.drop_constraint(
        "imperium_weekly_review_sessions_status_check",
        "imperium_weekly_review_sessions",
        type_="check",
    )
    op.create_check_constraint(
        "imperium_weekly_review_sessions_status_check",
        "imperium_weekly_review_sessions",
        OLD_SESSION_STATUS_CHECK,
    )
