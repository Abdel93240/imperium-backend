"""Réglage versionné des barèmes `df.*` (spec Daily §4.5, §10.3, §12 ; carte ACT-DLY-02).

`GET/PUT /api/daily/settings/scoring`, servis seulement si `daily.settings_enabled` (semé false).
Une modification = une NOUVELLE version de chaque paramètre changé (jamais d'écrasement : table
append-only, l'ancienne version reste interrogeable), avec la raison de l'utilisateur et la date de
la version (`valid_from`), et un event `decision.scoring.updated` par paramètre (`df.parameter_updated`
de la spec §11). Le jeu complet est validé avant écriture (`scales_from_parameter_values`) : un
barème incohérent est refusé en entier. Les tests dorés de parité ne s'appliquent pas aux réglages
volontaires (§10.3). Le refresh du registre `imperium_mission_scores` arrive avec ACT-DLY-03.
"""

import hashlib
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.enums import IdempotencyStatus, PrivacyLevel, SourceApp
from app.models.idempotency import IdempotencyKey
from app.models.toolbox import Parameter
from app.schemas.daily import ScoringParameterRead, ScoringSettingsRead, ScoringSettingsUpdateRequest
from app.services.events.emitter import build_event
from app.services.imperium import decision_framework as df
from app.services.params import get_parameter, set_parameter


class ScoringSettingsError(ValueError):
    def __init__(self, message: str, code: str) -> None:
        super().__init__(message)
        self.code = code


def settings_enabled(db: Session) -> bool:
    return bool(get_parameter(db, "daily.settings_enabled", default=False))


def read_settings(db: Session) -> ScoringSettingsRead:
    rows = {row.code: row for row in _current_rows(db)}
    in_use = df.load_scales(db)
    return ScoringSettingsRead(
        source="parameters" if len(rows) == len(df.SCALE_PARAMETERS) and in_use is not df.CODE_SCALES else "code",
        parameters=[_read(rows[code]) for code in df.SCALE_PARAMETERS if code in rows],
    )


def list_versions(db: Session, *, code: str) -> list[ScoringParameterRead]:
    if code not in df.SCALE_PARAMETERS:
        raise ScoringSettingsError(f"Unknown scoring parameter '{code}'.", "SCORING_PARAMETER_UNKNOWN")
    rows = db.scalars(select(Parameter).where(Parameter.code == code).order_by(Parameter.version.desc())).all()
    return [_read(row) for row in rows]


def update_settings(
    db: Session,
    *,
    current_user: User,
    request: ScoringSettingsUpdateRequest,
    idempotency_key: str,
    request_path: str,
) -> ScoringSettingsRead:
    fingerprint = hashlib.sha256(json.dumps(
        {"ns": "daily.settings.scoring", **request.model_dump(mode="json")}, sort_keys=True).encode()).hexdigest()
    previous = db.scalar(select(IdempotencyKey).where(
        IdempotencyKey.user_id == current_user.id, IdempotencyKey.idempotency_key == idempotency_key))
    if previous is not None:
        if previous.request_path != request_path or previous.request_hash != fingerprint or previous.response_body is None:
            raise ScoringSettingsError("Idempotency key already used with a different request.", "IDEMPOTENCY_CONFLICT")
        return ScoringSettingsRead.model_validate(previous.response_body)

    unknown = sorted(set(request.changes) - set(df.SCALE_PARAMETERS))
    if unknown:
        raise ScoringSettingsError(f"Unknown scoring parameters: {unknown}.", "SCORING_PARAMETER_UNKNOWN")
    current = {row.code: row for row in _current_rows(db)}
    if len(current) != len(df.SCALE_PARAMETERS):
        raise ScoringSettingsError("The df.* parameters are not seeded (migration 0101).", "SCORING_NOT_SEEDED")
    changed = {code: value for code, value in request.changes.items() if value != current[code].value}
    if not changed:
        raise ScoringSettingsError("No scoring value differs from the current version.", "SCORING_NO_CHANGE")
    try:
        df.scales_from_parameter_values({**{code: row.value for code, row in current.items()}, **changed})
    except (ValueError, KeyError, TypeError) as exc:
        raise ScoringSettingsError(f"Invalid scoring scales: {exc}", "SCORING_INVALID") from exc

    for code in sorted(changed):
        old = current[code]
        new = set_parameter(db, code=code, value=changed[code], origin="user", rationale_fr=request.reason_fr)
        db.add(build_event(
            db, user_id=current_user.id, event_type="decision.scoring.updated",
            payload={"param_code": code, "old_version": old.version, "new_version": new.version,
                     "reason_fr": request.reason_fr},
            idempotency_key=f"decision.scoring.updated.{new.id}", source_app=SourceApp.imperium,
            privacy_level=PrivacyLevel.low, occurred_at=new.valid_from,
        ))
        db.flush()
    read = read_settings(db)
    db.add(IdempotencyKey(
        user_id=current_user.id, idempotency_key=idempotency_key, request_method="PUT", request_path=request_path,
        request_hash=fingerprint, status=IdempotencyStatus.completed, response_status_code=200,
        response_body=read.model_dump(mode="json"),
    ))
    db.commit()
    return read


def _current_rows(db: Session) -> list[Parameter]:
    return list(db.scalars(select(Parameter).where(
        Parameter.code.in_(list(df.SCALE_PARAMETERS)), Parameter.superseded_by.is_(None))))


def _read(row: Parameter) -> ScoringParameterRead:
    return ScoringParameterRead(code=row.code, version=row.version, value=row.value, origin=row.origin,
                                rationale_fr=row.rationale_fr, valid_from=row.valid_from)
