"""Agendas structurés pour le scan des événements de Vector (accord utilisateur 2026-10-24).

- Open data de la Ville de Paris, « Que faire à Paris » (Opendatasoft, sans clé) : chaque séance d'un concert, d'une
  soirée, d'un spectacle ou d'un festival devient un élément. Ateliers, expositions, balades et activités pour enfants
  sont écartés : ils ne créent pas de sortie groupée.
- OpenAgenda (mairies, associations, salles de banlieue) : à brancher quand la clé est déposée.

Les éléments ont la forme de ceux du spécialiste web (heures locales de Paris sans décalage) : mêmes filtres, même
dédoublonnage. Les horaires de l'open data portent souvent un décalage faux : seule l'heure locale compte.
"""

import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

PARIS = ZoneInfo("Europe/Paris")
PARIS_DATASET = "https://opendata.paris.fr/api/explore/v2.1/catalog/datasets/que-faire-a-paris-/records"
PAGE = 100
MAX_PAGES = 30
TIMEOUT_S = 30
# Étiquette « Que faire à Paris » → catégorie Vector, dans cet ordre de priorité.
TAGS = (("Nuit", "club"), ("Concert", "concert"), ("Festival", "festival"), ("Humour", "spectacle"),
        ("Théâtre", "spectacle"), ("Danse", "spectacle"), ("Opéra", "spectacle"), ("Cirque", "spectacle"),
        ("Spectacle musical", "spectacle"))
EXCLUDED = {"Enfants", "Atelier"}


class AgendaUnavailableError(RuntimeError):
    pass


def _get(url: str) -> dict:
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"Accept": "application/json"}),  # nosec B310
                                    timeout=TIMEOUT_S) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise AgendaUnavailableError(f"{type(exc).__name__}") from exc


def _local(value: str | None) -> str | None:
    """« 2026-10-26T21:00:00+02:00 » → « 2026-10-26T21:00 » (heure locale, décalage ignoré)."""
    return value[:16] if value and len(value) >= 16 else None


def _after(start: str, end: str | None) -> str | None:
    """Fin avant le début (« 23:00 → 02:00 » le même jour) : la séance finit le lendemain."""
    if end is None or end > start:
        return end
    return (datetime.fromisoformat(end) + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M")


def _sessions(record: dict) -> list[tuple[str, str | None]]:
    """Séances datées ; sans séances, la plage seulement si elle tient dans une journée (une expo de 3 mois, non)."""
    out = []
    for part in (record.get("occurrences") or "").split(";"):
        start, _, end = part.partition("_")
        if _local(start):
            out.append((_local(start), _after(_local(start), _local(end))))
    if out:
        return out
    start, end = _local(record.get("date_start")), _local(record.get("date_end"))
    if start and end and start[:10] == end[:10]:
        return [(start, end)]
    return []


def paris_events(start: datetime, end: datetime, *, fetch=None) -> list[dict]:
    """Séances entre `start` et `end` (heures de Paris), au format des éléments du scan."""
    fetch = fetch or _get
    tags = " or ".join(f'search(qfap_tags, "{tag}")' for tag, _ in TAGS)
    where = f'date_end >= "{start.date().isoformat()}" and date_start <= "{end.date().isoformat()}" and ({tags})'
    lo, hi = start.strftime("%Y-%m-%dT%H:%M"), end.strftime("%Y-%m-%dT%H:%M")
    items = []
    for page in range(MAX_PAGES):
        body = fetch(PARIS_DATASET + "?" + urllib.parse.urlencode(
            {"where": where, "limit": PAGE, "offset": page * PAGE, "order_by": "date_start"}))
        records = body.get("results") or []
        for record in records:
            tags_of = set((record.get("qfap_tags") or "").split(";"))
            category = next((cat for tag, cat in TAGS if tag in tags_of), None)
            if category is None or tags_of & EXCLUDED:
                continue
            code = str(record.get("address_zipcode") or "")
            for begin, finish in _sessions(record):
                if not lo <= begin < hi:
                    continue
                items.append({
                    "kind": "event", "category": category, "title": str(record.get("title") or "").strip(),
                    "venue": record.get("address_name"), "commune": record.get("address_city") or "Paris",
                    "postal_code": code if len(code) == 5 and code.isdigit() else None, "road": None,
                    "starts_at": begin, "ends_at": finish, "expected_attendance": None,
                    "source_url": record.get("url"), "confidence": 0.95,
                })
        if len(records) < PAGE:
            break
    return items
