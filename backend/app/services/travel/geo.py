"""toolbox.geo — H3 indexing, cache rounding, haversine, A→B cell corridor.

Owner: the travel package (audit T6). Vector §3.5 consumes the corridor; Path
will consume the scan primitives (Q2) — always through this module, never a
private copy.
"""

import math
from dataclasses import dataclass

import h3

DEFAULT_H3_RES = 8  # parameter toolbox.h3_res (seed); callers may override
EARTH_RADIUS_M = 6_371_000.0


@dataclass(frozen=True)
class LatLng:
    lat: float
    lng: float


def h3_cell(point: LatLng, res: int = DEFAULT_H3_RES) -> str:
    return h3.latlng_to_cell(point.lat, point.lng, res)


def haversine_m(a: LatLng, b: LatLng) -> float:
    lat1, lng1, lat2, lng2 = map(math.radians, (a.lat, a.lng, b.lat, b.lng))
    dlat, dlng = lat2 - lat1, lng2 - lng1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(h))


def cell_corridor(a: LatLng, b: LatLng, res: int = DEFAULT_H3_RES, width: int = 1) -> list[str]:
    """Cells along the A→B broken line, widened by `width` rings (Vector §3.5).

    Deterministic and ordered from A to B (widening cells appended after their
    axis cell, deduplicated).
    """
    start, end = h3_cell(a, res), h3_cell(b, res)
    axis = h3.grid_path_cells(start, end)
    corridor: list[str] = []
    seen: set[str] = set()
    for cell in axis:
        for candidate in [cell, *sorted(h3.grid_disk(cell, width))]:
            if candidate not in seen:
                seen.add(candidate)
                corridor.append(candidate)
    return corridor


def time_slot(hour: int, minutes_per_slot: int = 60) -> str:
    """Cache time bucket. 60-minute slots by default: '13' for 13:00-13:59."""
    if minutes_per_slot == 60:
        return f"{hour:02d}"
    return f"{hour:02d}:{(0):02d}"
