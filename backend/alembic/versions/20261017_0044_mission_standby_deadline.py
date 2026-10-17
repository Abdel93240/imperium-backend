"""mission standby status and deadline_at

Décision utilisateur 2026-10-16 (doc 43 §5.4) : à la clôture de journée, une
mission non faite dont l'échéance est dépassée passe en `standby` (attend une
décision : nouvelle échéance, faite ou annulée). `deadline_at` porte l'échéance.

Revision ID: 20261017_0044
Revises: 20261017_0043
Create Date: 2026-10-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261017_0044"
down_revision: str | None = "20261017_0043"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MISSION_STATUS_CHECK = "status IN ('backlog', 'active', 'completed', 'failed', 'abandoned', 'cancelled', 'standby')"
LEGACY_MISSION_STATUS_CHECK = "status IN ('backlog', 'active', 'completed', 'failed', 'abandoned', 'cancelled')"


def upgrade() -> None:
    op.add_column("imperium_missions", sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=True))
    op.drop_constraint(
        op.f("ck_imperium_missions_imperium_missions_status_check"),
        "imperium_missions",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_imperium_missions_imperium_missions_status_check"),
        "imperium_missions",
        MISSION_STATUS_CHECK,
    )
    op.create_index(
        "imperium_missions_user_standby_idx",
        "imperium_missions",
        ["user_id"],
        postgresql_where=sa.text("status = 'standby'"),
    )


def downgrade() -> None:
    op.drop_index("imperium_missions_user_standby_idx", table_name="imperium_missions")
    # Retour arrière : les missions en standby retournent au backlog avant de resserrer la contrainte.
    op.execute("UPDATE imperium_missions SET status = 'backlog' WHERE status = 'standby'")
    op.drop_constraint(
        op.f("ck_imperium_missions_imperium_missions_status_check"),
        "imperium_missions",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_imperium_missions_imperium_missions_status_check"),
        "imperium_missions",
        LEGACY_MISSION_STATUS_CHECK,
    )
    op.drop_column("imperium_missions", "deadline_at")
