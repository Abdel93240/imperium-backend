"""Validation des contrats Opérations (doc 71) — tests unitaires."""
from datetime import time

import pytest
from pydantic import ValidationError

from app.schemas.operations import ProjectCreate, ProjectProgressUpdate, ProjectReorderRequest, RoutineCreate, RoutineUpdate


def test_project_title_is_required() -> None:
    with pytest.raises(ValidationError):
        ProjectCreate(title="  ")


@pytest.mark.parametrize("frequency", ["daily", "weekly", "biweekly", "monthly"])
def test_four_closed_frequencies(frequency) -> None:
    assert RoutineCreate(name="Lecture", frequency=frequency).frequency == frequency


@pytest.mark.parametrize("frequency", ["other", "twice_a_week", ""])
def test_no_other_frequency(frequency) -> None:
    with pytest.raises(ValidationError):
        RoutineCreate(name="Lecture", frequency=frequency)


def test_priority_defaults_to_medium_and_is_closed() -> None:
    assert RoutineCreate(name="Lecture", frequency="daily").priority == "medium"
    with pytest.raises(ValidationError):
        RoutineCreate(name="Lecture", frequency="daily", priority="urgent")


def test_routine_create_has_no_day_or_time_fields() -> None:
    # Jour/heure forcés : seulement via le chatbot (PATCH), jamais dans le formulaire.
    with pytest.raises(ValidationError):
        RoutineCreate(name="Lecture", frequency="weekly", pinned_weekday=6)


def test_pins_are_bounded() -> None:
    assert RoutineUpdate(pinned_weekday=7, pinned_month_day=31, pinned_time=time(21, 0)).pinned_weekday == 7
    for kwargs in ({"pinned_weekday": 0}, {"pinned_weekday": 8}, {"pinned_month_day": 32}):
        with pytest.raises(ValidationError):
            RoutineUpdate(**kwargs)


def test_progress_is_a_percentage_with_a_reason() -> None:
    with pytest.raises(ValidationError):
        ProjectProgressUpdate(percent=101, why="x")
    with pytest.raises(ValidationError):
        ProjectProgressUpdate(percent=50, why=" ")


def test_reorder_rejects_duplicates() -> None:
    from uuid import uuid4

    pid = uuid4()
    with pytest.raises(ValidationError):
        ProjectReorderRequest(project_ids=[pid, pid])


def test_operations_routes_are_registered_on_the_api() -> None:
    from app.api.v1.router import api_router

    paths = {(route.path, method) for route in api_router.routes for method in getattr(route, "methods", set())}
    for expected in [
        ("/imperium/projects", "GET"), ("/imperium/projects", "POST"), ("/imperium/projects/reorder", "POST"),
        ("/imperium/projects/{project_id}", "PATCH"), ("/imperium/projects/{project_id}", "DELETE"),
        ("/imperium/projects/{project_id}/complete", "POST"), ("/imperium/projects/{project_id}/missions", "POST"),
        ("/imperium/missions/{mission_id}", "PATCH"), ("/imperium/missions/{mission_id}", "DELETE"),
        ("/imperium/routines", "GET"), ("/imperium/routines/today", "GET"), ("/imperium/routines/{routine_id}/check", "POST"),
        ("/internal/projects/{project_id}/progress", "POST"),
    ]:
        assert expected in paths, expected
