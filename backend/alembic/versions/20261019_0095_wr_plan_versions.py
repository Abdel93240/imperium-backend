"""wr plan versions: the strategic plan object, its deltas and v_plan_current (spec WR §3.5, §8, Q8)

`plan_versions` : versions complètes du plan glissant (~4 semaines). origin initial|monthly_regen|
shock_regen ; status proposed|active|superseded, une seule version active par utilisateur ; jamais
de DELETE (trigger) : un retour arrière passe la version en superseded. `plan_deltas` : opérations
move|add|remove|modify sur une version (origin wr_weekly|user_request|shock_minor), appliquées en P5
à partir de V23. Vue `v_plan_current` : la version active + ses deltas appliqués, dans l'ordre.
Interrupteur `wr.plan_enabled` (semé false) : sert GET /api/wr/plan/current et la section plan du digest.

Revision ID: 20261019_0095
Revises: 20261019_0094
Create Date: 2026-10-19
"""

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261019_0095"
down_revision: str | None = "20261019_0094"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)

PARAMETERS = [
    ("wr.plan_enabled", "wr", False, "bool",
     "Sert le plan courant (GET plan/current, section plan du digest) ; bascule ACT-WR-18 (À VALIDER)."),
]


def upgrade() -> None:
    op.create_table(
        "plan_versions",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("horizon_start", sa.Date(), nullable=False),
        sa.Column("horizon_end", sa.Date(), nullable=False),
        sa.Column("plan", postgresql.JSONB(), nullable=False),
        sa.Column("origin", sa.Text(), nullable=False),
        sa.Column("origin_ref", UUID, nullable=True),
        sa.Column("model_used", sa.Text(), nullable=True),
        sa.Column("rationale_fr", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="proposed"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("superseded_reason_fr", sa.Text(), nullable=True),
        sa.CheckConstraint("origin IN ('initial', 'monthly_regen', 'shock_regen')", name="plan_versions_origin_check"),
        sa.CheckConstraint("status IN ('proposed', 'active', 'superseded')", name="plan_versions_status_check"),
        sa.CheckConstraint("horizon_end >= horizon_start", name="plan_versions_horizon_check"),
        sa.CheckConstraint("jsonb_typeof(plan) = 'object'", name="plan_versions_plan_object"),
        sa.CheckConstraint("status <> 'active' OR activated_at IS NOT NULL", name="plan_versions_active_check"),
    )
    op.create_index("plan_versions_one_active", "plan_versions", ["user_id"], unique=True,
                    postgresql_where=sa.text("status = 'active'"))
    op.execute(
        """
        CREATE FUNCTION plan_versions_no_delete() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          RAISE EXCEPTION 'plan_versions rows are never deleted: set status = superseded';
        END $$;
        CREATE TRIGGER plan_versions_no_delete BEFORE DELETE ON plan_versions
          FOR EACH ROW EXECUTE FUNCTION plan_versions_no_delete();
        """
    )
    op.create_table(
        "plan_deltas",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("plan_version_id", UUID, sa.ForeignKey("plan_versions.id"), nullable=False),
        sa.Column("operations", postgresql.JSONB(), nullable=False),
        sa.Column("origin", sa.Text(), nullable=False),
        sa.Column("proposal_id", UUID, sa.ForeignKey("wr_docket_items.id"), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="proposed"),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_fr", sa.Text(), nullable=True),
        sa.Column("model_used", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("origin IN ('wr_weekly', 'user_request', 'shock_minor')", name="plan_deltas_origin_check"),
        sa.CheckConstraint("status IN ('proposed', 'accepted', 'refused', 'applied')", name="plan_deltas_status_check"),
        sa.CheckConstraint("jsonb_typeof(operations) = 'array'", name="plan_deltas_operations_array"),
        sa.CheckConstraint("(status = 'applied') = (applied_at IS NOT NULL)", name="plan_deltas_applied_check"),
        sa.CheckConstraint("confidence IS NULL OR confidence BETWEEN 0 AND 100", name="plan_deltas_confidence_check"),
    )
    op.create_index("plan_deltas_version_idx", "plan_deltas", ["plan_version_id", "applied_at"])
    op.execute(
        """
        CREATE VIEW v_plan_current AS
        SELECT pv.id AS plan_version_id, pv.user_id, pv.horizon_start, pv.horizon_end, pv.plan, pv.origin,
               pv.activated_at,
               COALESCE(jsonb_agg(jsonb_build_object('delta_id', d.id, 'operations', d.operations,
                                                     'applied_at', d.applied_at)
                                  ORDER BY d.applied_at, d.id) FILTER (WHERE d.id IS NOT NULL),
                        '[]'::jsonb) AS applied_deltas
        FROM plan_versions pv
        LEFT JOIN plan_deltas d ON d.plan_version_id = pv.id AND d.status = 'applied'
        WHERE pv.status = 'active'
        GROUP BY pv.id
        """
    )
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


def downgrade() -> None:
    conn = op.get_bind()
    conn.exec_driver_sql("ALTER TABLE parameters DISABLE TRIGGER parameters_append_only")
    try:
        conn.exec_driver_sql("DELETE FROM parameters WHERE code = ANY(%s)", ([p[0] for p in PARAMETERS],))
    finally:
        conn.exec_driver_sql("ALTER TABLE parameters ENABLE TRIGGER parameters_append_only")
    op.execute("DROP VIEW v_plan_current")
    op.drop_table("plan_deltas")
    op.execute("DROP TRIGGER plan_versions_no_delete ON plan_versions")
    op.execute("DROP FUNCTION plan_versions_no_delete()")
    op.drop_table("plan_versions")
