"""Clé de zone : même zone malgré la casse, les accents et les espaces (« Gare de Lyon » = « gare de lyon »)."""

import re
import unicodedata


def zone_key(zone: str | None) -> str | None:
    if not zone or not zone.strip():
        return None
    folded = unicodedata.normalize("NFKD", zone).encode("ascii", "ignore").decode().casefold()
    return re.sub(r"[^a-z0-9]+", " ", folded).strip() or None
