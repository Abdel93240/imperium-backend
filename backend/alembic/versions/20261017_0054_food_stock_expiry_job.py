"""job pulse.food_stock_expiry (alertes de date limite, doc 40 §11.3)

Le planificateur compte en UTC : le job est planifié à 7 h et 8 h UTC et n'agit qu'à
9 h heure de Paris (été comme hiver). Semé DÉSACTIVÉ comme les autres jobs ;
l'activation suit la feuille d'activation (doc 76).

Revision ID: 20261017_0054
Revises: 20261017_0053
Create Date: 2026-10-17
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20261017_0054"
down_revision: str | None = "20261017_0053"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JOB_CODE = "pulse.food_stock_expiry"
HANDLER_REF = "app.services.pulse.expiry:food_stock_expiry_job"


def upgrade() -> None:
    op.get_bind().exec_driver_sql(
        """
        INSERT INTO job_definitions
          (id, code, kind, schedule, event_types, handler_ref, enabled, singleton, timeout_s)
        VALUES (gen_random_uuid(), %s, 'cron', '0 7,8 * * *', NULL, %s, false, true, 120)
        ON CONFLICT ON CONSTRAINT job_definitions_code_unique DO NOTHING
        """,
        (JOB_CODE, HANDLER_REF),
    )


def downgrade() -> None:
    op.get_bind().exec_driver_sql("DELETE FROM job_definitions WHERE code = %s", (JOB_CODE,))
