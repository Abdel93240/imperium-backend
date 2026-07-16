"""Dotted event_type nomenclature (doc 77, applied by passe 0 — DV-11 graved).

Canonical = what the code emits. The doc 77 renames "À faire côté code" are
applied here, EXCEPT the worship.* branch: DV-11 decided the code wins, so
path.* stays canonical and worship.* is marked non-retained in doc 77.

Read compatibility (30 days, until 2026-08-14): every reader that filters by
event_type must match BOTH the old and the new name of a type — use
expand_for_read(). After the window, the old names may be dropped.
"""

from datetime import date

READ_COMPAT_UNTIL = date(2026, 8, 14)

# old (still stored in historical rows) → new (canonical, emitted from now on)
RENAMES: dict[str, str] = {
    "vault.transaction.created": "finance.transaction.created",
    "mission.backlog.created": "planning.mission.created",
    "mission.started": "planning.mission.started",
    "mission.completed": "planning.mission.completed",
    # E1: abandoned/failed are REASONS of a single aborted type, not types.
    "mission.failed": "planning.mission.aborted",
    "mission.abandoned": "planning.mission.aborted",
    "day.plan.created": "planning.daily_plan.generated",
    # Doc 77 keeps one V1 type for plan version transitions; the lifecycle verb
    # travels in the payload (trigger), see emitters.
    "day.plan.activated": "planning.daily_plan.replanned",
    "day.plan.completed": "planning.daily_plan.replanned",
    "day.plan.cancelled": "planning.daily_plan.replanned",
    "day.finished": "planning.day.finished",
    "priority.rules.updated": "decision.priorities.updated",
    # DV-11: path.* UNCHANGED (worship.* non-retained in doc 77).
}

_NEW_TO_OLD: dict[str, set[str]] = {}
for _old, _new in RENAMES.items():
    _NEW_TO_OLD.setdefault(_new, set()).add(_old)


def canonical_event_type(event_type: str) -> str:
    """Map a legacy name to its canonical form (identity for canonical names)."""
    return RENAMES.get(event_type, event_type)


def expand_for_read(event_types: list[str], *, today: date | None = None) -> list[str]:
    """Expand a type filter so old and new names both match (compat window).

    After READ_COMPAT_UNTIL the expansion collapses to canonical names only.
    """
    today = today or date.today()
    expanded: list[str] = []
    for event_type in event_types:
        canonical = canonical_event_type(event_type)
        if canonical not in expanded:
            expanded.append(canonical)
        if today <= READ_COMPAT_UNTIL:
            for old in _NEW_TO_OLD.get(canonical, ()):
                if old not in expanded:
                    expanded.append(old)
    return expanded
