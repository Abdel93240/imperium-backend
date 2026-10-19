"""daily scores refresh: coefficients freed from ×10/8/5/4 checks, refresh and day-start jobs seeded disabled (spec Daily §4.6, ACT-DLY-03)

1. Les CHECK qui figeaient les coefficients (imperium_user_priorities : position ↔ 10/8/5/4 ;
   imperium_mission_scores : 10/8/5/4) contredisent `df.coefficient_by_position` réglable
   (ACT-DLY-02) : remplacés par `coefficient > 0`. Downgrade : les anciens CHECK reviennent (échoue
   si un coefficient réglé hors 10/8/5/4 a déjà été écrit — attendu).
2. Jobs semés désactivés : `daily.scores_refresh` (cron 04:30 et 05:30 UTC ; le handler ne tourne
   qu'à 6 h de Paris, été comme hiver) et `daily.day_start` (abonné à `planning.day.started` :
   refresh ; la sélection du Niveau 1 n'est pas codée, no-op journalisé).

Revision ID: 20261019_0103
Revises: 20261019_0102
Create Date: 2026-10-19
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20261019_0103"
down_revision: str | None = "20261019_0102"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Noms réels tronqués par la convention de nommage (63 caractères) : retrouvés par leur définition.
_DROP_FIXED_COEFFICIENT_CHECKS = """
DO $$
DECLARE target record;
BEGIN
  FOR target IN
    SELECT conrelid::regclass AS tbl, conname FROM pg_constraint
    WHERE contype = 'c'
      AND conrelid IN ('imperium_user_priorities'::regclass, 'imperium_mission_scores'::regclass)
      AND (pg_get_constraintdef(oid) LIKE '%coefficient = 10)%'
           OR pg_get_constraintdef(oid) LIKE '%coefficient = ANY (ARRAY[10, 8, 5, 4])%')
  LOOP
    EXECUTE format('ALTER TABLE %s DROP CONSTRAINT %I', target.tbl, target.conname);
  END LOOP;
END $$;
"""


def upgrade() -> None:
    op.execute(_DROP_FIXED_COEFFICIENT_CHECKS)
    op.execute("ALTER TABLE imperium_user_priorities ADD CONSTRAINT ck_imperium_user_priorities_coefficient_positive "
               "CHECK (coefficient > 0)")
    op.execute("ALTER TABLE imperium_mission_scores ADD CONSTRAINT ck_imperium_mission_scores_coefficient_positive "
               "CHECK (domain_coefficient > 0)")
    op.execute(
        """
        INSERT INTO job_definitions
          (id, code, kind, schedule, event_types, handler_ref, enabled, singleton, timeout_s)
        VALUES
          (gen_random_uuid(), 'daily.scores_refresh', 'cron', '30 4,5 * * *', NULL,
           'app.services.daily.scores_refresh:scores_refresh_job', false, true, 300),
          (gen_random_uuid(), 'daily.day_start', 'event_subscription', NULL, ARRAY['planning.day.started'],
           'app.services.daily.scores_refresh:day_start_job', false, true, 300)
        ON CONFLICT ON CONSTRAINT job_definitions_code_unique DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM job_definitions WHERE code IN ('daily.scores_refresh', 'daily.day_start')")
    op.execute("ALTER TABLE imperium_mission_scores DROP CONSTRAINT ck_imperium_mission_scores_coefficient_positive")
    op.execute("ALTER TABLE imperium_user_priorities DROP CONSTRAINT ck_imperium_user_priorities_coefficient_positive")
    op.execute(
        "ALTER TABLE imperium_mission_scores ADD CONSTRAINT "
        "ck_imperium_mission_scores_fixed_coefficient CHECK (domain_coefficient IN (10, 8, 5, 4))"
    )
    op.execute(
        "ALTER TABLE imperium_user_priorities ADD CONSTRAINT "
        "ck_imperium_user_priorities_fixed_coefficient CHECK ("
        "(position = 1 AND coefficient = 10) OR (position = 2 AND coefficient = 8) OR "
        "(position = 3 AND coefficient = 5) OR (position = 4 AND coefficient = 4))"
    )
