"""Agendas structurés pour le scan des événements de Vector (accord utilisateur 2026-10-24).

- Open data de la Ville de Paris, « Que faire à Paris » (Opendatasoft, sans clé) : chaque séance d'un concert, d'une
  soirée, d'un spectacle ou d'un festival devient un élément. Ateliers, expositions, balades et activités pour enfants
  sont écartés : ils ne créent pas de sortie groupée.
- OpenAgenda (mairies, associations, salles, surtout en banlieue ; clé dans `.env`) : la recherche d'événements dans
  tous les agendas demande un droit « transverse » que la clé gratuite n'a pas. Le lundi, les agendas utiles sont
  cherchés commune par commune (communes urbaines denses et grandes villes) et gardés dans le paramètre
  `vector.openagenda_agendas` ; chaque scan lit ensuite leurs événements de la période. Stages, ateliers, activités
  pour enfants, visites, conférences et événements en ligne ou annulés sont écartés.

Les éléments ont la forme de ceux du spécialiste web (heures locales de Paris sans décalage) : mêmes filtres, même
dédoublonnage. Les horaires de l'open data portent souvent un décalage faux : seule l'heure locale compte.
"""

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from importlib import resources
from zoneinfo import ZoneInfo

from app.core.config import get_settings

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


# --- OpenAgenda ----------------------------------------------------------------------------------------------------

OPENAGENDA = "https://api.openagenda.com/v2"
DENSE_COMMUNES = 140  # les communes les plus denses d'Île-de-France (hors Paris)
# Grandes villes étendues, peu denses mais avec des salles et des sorties.
BIG_TOWNS = ("Versailles", "Saint-Germain-en-Laye", "Cergy", "Pontoise", "Argenteuil", "Évry-Courcouronnes", "Corbeil-Essonnes",
             "Massy", "Palaiseau", "Meaux", "Melun", "Chelles", "Torcy", "Noisiel", "Marne-la-Vallée", "Mantes-la-Jolie",
             "Poissy", "Les Mureaux", "Sartrouville", "Rambouillet", "Fontainebleau", "Créteil", "Nanterre", "Saint-Denis",
             "Bobigny", "Montreuil", "Aulnay-sous-Bois", "Sarcelles", "Roissy", "Brétigny-sur-Orge", "Savigny-sur-Orge")
GENERIC = ("Paris", "Île-de-France", "Hauts-de-Seine", "Seine-Saint-Denis", "Val-de-Marne", "Seine-et-Marne", "Yvelines",
           "Essonne", "Val-d'Oise")
AGENDA_KEEP = re.compile(r"sortir|agenda|culture|cultur|saison|programm|th[ée][âa]tre|concert|salle|festival|spectacle|"
                         r"[ée]v[ée]nement|musique|jazz|club|f[êe]te|sc[eè]ne|cabaret|cin[ée]ma|ville|mairie|espace|"
                         r"centre culturel|maison|caf[ée]|bar|live", re.I)
AGENDA_SKIP = re.compile(r"emploi|formation|biblioth|m[ée]diath|conservatoire|enfan|jeune|colo|vacances|h[ée]bergement|"
                         r"catalogue|atelier|portes ouvertes|sant[ée]|seniors?|retrait|[ée]cole|coll[èe]ge|lyc[ée]e|"
                         r"universit|entreprise|patrimoine|nature|rando|archive", re.I)
EVENT_KEEP = re.compile(r"concert|soir[ée]e|f[êe]te|festival|spectacle|th[ée][âa]tre|humour|bal\b|dj|gala|live|jazz|"
                        r"rap|cabaret|danse|cirque|match|d[îi]ner|op[ée]ra|show|stand-?up|musique|chorale|gospel|"
                        r"orchestre|nuit", re.I)
EVENT_SKIP = re.compile(r"stage|atelier|enfant|\bado|jeune public|b[ée]b[ée]|conf[ée]rence|visite|exposition|\bexpo\b|"
                        r"permanence|r[ée]union|cours\b|initiation|lecture|formation|webinaire|balade|rando", re.I)
CANCELLED, ONLINE = 6, 2  # statut OpenAgenda « annulé », mode de participation « en ligne »


def _openagenda(path: str, params: dict, fetch=None) -> dict:
    key = get_settings().openagenda_api_key
    if fetch is None and not key:
        raise AgendaUnavailableError("Clé OpenAgenda absente.")
    return (fetch or _get)(OPENAGENDA + path + "?" + urllib.parse.urlencode({"key": key or "", **params}, doseq=True))


def search_terms() -> list[str]:
    data = json.loads(resources.files("app.services.vector").joinpath("data/communes_idf.json").read_text("utf-8"))
    dense = [name for name, *_rest, density in sorted(data["communes"], key=lambda c: -(c[4] or 0))][:DENSE_COMMUNES]
    return list(dict.fromkeys([*GENERIC, *BIG_TOWNS, *dense]))


def discover_openagenda(*, fetch=None, terms: list[str] | None = None, per_term: int = 20) -> list[int]:
    """Agendas utiles (villes, salles, festivals, sorties), cherchés commune par commune ; sans les agendas d'emploi,
    de bibliothèques, d'enfance…"""
    found: dict[int, None] = {}
    for term in terms or search_terms():
        body = _openagenda("/agendas", {"search": term, "size": per_term}, fetch)
        for agenda in body.get("agendas") or []:
            title = str(agenda.get("title") or "")
            if AGENDA_KEEP.search(title) and not AGENDA_SKIP.search(title):
                found[int(agenda["uid"])] = None
    return list(found)


def openagenda_events(uids: list[int], start: datetime, end: datetime, *, fetch=None) -> list[dict]:
    """Séances des agendas entre `start` et `end` (Île-de-France seulement), au format des éléments du scan."""
    lo, hi = start.strftime("%Y-%m-%dT%H:%M"), end.strftime("%Y-%m-%dT%H:%M")
    items, seen = [], set()
    for uid in uids:
        after: list = []
        for _ in range(5):  # 500 événements au plus par agenda et par période
            params = {"size": 100, "detailed": 1, "monolingual": "fr", "timings[gte]": start.isoformat(),
                      "timings[lte]": end.isoformat()}
            if after:
                params["after[]"] = after
            body = _openagenda(f"/agendas/{uid}/events", params, fetch)
            for event in body.get("events") or []:
                if event.get("uid") in seen:  # un événement partagé entre plusieurs agendas
                    continue
                seen.add(event.get("uid"))
                title = str(event.get("title") or "").strip()
                words = " ".join([title, *(event.get("keywords") or [])])
                location = event.get("location") or {}
                code = str(location.get("postalCode") or "")
                if (not EVENT_KEEP.search(words) or EVENT_SKIP.search(words) or event.get("status") == CANCELLED
                        or event.get("attendanceMode") == ONLINE or code[:2] not in IDF):
                    continue
                for timing in event.get("timings") or []:
                    begin, finish = _local(timing.get("begin")), _local(timing.get("end"))
                    if begin and lo <= begin < hi:
                        items.append({
                            "kind": "event", "category": _category(words), "title": title,
                            "venue": location.get("name"), "commune": location.get("city"),
                            "postal_code": code if len(code) == 5 and code.isdigit() else None, "road": None,
                            "starts_at": begin, "ends_at": _after(begin, finish), "expected_attendance": None,
                            "source_url": event.get("canonicalUrl") or f"https://openagenda.com/e/{event.get('uid')}",
                            "confidence": 0.9,
                        })
            after = body.get("after") or []
            if not after or len(body.get("events") or []) < 100:
                break
    return items


IDF = {"75", "77", "78", "91", "92", "93", "94", "95"}


def _category(words: str) -> str:
    lower = words.lower()
    if re.search(r"cabaret|th[ée][âa]tre|spectacle", lower):
        return "spectacle"
    if re.search(r"soir[ée]e|\bdj\b|club|\bbal\b", lower):  # vraies soirées dansantes : sorties de boîte
        return "club"
    if re.search(r"concert|jazz|rap|live|musique|chorale|gospel|orchestre", lower):
        return "concert"
    if re.search(r"festival|f[êe]te", lower):
        return "festival"
    if "match" in lower:
        return "sport"
    return "spectacle"
