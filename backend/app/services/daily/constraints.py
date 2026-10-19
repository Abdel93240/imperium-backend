"""Attributs de faisabilité d'une mission et dépendances explicites (spec Daily §3.1-3.2, carte ACT-DLY-04).

Les contraintes (lieu, fenêtre, engagement fixe, charges) sont remplacées en entier par
`PUT missions/{id}/constraints`. Une arête parent → enfant est refusée si elle ferme un cycle
(toutes arêtes confondues, `hard` ou non) : rejet motivé, jamais d'écriture partielle.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.daily import MissionDependency
from app.models.imperium import ImperiumMission
from app.schemas.daily import MissionConstraints, MissionDependencyCreate

CLOSED_STATUSES = frozenset({"completed", "failed", "abandoned", "cancelled"})


class ConstraintsError(RuntimeError):
    def __init__(self, message: str, code: str) -> None:
        super().__init__(message)
        self.code = code


def update_constraints(db: Session, *, current_user: User, mission_id: UUID, payload: MissionConstraints) -> MissionConstraints:
    mission = _owned(db, current_user, mission_id)
    if mission.status in CLOSED_STATUSES:
        raise ConstraintsError("Mission is closed.", "MISSION_CLOSED")
    location = payload.location
    mission.location_lat = location.lat if location else None
    mission.location_lng = location.lng if location else None
    mission.location_label = location.label if location else None
    mission.window_start, mission.window_end = payload.window_start, payload.window_end
    mission.window_days = list(payload.window_days) if payload.window_days else None
    mission.is_fixed_commitment, mission.fixed_at = payload.is_fixed_commitment, payload.fixed_at
    mission.physical_load, mission.cognitive_load = payload.physical_load, payload.cognitive_load
    db.commit()
    return read_constraints(mission)


def read_constraints(mission: ImperiumMission) -> MissionConstraints:
    location = None
    if mission.location_lat is not None:
        location = {"lat": float(mission.location_lat), "lng": float(mission.location_lng),
                    "label": mission.location_label}
    return MissionConstraints(
        location=location, window_start=mission.window_start, window_end=mission.window_end,
        window_days=mission.window_days, is_fixed_commitment=mission.is_fixed_commitment, fixed_at=mission.fixed_at,
        physical_load=mission.physical_load, cognitive_load=mission.cognitive_load,
    )


def add_dependency(db: Session, *, current_user: User, payload: MissionDependencyCreate) -> MissionDependency:
    parent_id, child_id = payload.parent_mission_id, payload.child_mission_id
    if parent_id == child_id:
        raise ConstraintsError("A mission cannot depend on itself.", "DEPENDENCY_SELF")
    _owned(db, current_user, parent_id)
    _owned(db, current_user, child_id)
    edges = db.execute(
        select(MissionDependency.parent_mission_id, MissionDependency.child_mission_id)
        .where(MissionDependency.user_id == current_user.id)
    ).all()
    if (parent_id, child_id) in {(p, c) for p, c in edges}:
        raise ConstraintsError("This dependency already exists.", "DEPENDENCY_EXISTS")
    cycle = find_path(edges, start=child_id, goal=parent_id)
    if cycle is not None:
        raise ConstraintsError(
            "This dependency would close a cycle: " + " → ".join(str(node) for node in [parent_id, *cycle]),
            "DEPENDENCY_CYCLE",
        )
    row = MissionDependency(user_id=current_user.id, parent_mission_id=parent_id, child_mission_id=child_id,
                            hard=payload.hard)
    db.add(row)
    db.commit()
    return row


def list_dependencies(db: Session, *, current_user: User, mission_id: UUID) -> list[MissionDependency]:
    _owned(db, current_user, mission_id)
    return list(db.scalars(
        select(MissionDependency).where(
            MissionDependency.user_id == current_user.id,
            (MissionDependency.parent_mission_id == mission_id) | (MissionDependency.child_mission_id == mission_id),
        ).order_by(MissionDependency.created_at)
    ))


def find_path(edges, *, start: UUID, goal: UUID) -> list[UUID] | None:
    """Chemin start → goal en suivant parent → enfant (code pur) ; None si goal est injoignable."""
    children: dict[UUID, list[UUID]] = {}
    for parent, child in edges:
        children.setdefault(parent, []).append(child)
    previous: dict[UUID, UUID | None] = {start: None}
    queue = [start]
    while queue:
        node = queue.pop(0)
        if node == goal:
            path = []
            while node is not None:
                path.append(node)
                node = previous[node]
            return path[::-1]
        for child in children.get(node, ()):
            if child not in previous:
                previous[child] = node
                queue.append(child)
    return None


def _owned(db: Session, current_user: User, mission_id: UUID) -> ImperiumMission:
    mission = db.get(ImperiumMission, mission_id)
    if mission is None or mission.user_id != current_user.id:
        raise ConstraintsError("Mission not found.", "MISSION_NOT_FOUND")
    return mission
