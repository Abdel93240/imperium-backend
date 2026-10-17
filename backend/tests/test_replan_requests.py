"""Validation des demandes de replanification (doc 43 §3.4) — tests unitaires."""
import pytest
from pydantic import ValidationError

from app.schemas.imperium import ReplanProposalAttachRequest, ReplanRequestCreate, ReplanReviseRequest


@pytest.mark.parametrize("category", ["new_event", "wrong_estimation", "fatigue", "priority_shift", "other"])
def test_five_reason_categories_are_accepted(category) -> None:
    other = "Panne de voiture" if category == "other" else None
    assert ReplanRequestCreate(reason_category=category, reason_detail="Une phrase claire.", other_reason=other).reason_category == category


def test_unknown_category_rejected() -> None:
    with pytest.raises(ValidationError):
        ReplanRequestCreate(reason_category="mood", reason_detail="Une phrase claire.")


@pytest.mark.parametrize("detail", ["", "  ", "ok"])
def test_details_are_mandatory(detail) -> None:
    with pytest.raises(ValidationError):
        ReplanRequestCreate(reason_category="fatigue", reason_detail=detail)


def test_other_requires_other_reason() -> None:
    with pytest.raises(ValidationError):
        ReplanRequestCreate(reason_category="other", reason_detail="Une phrase claire.")


def test_proposal_block_changes_are_constrained() -> None:
    with pytest.raises(ValidationError):
        ReplanProposalAttachRequest(blocks=[{"block_type": "mission", "title": "x", "change": "teleported"}], rationale="x")
    ok = ReplanProposalAttachRequest(blocks=[{"block_type": "mission", "title": "x", "change": "moved"}], rationale="x")
    assert ok.blocks[0]["change"] == "moved"


def test_revise_needs_a_message() -> None:
    with pytest.raises(ValidationError):
        ReplanReviseRequest(message=" ")


def test_cooldown_returns_409_with_server_eligible_at(monkeypatch) -> None:
    from datetime import UTC, datetime
    from types import SimpleNamespace
    from uuid import uuid4

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.api.deps import get_current_user, get_db
    from app.api.v1.routes import imperium
    from app.services.imperium.replan import ReplanCooldownError

    eligible = datetime(2026, 10, 17, 7, 29, tzinfo=UTC)

    def _raise(*_args, **_kwargs):
        raise ReplanCooldownError(eligible)

    monkeypatch.setattr(imperium, "request_replan", _raise)
    app = FastAPI()
    app.include_router(imperium.router, prefix="/api/imperium")
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=uuid4())
    app.dependency_overrides[get_db] = lambda: SimpleNamespace(rollback=lambda: None)

    response = TestClient(app).post(
        "/api/imperium/day/replan",
        headers={"Idempotency-Key": "k"},
        json={"reason_category": "fatigue", "reason_detail": "Longue nuit."},
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "REPLAN_COOLDOWN"
    assert response.json()["detail"]["eligible_at"] == eligible.isoformat()
