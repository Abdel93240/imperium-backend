"""Portes de faisabilité et détection de cycles : code pur (spec Daily §5, §14.2 ; carte ACT-DLY-04)."""

from datetime import datetime, time
from types import SimpleNamespace
from uuid import uuid4

from app.services.daily.constraints import find_path
from app.services.daily.selection import PARIS, gate_dependencies, gate_pulse, gate_status, gate_time, gate_window

WEDNESDAY_10H = datetime(2026, 10, 21, 10, 0, tzinfo=PARIS)


def _mission(**fields):
    base = {"status": "backlog", "annex_of_mission_id": None, "is_fixed_commitment": False, "window_days": None,
            "window_start": None, "window_end": None}
    return SimpleNamespace(**{**base, **fields})


def test_g1_status_and_perimeter() -> None:
    assert gate_status(_mission())
    assert not gate_status(_mission(status="standby"))  # en attente d'arbitrage
    assert not gate_status(_mission(annex_of_mission_id=uuid4()))
    assert not gate_status(_mission(is_fixed_commitment=True))


def test_g2_open_hard_parents_block() -> None:
    child = uuid4()
    assert gate_dependencies(child, {})
    assert not gate_dependencies(child, {child: 1})


def test_g3_window_counts_travel_and_duration() -> None:
    window = _mission(window_start=time(9, 0), window_end=time(11, 0))
    assert gate_window(window, now_local=WEDNESDAY_10H, travel_min=10, duration_min=30)
    assert not gate_window(window, now_local=WEDNESDAY_10H, travel_min=40, duration_min=30)  # finirait après 11 h
    assert not gate_window(_mission(window_start=time(10, 30)), now_local=WEDNESDAY_10H, travel_min=10,
                           duration_min=5)  # arrivée avant l'ouverture
    assert gate_window(_mission(), now_local=WEDNESDAY_10H, travel_min=600, duration_min=600)  # null = libre
    assert gate_window(_mission(window_days=["wed"]), now_local=WEDNESDAY_10H, travel_min=0, duration_min=5)
    assert not gate_window(_mission(window_days=["sat", "sun"]), now_local=WEDNESDAY_10H, travel_min=0,
                           duration_min=5)


def test_g4_time_before_next_fixed_commitment() -> None:
    assert gate_time(travel_min=10, duration_min=20, remaining_min=30)
    assert not gate_time(travel_min=11, duration_min=20, remaining_min=30)


def test_g5_is_a_passing_stub_until_wave_29() -> None:
    assert gate_pulse(_mission(physical_load=5))


def test_cycle_detection_follows_parent_to_child() -> None:
    a, b, c = uuid4(), uuid4(), uuid4()
    edges = [(a, b), (b, c)]
    assert find_path(edges, start=c, goal=a) is None  # c → a n'existe pas : l'arête a → c reste légale
    assert find_path(edges, start=a, goal=c) == [a, b, c]  # c → a fermerait le cycle a → b → c → a
