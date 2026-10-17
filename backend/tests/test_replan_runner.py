"""Runner de replanification (doc 43 §2, §3.2) — proposition déterministe, tests unitaires."""
from datetime import UTC, datetime

from app.services.imperium.replan_runner import build_deterministic_proposal, build_revision_proposal

NOW = datetime(2026, 10, 17, 11, 0, tzinfo=UTC)


def _blocks():
    return [
        {"block_type": "mission", "title": "Routine du matin", "planned_start": "2026-10-17T03:30:00+00:00", "planned_end": "2026-10-17T04:00:00+00:00", "status": "completed"},
        {"block_type": "current_mission", "title": "Travail VTC", "planned_start": "2026-10-17T07:00:00+00:00", "planned_end": "2026-10-17T12:00:00+00:00", "status": "active"},
        {"block_type": "mission", "title": "Démarches", "planned_start": "2026-10-17T13:00:00+00:00", "planned_end": "2026-10-17T14:00:00+00:00"},
        {"block_type": "mission", "title": "Lecture", "planned_start": "2026-10-17T20:30:00+00:00", "planned_end": "2026-10-17T20:50:00+00:00"},
        {"block_type": "priority_context", "priorities": []},
    ]


def _by_title(blocks):
    return {b.get("title"): b for b in blocks if b.get("title")}


def test_new_event_shifts_upcoming_blocks_by_thirty_minutes() -> None:
    blocks, rationale = build_deterministic_proposal(_blocks(), reason_category="new_event", now=NOW)
    titles = _by_title(blocks)
    assert titles["Routine du matin"]["change"] == "unchanged"
    assert titles["Travail VTC"]["change"] == "unchanged"  # en cours : pas déplacée
    assert titles["Démarches"]["planned_start"] == "2026-10-17T13:30:00+00:00"
    assert titles["Démarches"]["change"] == "moved"
    assert titles["Lecture"]["planned_end"] == "2026-10-17T21:20:00+00:00"
    assert "30 min" in rationale


def test_fatigue_inserts_a_recovery_break_and_shifts() -> None:
    blocks, rationale = build_deterministic_proposal(_blocks(), reason_category="fatigue", now=NOW)
    new = [b for b in blocks if b["change"] == "new"]
    assert len(new) == 1 and new[0]["title"] == "Pause récupération"
    assert _by_title(blocks)["Démarches"]["planned_start"] == "2026-10-17T13:20:00+00:00"
    assert "pause" in rationale.lower()


def test_wrong_estimation_extends_the_current_mission() -> None:
    blocks, _ = build_deterministic_proposal(_blocks(), reason_category="wrong_estimation", now=NOW)
    current = _by_title(blocks)["Travail VTC"]
    assert current["planned_end"] == "2026-10-17T12:30:00+00:00" and current["change"] == "moved"
    assert _by_title(blocks)["Démarches"]["planned_start"] == "2026-10-17T13:30:00+00:00"


def test_priority_shift_moves_nothing_and_asks_the_user() -> None:
    blocks, rationale = build_deterministic_proposal(_blocks(), reason_category="priority_shift", now=NOW)
    assert all(b["change"] == "unchanged" for b in blocks)
    assert "?" in rationale


def test_context_blocks_are_kept_untouched() -> None:
    blocks, _ = build_deterministic_proposal(_blocks(), reason_category="new_event", now=NOW)
    context = [b for b in blocks if b["block_type"] == "priority_context"]
    assert context == [{"block_type": "priority_context", "priorities": [], "change": "unchanged"}]


def test_revision_uses_local_model_output_when_valid() -> None:
    current = [{"block_type": "mission", "title": "Lecture", "change": "removed"}]

    def fake_model(prompt: str) -> dict:
        assert "Garde la lecture" in prompt
        return {"blocks": [{"block_type": "mission", "title": "Lecture", "change": "moved"}], "rationale": "Je garde la lecture."}

    blocks, rationale, used_model = build_revision_proposal(current, correction="Garde la lecture ce soir.", call_model=fake_model)
    assert used_model is True and blocks[0]["change"] == "moved" and rationale == "Je garde la lecture."


def test_revision_falls_back_when_model_output_is_invalid_or_unavailable() -> None:
    current = [{"block_type": "mission", "title": "Lecture", "change": "removed"}]

    def broken(prompt: str) -> dict:
        return {"blocks": [{"title": "", "change": "teleported"}]}

    def down(prompt: str) -> dict:
        raise RuntimeError("model down")

    for model in (broken, down, None):
        blocks, rationale, used_model = build_revision_proposal(current, correction="Garde la lecture.", call_model=model)
        assert used_model is False and blocks == current
        assert "pas pu appliquer" in rationale


def test_seeded_handler_ref_resolves_to_the_job_function() -> None:
    from app.services.imperium.replan_runner import rolling_replan_job
    from app.services.runner.engine import resolve_handler

    assert resolve_handler("app.services.imperium.replan_runner:rolling_replan_job") is rolling_replan_job
