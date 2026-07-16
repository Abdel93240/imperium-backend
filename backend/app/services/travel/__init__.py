"""toolbox.travel — single travel-estimation interface (DBL-1 killed).

The signature of estimate() is GRAVED: the Vector pass will strengthen the
engine (H3 matrix + live multipliers) without changing it. The ×1.3 hard floor
lives in this interface, never in consumers.
"""

from app.services.travel.estimate import LatLng, TravelEstimate, estimate

__all__ = ["LatLng", "TravelEstimate", "estimate"]
