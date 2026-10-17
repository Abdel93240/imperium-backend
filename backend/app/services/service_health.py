"""État des services pour l'écran « Connexion à Imperium » (maquette 19, doc 65 §8.5).

Légende : green disponible, orange dégradé, red indisponible, grey non vérifié.
Règle du kit : un service qu'on ne peut pas vérifier n'est JAMAIS vert par défaut.
Chaque sonde est courte (2 s) et toute exception vaut « indisponible ».
"""

import logging
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

PROBE_TIMEOUT_SECONDS = 2


class ServiceHealthRead(BaseModel):
    code: str
    label: str
    state: str  # green | orange | red | grey
    detail: str


class ServiceHealthReport(BaseModel):
    checked_at: datetime
    overall: str
    services: list[ServiceHealthRead]


@dataclass
class Probes:
    database: Callable[[], bool]
    vector_extension: Callable[[], bool]
    embedding_service: Callable[[], bool]
    local_model: Callable[[], bool]


def default_probes(db: Session, settings) -> Probes:
    def database() -> bool:
        db.execute(text("SELECT 1"))
        return True

    def vector_extension() -> bool:
        return db.execute(text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")).scalar() == 1

    return Probes(
        database=database,
        vector_extension=vector_extension,
        embedding_service=lambda: _http_ok(settings.embedding_base_url, "/health"),
        local_model=lambda: _http_ok(settings.qwen_base_url, "/api/tags"),
    )


def check_services(*, settings, probes: Probes) -> ServiceHealthReport:
    services = [
        ServiceHealthRead(code="api", label="API Imperium", state="green", detail="L'API répond."),
        _database(probes),
        _vector_memory(settings, probes),
        _local_ai(settings, probes),
        ServiceHealthRead(
            code="cloud_ai",
            label="IA cloud",
            state="grey",
            detail="Aucun fournisseur cloud n'est branché au backend : non vérifié.",
        ),
    ]
    return ServiceHealthReport(checked_at=datetime.now(UTC), overall=_overall(services), services=services)


def _database(probes: Probes) -> ServiceHealthRead:
    ok = _safe(probes.database)
    return ServiceHealthRead(
        code="database", label="Base de données", state="green" if ok else "red",
        detail="La base répond." if ok else "La base ne répond pas.",
    )


def _vector_memory(settings, probes: Probes) -> ServiceHealthRead:
    base = {"code": "vector_memory", "label": "Mémoire vectorielle"}
    if not _safe(probes.vector_extension):
        return ServiceHealthRead(**base, state="red", detail="Extension pgvector absente : mémoire indisponible.")
    if not settings.embeddings_enabled or not settings.embedding_base_url:
        return ServiceHealthRead(**base, state="grey", detail="Embeddings désactivés : non vérifié.")
    if not _safe(probes.embedding_service):
        return ServiceHealthRead(
            **base, state="orange", detail="Mémoire lisible, mais le service d'embeddings (GPU) ne répond pas."
        )
    return ServiceHealthRead(**base, state="green", detail="Mémoire et service d'embeddings disponibles.")


def _local_ai(settings, probes: Probes) -> ServiceHealthRead:
    base = {"code": "local_ai", "label": "IA locale"}
    if not settings.qwen_enabled or settings.qwen_dry_run or not settings.qwen_base_url:
        return ServiceHealthRead(**base, state="grey", detail="Modèle local désactivé (mode à blanc) : non vérifié.")
    if not _safe(probes.local_model):
        return ServiceHealthRead(**base, state="red", detail="Le modèle local ne répond pas.")
    return ServiceHealthRead(**base, state="green", detail="Le modèle local répond.")


def _overall(services: list[ServiceHealthRead]) -> str:
    states = {service.code: service.state for service in services}
    if "red" in (states["api"], states["database"]):
        return "red"
    if any(state in ("red", "orange") for state in states.values()):
        return "orange"
    return "green"


def _safe(probe: Callable[[], bool]) -> bool:
    try:
        return bool(probe())
    except Exception:  # noqa: BLE001 - toute erreur de sonde vaut « indisponible »
        logger.warning("Health probe failed.", exc_info=True)
        return False


def _http_ok(base_url: str | None, path: str) -> bool:
    if not base_url:
        return False
    url = base_url.rstrip("/") + path
    if not url.startswith(("http://", "https://")):
        return False
    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=PROBE_TIMEOUT_SECONDS) as response:  # nosec B310 - internal configured URL
            return response.status == 200
    except (urllib.error.URLError, TimeoutError, OSError):
        return False
