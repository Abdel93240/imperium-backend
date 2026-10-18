"""Réglages Path (PAT-11, doc 41 §6.4) : méthode de calcul, madhhab et ville du calcul local.

Ils ne servent qu'au calcul local des horaires : le cache MAWAQIT de la mosquée de référence
reste prioritaire (doc 41 §6.2), et une mosquée de référence à coordonnées l'emporte sur la
ville. La ville est saisie avec ses coordonnées (pas de géocodage : il passerait par le
réseau) ; le fuseau reste Europe/Paris. Sans réglage enregistré, les paramètres globaux
path.calc_method / path.madhhab et Paris s'appliquent. Méthodes Jafari et Custom du doc 41
§6.4 : pas encore dans le moteur.

Pourcentage de sadaqa : /sadaqa/settings ; mosquées : /mosques ; routines : /adhkar.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.enums import PrivacyLevel, SourceApp
from app.models.path import CALCULATION_METHODS, MADHHABS, PathSettings
from app.schemas.path_settings import PathCity, PathSettingsRead, PathSettingsUpdate
from app.services.events.emitter import build_event
from app.services.path.fasting import paris_today
from app.services.path.prayer import calculation_config, prayer_times
from app.services.pulse import food_stock


class PathSettingsVersionConflictError(ValueError):
    def __init__(self, current: PathSettingsRead) -> None:
        super().__init__("Les réglages Path ont changé depuis ta lecture.")
        self.current = current


def get_settings(db: Session, *, current_user: User) -> PathSettingsRead:
    row = db.scalar(select(PathSettings).where(PathSettings.user_id == current_user.id))
    return _read(db, current_user, row)


def update_settings(
    db: Session, *, current_user: User, payload: PathSettingsUpdate, idempotency_key: str, request_path: str
) -> PathSettingsRead:
    fingerprint = food_stock.request_hash("path.settings", payload.model_dump(mode="json", exclude_unset=True))
    previous = food_stock.replay(db, current_user, idempotency_key, fingerprint, request_path, PathSettingsRead)
    if previous is not None:
        return previous
    row = db.scalar(select(PathSettings).where(PathSettings.user_id == current_user.id).with_for_update())
    current_version = row.version if row is not None else 0
    if payload.version != current_version:
        raise PathSettingsVersionConflictError(_read(db, current_user, row))
    before = _values(db, current_user, row)
    changes = payload.model_dump(exclude_unset=True, exclude={"version"})
    if row is None:
        row = PathSettings(user_id=current_user.id, calculation_method=before["calculation_method"],
                           madhhab=before["madhhab"], version=0)
        db.add(row)
    if changes.get("calculation_method") is not None:
        row.calculation_method = changes["calculation_method"]
    if changes.get("madhhab") is not None:
        row.madhhab = changes["madhhab"]
    if "city" in changes:
        city = payload.city
        row.city_name = city.name.strip() if city else None
        row.latitude = city.latitude if city else None
        row.longitude = city.longitude if city else None
    changed = [field for field, value in _values(db, current_user, row).items() if value != before[field]]
    if not changed:
        if row.version == 0:
            db.expunge(row)
            row = None
        read = _read(db, current_user, row)
    else:
        row.version += 1
        db.flush()
        db.refresh(row)
        db.add(
            build_event(
                db, user_id=current_user.id, event_type="path.settings.updated",
                payload={"changed": changed, "calculation_method": row.calculation_method, "madhhab": row.madhhab,
                         "has_city": row.city_name is not None, "version": row.version},
                idempotency_key=f"path.settings.{row.id}.v{row.version}", source_app=SourceApp.path,
                privacy_level=PrivacyLevel.high,
            )
        )
        read = _read(db, current_user, row)
    food_stock.remember(db, current_user, idempotency_key, "PATCH", request_path, fingerprint, 200, read)
    db.commit()
    return read


def _values(db: Session, user: User, row: PathSettings | None) -> dict:
    if row is None:
        config = calculation_config(db, None)  # paramètres globaux, comme avant tout réglage
        return {"calculation_method": config.method, "madhhab": config.madhhab, "city": None}
    city = (row.city_name, row.latitude, row.longitude) if row.city_name is not None else None
    return {"calculation_method": row.calculation_method, "madhhab": row.madhhab, "city": city}


def _read(db: Session, user: User, row: PathSettings | None) -> PathSettingsRead:
    config = calculation_config(db, user.id)
    _, times_source = prayer_times(db, paris_today(), user_id=user.id)
    city = (
        PathCity(name=row.city_name, latitude=row.latitude, longitude=row.longitude)
        if row is not None and row.city_name is not None
        else None
    )
    return PathSettingsRead(
        calculation_method=config.method, madhhab=config.madhhab, city=city,
        version=row.version if row is not None else 0, updated_at=row.updated_at if row is not None else None,
        location_source=config.location_source, times_source=times_source,
        supported_methods=list(CALCULATION_METHODS), supported_madhhabs=list(MADHHABS),
    )
