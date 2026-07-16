"""§13.4 shared tables: parameters append-only, current views, training pairs."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError

from _postgres import require_test_database_url

pytest.importorskip("psycopg")

from sqlalchemy.orm import Session  # noqa: E402

from app.models.toolbox import AIAuditSample, AISlotTransition  # noqa: E402
from app.services.params import get_parameter, set_parameter  # noqa: E402


@pytest.fixture(scope="module")
def engine():
    engine = create_engine(require_test_database_url("toolbox shared tables tests"), future=True)
    yield engine
    engine.dispose()


def test_parameters_update_of_value_is_rejected_by_trigger(engine) -> None:
    with pytest.raises(DBAPIError, match="append-only"):
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE parameters SET value = '99'::jsonb WHERE code = 'toolbox.h3_res'")
            )
    with pytest.raises(DBAPIError, match="append-only"):
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM parameters WHERE code = 'toolbox.h3_res'"))


def test_set_parameter_versions_and_current_view_follows(engine) -> None:
    code = f"toolbox.test_param_{uuid4().hex[:8]}"
    with Session(engine) as db:
        first = set_parameter(
            db, code=code, value=1, origin="test", rationale_fr="Version initiale."
        )
        db.commit()
        assert first.version == 1
        assert get_parameter(db, code) == 1

        second = set_parameter(
            db, code=code, value=2, origin="test", rationale_fr="Deuxième version."
        )
        db.commit()
        assert second.version == 2
        assert get_parameter(db, code) == 2  # v_parameters_current follows

        rows = db.execute(
            text("SELECT version, superseded_by FROM parameters WHERE code = :c ORDER BY version"),
            {"c": code},
        ).all()
        assert len(rows) == 2
        assert rows[0].superseded_by is not None  # v1 points to v2
        assert rows[1].superseded_by is None


def test_seeded_parameters_are_present_and_namespaced(engine) -> None:
    with Session(engine) as db:
        assert get_parameter(db, "toolbox.h3_res") == 8
        assert float(get_parameter(db, "toolbox.travel_floor")) == 1.3
        assert get_parameter(db, "toolbox.travel_cache_ttl_min") == 120
        assert get_parameter(db, "toolbox.fallback_speed_kmh") == 25
        assert float(get_parameter(db, "toolbox.topk_threshold")) == 0.35
        assert get_parameter(db, "path.calc_method") == "MuslimWorldLeague"
        assert get_parameter(db, "path.madhhab") == "Maliki"
        assert get_parameter(db, "path.window_before_min") == 0
        assert get_parameter(db, "notify.dedup_hours") == 24


def test_v_ai_training_pairs_exposes_disagreements_only(engine) -> None:
    slot_code = f"test.slot_{uuid4().hex[:8]}"
    with Session(engine) as db:
        db.add(AISlotTransition(id=uuid4(), slot_code=slot_code, domain="test"))
        db.flush()
        db.add(
            AIAuditSample(
                id=uuid4(),
                slot_code=slot_code,
                local_output={"answer": "a"},
                cloud_output={"answer": "b"},
                agreement=False,
                disagreement_reason="divergent answers",
            )
        )
        db.add(
            AIAuditSample(
                id=uuid4(),
                slot_code=slot_code,
                local_output={"answer": "a"},
                cloud_output={"answer": "a"},
                agreement=True,
            )
        )
        db.commit()
        pairs = db.execute(
            text("SELECT slot_code, domain FROM v_ai_training_pairs WHERE slot_code = :s"),
            {"s": slot_code},
        ).all()
        assert len(pairs) == 1
        assert pairs[0].domain == "test"


def test_signal_tables_exist_shared_with_domain_column(engine) -> None:
    # DBL-2 killed: ONE shared table with a domain column; the 32 Pulse signals
    # will be seeded BY the Pulse pass, so the socle table is empty.
    with engine.connect() as conn:
        columns = {
            row.column_name
            for row in conn.execute(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = 'signal_definitions'"
                )
            )
        }
        assert {"domain", "code", "active", "bands", "baseline_window_days"} <= columns
        count = conn.execute(text("SELECT count(*) FROM signal_definitions")).scalar()
        assert count == 0
        forbidden = conn.execute(
            text(
                "SELECT count(*) FROM information_schema.tables WHERE table_name IN "
                "('pulse_parameters', 'wr_signal_definitions', 'pulse_ai_transition', "
                "'pulse_signal_definitions')"
            )
        ).scalar()
        assert forbidden == 0
