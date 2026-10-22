"""vector: pause et reprise d'une session (kit Vector final 2026-10-22, écart backend « pause_reprise »)

Le kit garde Mettre en pause / Reprendre dans Ma session ; le contrat n'avait que active|completed. Statut `paused`,
`paused_at` (pause en cours) et `paused_seconds` (pauses terminées) : la durée active = écoulé − pauses ; la durée
totale reste affichée telle quelle. Une seule session ouverte (active ou en pause) par utilisateur.

Revision ID: 20261022_0137
Revises: 20261022_0136
Create Date: 2026-10-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261022_0137"
down_revision: str | None = "20261022_0136"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("rides_sessions", sa.Column("paused_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("rides_sessions", sa.Column("paused_seconds", sa.Integer(), nullable=False, server_default="0"))
    op.drop_constraint("status_check", "rides_sessions", type_="check")
    op.create_check_constraint("status_check", "rides_sessions", "status IN ('active', 'paused', 'completed')")
    op.create_check_constraint("paused_has_time", "rides_sessions", "(status = 'paused') = (paused_at IS NOT NULL)")
    op.drop_index("rides_sessions_one_active_idx", table_name="rides_sessions")
    op.create_index("rides_sessions_one_active_idx", "rides_sessions", ["user_id"], unique=True,
                    postgresql_where=sa.text("status IN ('active', 'paused')"))


def downgrade() -> None:
    op.execute("UPDATE rides_sessions SET status = 'active', paused_at = NULL WHERE status = 'paused'")
    op.drop_index("rides_sessions_one_active_idx", table_name="rides_sessions")
    op.create_index("rides_sessions_one_active_idx", "rides_sessions", ["user_id"], unique=True,
                    postgresql_where=sa.text("status = 'active'"))
    op.drop_constraint("paused_has_time", "rides_sessions", type_="check")
    op.drop_constraint("status_check", "rides_sessions", type_="check")
    op.create_check_constraint("status_check", "rides_sessions", "status IN ('active', 'completed')")
    op.drop_column("rides_sessions", "paused_seconds")
    op.drop_column("rides_sessions", "paused_at")
