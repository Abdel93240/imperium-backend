"""Consentement aux domaines de santé sensibles (cadre validé le 2026-10-17, doc 05).

Un consentement explicite par domaine (body, pain, medical) : l'utilisateur accepte
un texte versionné, la date est gardée, il peut le retirer à tout moment. Sans
consentement actif, les écritures du domaine sont refusées ; l'accès à ses propres
données et leur suppression restent toujours possibles.
"""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.enums import PrivacyLevel, SourceApp
from app.models.imperium import PulseHealthConsent
from app.schemas.pulse_health import ConsentListResponse, ConsentRead
from app.services.events.emitter import build_event

DOMAINS = ("body", "pain", "medical")
TEXT_VERSION = "2026-10-17"
TEXTS_FR = {
    "body": (
        "J'accepte qu'Imperium enregistre mes relevés corporels (poids, masse grasse, tour de taille, de poitrine, "
        "de bras, notes). Aucune photo n'est envoyée au serveur. Ces données ne servent qu'à me montrer ma progression, "
        "jamais à tirer une conclusion médicale. Je peux retirer mon accord et tout supprimer à tout moment."
    ),
    "pain": (
        "J'accepte qu'Imperium enregistre mes douleurs (zone, intensité, gêne, notes) pour adapter mes séances. "
        "Ce n'est pas un avis médical. Je peux retirer mon accord et tout supprimer à tout moment."
    ),
    "medical": (
        "J'accepte qu'Imperium enregistre mes documents et règles médicales pour en tenir compte dans mon planning. "
        "Rien n'est appliqué sans ma validation, et ce n'est pas un avis médical. Je peux retirer mon accord et tout "
        "supprimer à tout moment."
    ),
}


class ConsentRequiredError(PermissionError):
    def __init__(self, domain: str) -> None:
        super().__init__(f"Consent required for {domain} data.")
        self.domain = domain


class ConsentVersionError(ValueError):
    pass


def list_consents(db: Session, *, current_user: User) -> ConsentListResponse:
    return ConsentListResponse(items=[_read(db, current_user, domain) for domain in DOMAINS])


def grant(db: Session, *, current_user: User, domain: str, text_version: str) -> ConsentRead:
    if text_version != TEXT_VERSION:
        raise ConsentVersionError("The consent text changed: show the current text and ask again.")
    if _active(db, current_user, domain) is None:
        consent = PulseHealthConsent(
            user_id=current_user.id, domain=domain, text_version=text_version, granted_at=datetime.now(UTC)
        )
        db.add(consent)
        db.flush()
        _emit(db, current_user, "pulse.health_consent.granted", consent)
        db.commit()
    return _read(db, current_user, domain)


def revoke(db: Session, *, current_user: User, domain: str) -> ConsentRead:
    consent = _active(db, current_user, domain, lock=True)
    if consent is not None:
        consent.revoked_at = datetime.now(UTC)
        _emit(db, current_user, "pulse.health_consent.revoked", consent)
        db.commit()
    return _read(db, current_user, domain)


def require(db: Session, current_user: User, domain: str) -> None:
    if _active(db, current_user, domain) is None:
        raise ConsentRequiredError(domain)


def _active(db: Session, current_user: User, domain: str, *, lock: bool = False) -> PulseHealthConsent | None:
    query = select(PulseHealthConsent).where(
        PulseHealthConsent.user_id == current_user.id, PulseHealthConsent.domain == domain,
        PulseHealthConsent.revoked_at.is_(None),
    )
    return db.scalar(query.with_for_update() if lock else query)


def _read(db: Session, current_user: User, domain: str) -> ConsentRead:
    latest = db.scalar(
        select(PulseHealthConsent)
        .where(PulseHealthConsent.user_id == current_user.id, PulseHealthConsent.domain == domain)
        .order_by(PulseHealthConsent.granted_at.desc())
        .limit(1)
    )
    active = latest is not None and latest.revoked_at is None
    return ConsentRead(
        domain=domain, granted=active, granted_at=latest.granted_at if active else None,
        revoked_at=latest.revoked_at if latest is not None and not active else None,
        text_version=TEXT_VERSION, text_fr=TEXTS_FR[domain],
    )


def _emit(db: Session, current_user: User, event_type: str, consent: PulseHealthConsent) -> None:
    db.add(
        build_event(
            db, user_id=current_user.id, event_type=event_type,
            payload={"domain": consent.domain, "text_version": consent.text_version},
            idempotency_key=f"{event_type}.{consent.id}", source_app=SourceApp.pulse, privacy_level=PrivacyLevel.medium,
        )
    )
