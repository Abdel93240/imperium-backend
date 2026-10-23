"""Flux en temps réel de Vector : perturbations IDFM, trafic TomTom, avions OpenSky (doc 57 §5.6).

Relevés seulement pendant une session VTC ouverte (comme la météo), gardés comme données d'apprentissage. Clés dans
la configuration privée du serveur (`.env`), jamais dans le code ni la base ; appels sortants autorisés par
l'utilisateur. Les données servent deux fois :
- variables de chaque offre (situation au départ, à l'arrivée et en Île-de-France au moment de l'offre) ;
- contexte de chaque mesure après dépose (situation au lieu et à l'heure de la dépose), pour que le modèle apprenne
  par exemple qu'une zone devant une gare vaut 22 €/h d'habitude mais bien plus quand la ligne est en panne.

- IDFM PRIM `disruptions_bulk` : perturbations en cours des modes lourds (métro, RER, Transilien, tram), gravité,
  cause, arrêts touchés ; position des arrêts demandée une fois (`navitia/stop_points`) et gardée.
- TomTom `incidentDetails` (4 rectangles couvrant l'Île-de-France) : bouchons, fermetures, travaux, retard en secondes.
- OpenSky `states/all` autour de Roissy-CDG, Orly, Beauvais : avions en approche finale (moins de 900 m, en descente,
  à moins de 15 km) et au sol ; les atterrissages se comptent par avions distincts vus en approche finale.
"""

import json
import logging
import math
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.rides import (
    RidesAirportSnapshot,
    RidesTrafficIncident,
    RidesTransitDisruption,
    RidesTransitStop,
)
from app.services.vector import grid, weather

logger = logging.getLogger(__name__)

TIMEOUT_S = 25
FRESH = timedelta(minutes=20)
NEAR_KM = 1.5  # perturbation « près » d'un lieu : arrêt touché à moins de 1,5 km
TRAFFIC_NEAR_KM = 3.0
HEAVY_MODES = {"Metro": "metro", "RapidTransit": "rer", "LocalTrain": "transilien", "Tramway": "tram", "RailShuttle": "rer"}
SEVERITIES = ("BLOQUANTE", "PERTURBEE")
IDFM_BULK = "https://prim.iledefrance-mobilites.fr/marketplace/disruptions_bulk/disruptions/v2"
IDFM_STOP = "https://prim.iledefrance-mobilites.fr/marketplace/v2/navitia/stop_points/{}"
TOMTOM = "https://api.tomtom.com/traffic/services/5/incidentDetails"
TOMTOM_FIELDS = ("{incidents{type,geometry{type,coordinates},properties{iconCategory,magnitudeOfDelay,from,to,length,"
                 "delay,roadNumbers}}}")
# Île-de-France en 4 rectangles (TomTom limite un rectangle à 10 000 km²) : lon min, lat min, lon max, lat max.
TOMTOM_BOXES = ((1.44, 48.11, 2.50, 48.68), (2.50, 48.11, 3.56, 48.68), (1.44, 48.68, 2.50, 49.25), (2.50, 48.68, 3.56, 49.25))
OPENSKY_TOKEN = "https://auth.opensky-network.org/auth/realms/opensky-network/protocol/openid-connect/token"
OPENSKY_STATES = "https://opensky-network.org/api/states/all"
AIRPORTS = {"CDG": (49.0097, 2.5479), "ORY": (48.7262, 2.3652), "BVA": (49.4544, 2.1128)}
FINAL_ALT_M = 900
FINAL_RADIUS_KM = 15
GROUND_RADIUS_KM = 4


class FeedUnavailableError(RuntimeError):
    pass


def _get(url: str, headers: dict | None = None, data: bytes | None = None) -> dict:
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers or {}, data=data),  # nosec B310
                                    timeout=TIMEOUT_S) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise FeedUnavailableError(f"{urllib.parse.urlsplit(url).netloc} injoignable : {type(exc).__name__}") from exc


def _km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    dlat, dlng = math.radians(lat2 - lat1), math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(a))


def _idfm_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y%m%dT%H%M%S").replace(tzinfo=grid.PARIS)
    except ValueError:
        return None


# --- IDFM ------------------------------------------------------------------------------------------------------

def _stop(db: Session, stop_id: str, name: str | None, fetch_stop, now: datetime) -> RidesTransitStop:
    stop = db.get(RidesTransitStop, stop_id)
    if stop is None:
        lat = lng = None
        try:
            point = (fetch_stop(stop_id).get("stop_points") or [{}])[0].get("coord") or {}
            lat, lng = float(point["lat"]), float(point["lon"])
        except (FeedUnavailableError, KeyError, ValueError, TypeError):
            pass
        stop = RidesTransitStop(stop_id=stop_id, name=name, lat=lat, lng=lng, fetched_at=now,
                                zone_code=grid.zone_at(lat, lng).code if lat is not None else None)
        db.add(stop)
        db.flush()
    return stop


def refresh_transit(db: Session, *, now: datetime | None = None, fetch_bulk=None, fetch_stop=None) -> int:
    """Perturbations en cours des modes lourds ; une ligne par (perturbation, ligne)."""
    now = now or datetime.now(UTC)
    key = get_settings().idfm_prim_api_key
    if fetch_bulk is None or fetch_stop is None:
        if not key:
            raise FeedUnavailableError("Clé IDFM absente.")
        fetch_bulk = fetch_bulk or (lambda: _get(IDFM_BULK, {"apikey": key}))
        fetch_stop = fetch_stop or (lambda sid: _get(IDFM_STOP.format(urllib.parse.quote(sid, safe="")), {"apikey": key}))
    body = fetch_bulk()
    disruptions = {d["id"]: d for d in body.get("disruptions") or []}
    rows = 0
    for line in body.get("lines") or []:
        mode = HEAVY_MODES.get(line.get("mode"))
        if mode is None:
            continue
        stops_by_disruption: dict[str, list[tuple[str, str | None]]] = {}
        for item in line.get("impactedObjects") or []:
            for did in item.get("disruptionIds") or []:
                stops_by_disruption.setdefault(did, [])
                if item.get("type") == "stop_point":
                    stops_by_disruption[did].append((item["id"], item.get("name")))
        for did, stops in stops_by_disruption.items():
            d = disruptions.get(did)
            if d is None or d.get("severity") not in SEVERITIES:
                continue
            periods = [(_idfm_time(p.get("begin")), _idfm_time(p.get("end"))) for p in d.get("applicationPeriods") or []]
            current = [p for p in periods if p[0] and p[1] and p[0] <= now <= p[1]]
            if not current:
                continue
            located = [_stop(db, sid, name, fetch_stop, now) for sid, name in stops[:40]]
            db.add(RidesTransitDisruption(
                id=uuid4(), fetched_at=now, disruption_id=did, line_id=line["id"], line_name=f"{mode} {line.get('shortName') or line.get('name')}",
                mode=mode, severity=d["severity"], cause=d.get("cause"), title=(d.get("title") or "")[:300] or None,
                starts_at=current[0][0], ends_at=current[0][1], stop_ids=[s.stop_id for s in located],
                zone_codes=sorted({s.zone_code for s in located if s.zone_code}),
            ))
            rows += 1
    db.flush()
    return rows


# --- TomTom ----------------------------------------------------------------------------------------------------

def _middle(coordinates) -> tuple[float, float] | None:
    points = coordinates if coordinates and isinstance(coordinates[0], list) else [coordinates] if coordinates else []
    if not points:
        return None
    lng, lat = points[len(points) // 2][:2]
    return float(lat), float(lng)


def refresh_traffic(db: Session, *, now: datetime | None = None, fetch=None) -> int:
    now = now or datetime.now(UTC)
    key = get_settings().tomtom_api_key
    if fetch is None:
        if not key:
            raise FeedUnavailableError("Clé TomTom absente.")
        fetch = lambda box: _get(TOMTOM + "?" + urllib.parse.urlencode({  # noqa: E731
            "key": key, "bbox": ",".join(map(str, box)), "fields": TOMTOM_FIELDS, "language": "fr-FR",
            "timeValidityFilter": "present"}))
    rows, seen = 0, set()
    for box in TOMTOM_BOXES:
        for incident in fetch(box).get("incidents") or []:
            props, middle = incident.get("properties") or {}, _middle((incident.get("geometry") or {}).get("coordinates"))
            if middle is None:
                continue
            ident = (round(middle[0], 4), round(middle[1], 4), props.get("iconCategory"))
            if ident in seen:  # incident à cheval sur deux rectangles
                continue
            seen.add(ident)
            db.add(RidesTrafficIncident(
                id=uuid4(), fetched_at=now, category=props.get("iconCategory"), magnitude=props.get("magnitudeOfDelay"),
                delay_s=props.get("delay"), length_m=int(props["length"]) if props.get("length") is not None else None,
                roads=props.get("roadNumbers") or [], from_text=(props.get("from") or "")[:200] or None,
                to_text=(props.get("to") or "")[:200] or None, lat=middle[0], lng=middle[1],
                zone_code=grid.zone_at(*middle).code,
            ))
            rows += 1
    db.flush()
    return rows


# --- OpenSky ---------------------------------------------------------------------------------------------------

def _opensky_fetch():
    settings = get_settings()
    if not settings.opensky_client_id or not settings.opensky_client_secret:
        raise FeedUnavailableError("Identifiants OpenSky absents.")
    token = _get(OPENSKY_TOKEN, {"Content-Type": "application/x-www-form-urlencoded"}, urllib.parse.urlencode({
        "grant_type": "client_credentials", "client_id": settings.opensky_client_id,
        "client_secret": settings.opensky_client_secret}).encode())["access_token"]
    return lambda box: _get(OPENSKY_STATES + "?" + urllib.parse.urlencode(
        {"lamin": box[0], "lomin": box[1], "lamax": box[2], "lomax": box[3]}), {"Authorization": f"Bearer {token}"})


def refresh_airports(db: Session, *, now: datetime | None = None, fetch=None) -> int:
    now = now or datetime.now(UTC)
    fetch = fetch or _opensky_fetch()
    for code, (lat, lng) in AIRPORTS.items():
        dlat, dlng = FINAL_RADIUS_KM / 111, FINAL_RADIUS_KM / (111 * math.cos(math.radians(lat)))
        states = fetch((lat - dlat, lng - dlng, lat + dlat, lng + dlng)).get("states") or []
        final, ground = [], 0
        for s in states:
            # icao24, indicatif, pays, t_pos, t_contact, lon, lat, alt baro, au sol, vitesse, cap, vitesse verticale…
            if s[5] is None or s[6] is None:
                continue
            km = _km(lat, lng, s[6], s[5])
            if s[8] and km <= GROUND_RADIUS_KM:
                ground += 1
            elif not s[8] and km <= FINAL_RADIUS_KM and (s[7] or 1e9) <= FINAL_ALT_M and (s[11] or 0) < 0:
                final.append(s[0])
        db.add(RidesAirportSnapshot(id=uuid4(), fetched_at=now, airport=code, approaching=len(final), on_ground=ground,
                                    final_icao=sorted(set(final))))
    db.flush()
    return len(AIRPORTS)


# --- Situation à un lieu et un instant (offres, mesures après dépose) -------------------------------------------

def _latest(db: Session, model, at: datetime):
    fetched = db.scalar(select(func.max(model.fetched_at)).where(model.fetched_at <= at + timedelta(minutes=2)))
    return fetched if fetched is not None and fetched >= at - FRESH else None


def landings(db: Session, airport: str, start: datetime, end: datetime) -> int | None:
    """Avions distincts vus en approche finale entre deux instants (≈ atterrissages) ; None sans relevé."""
    rows = list(db.scalars(select(RidesAirportSnapshot.final_icao).where(
        RidesAirportSnapshot.airport == airport, RidesAirportSnapshot.fetched_at.between(start, end))))
    return len({icao for row in rows for icao in row}) if rows else None


def context(db: Session, at: datetime, places: dict[str, tuple[float, float] | None]) -> dict:
    """Variables du moment : Île-de-France entière, puis pour chaque lieu (« pickup », « dest », « drop »…)."""
    out: dict = {}
    fetched = _latest(db, RidesTransitDisruption, at)
    disruptions = list(db.scalars(select(RidesTransitDisruption).where(RidesTransitDisruption.fetched_at == fetched))) \
        if fetched else None
    if disruptions is None:
        out.update({"transit_heavy_disruptions": None, "transit_blocking": None, "rer_lines_disrupted": None,
                    "metro_lines_disrupted": None})
    else:
        out.update({
            "transit_heavy_disruptions": len(disruptions),
            "transit_blocking": sum(1 for d in disruptions if d.severity == "BLOQUANTE"),
            "rer_lines_disrupted": len({d.line_id for d in disruptions if d.mode in ("rer", "transilien")}),
            "metro_lines_disrupted": len({d.line_id for d in disruptions if d.mode == "metro"}),
        })
    stops = {}
    if disruptions:
        ids = {sid for d in disruptions for sid in d.stop_ids}
        stops = {s.stop_id: s for s in db.scalars(select(RidesTransitStop).where(RidesTransitStop.stop_id.in_(ids)))}
    t_fetched = _latest(db, RidesTrafficIncident, at)
    incidents = list(db.scalars(select(RidesTrafficIncident).where(RidesTrafficIncident.fetched_at == t_fetched))) \
        if t_fetched else None
    if incidents is None:
        out.update({"traffic_incidents_idf": None, "traffic_delay_idf_min": None, "traffic_closures_idf": None})
    else:
        out.update({
            "traffic_incidents_idf": len(incidents),
            "traffic_delay_idf_min": round(sum(i.delay_s or 0 for i in incidents) / 60),
            # Fermetures : axes numérotés seulement (A, N, D, périphérique…) ; les petites rues en travaux sont légion.
            "traffic_closures_idf": sum(1 for i in incidents if i.category == 8 and i.roads),
        })
    for code in AIRPORTS:
        key = code.lower()
        out[f"{key}_landings_30_60_min"] = landings(db, code, at - timedelta(minutes=60), at - timedelta(minutes=30))
        out[f"{key}_landings_last_30_min"] = landings(db, code, at - timedelta(minutes=30), at)
    for name, where in places.items():
        if where is None:
            out.update({f"{name}_transit_disrupted": None, f"{name}_transit_blocking": None,
                        f"{name}_traffic_delay_min": None, f"{name}_road_closed": None})
            continue
        lat, lng = where
        near = [d for d in disruptions or [] if any(
            (s := stops.get(sid)) is not None and s.lat is not None and _km(lat, lng, float(s.lat), float(s.lng)) <= NEAR_KM
            for sid in d.stop_ids)]
        close = [i for i in incidents or [] if _km(lat, lng, float(i.lat), float(i.lng)) <= TRAFFIC_NEAR_KM]
        out.update({
            f"{name}_transit_disrupted": bool(near) if disruptions is not None else None,
            f"{name}_transit_blocking": any(d.severity == "BLOQUANTE" for d in near) if disruptions is not None else None,
            f"{name}_transit_lines": sorted({d.line_name for d in near}) if near else [],
            f"{name}_traffic_delay_min": round(sum(i.delay_s or 0 for i in close) / 60) if incidents is not None else None,
            f"{name}_road_closed": any(i.category == 8 and i.roads for i in close) if incidents is not None else None,
        })
    return out


def drop_context(db: Session, at: datetime, lat: float | None, lng: float | None) -> dict:
    """Situation au lieu et à l'heure d'une dépose : pluie de la case, perturbations, bouchons, avions."""
    where = (lat, lng) if lat is not None and lng is not None else None
    rain = weather.offer_features(db, at, lat=lat, lng=lng) if where else {}
    return {**context(db, at, {"drop": where}),
            **{k.replace("weather_pickup", "drop_weather"): v for k, v in rain.items() if k.startswith("weather_pickup")}}


# --- Jobs (seulement pendant une session VTC ouverte) ------------------------------------------------------------

def _run(ctx, steps) -> None:
    if not weather.session_open(ctx.db):
        ctx.items_in = ctx.items_out = 0
        ctx.detail = {"skipped": "no_open_session"}
        return
    detail, total = {}, 0
    for name, step in steps:
        try:
            count = step(ctx.db)
            ctx.db.commit()
            detail[name], total = count, total + count
        except FeedUnavailableError as exc:
            ctx.db.rollback()
            logger.warning("vector.%s: %s", name, exc)
            detail[name] = f"erreur : {exc}"
    ctx.items_in = ctx.items_out = total
    ctx.detail = detail


def transit_traffic_job(ctx, window) -> None:  # noqa: ARG001 - signature du runner
    _run(ctx, [("transit", refresh_transit), ("traffic", refresh_traffic)])


def airports_job(ctx, window) -> None:  # noqa: ARG001 - signature du runner
    _run(ctx, [("airports", refresh_airports)])
