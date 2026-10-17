"""État des services (maquette 19, kit : jamais de vert par défaut) — tests unitaires."""
from types import SimpleNamespace

from app.services import service_health as sh


def _settings(**overrides):
    base = dict(embeddings_enabled=True, embedding_base_url="http://gpu:8000", qwen_enabled=True, qwen_dry_run=False,
                qwen_base_url="http://tower:11434")
    base.update(overrides)
    return SimpleNamespace(**base)


def _probes(db=True, vector_ext=True, gpu=True, ollama=True):
    return sh.Probes(database=lambda: db, vector_extension=lambda: vector_ext, embedding_service=lambda: gpu,
                     local_model=lambda: ollama)


def _states(report):
    return {service.code: service.state for service in report.services}


def test_all_up_is_green_except_cloud_which_is_never_verified() -> None:
    report = sh.check_services(settings=_settings(), probes=_probes())
    assert _states(report) == {"api": "green", "database": "green", "vector_memory": "green", "local_ai": "green", "cloud_ai": "grey"}
    assert report.overall == "green"


def test_gpu_down_degrades_vector_memory() -> None:
    report = sh.check_services(settings=_settings(), probes=_probes(gpu=False))
    assert _states(report)["vector_memory"] == "orange" and report.overall == "orange"


def test_missing_pgvector_makes_memory_unavailable() -> None:
    assert _states(sh.check_services(settings=_settings(), probes=_probes(vector_ext=False)))["vector_memory"] == "red"


def test_disabled_features_are_not_verified_never_green() -> None:
    report = sh.check_services(settings=_settings(embeddings_enabled=False, qwen_dry_run=True), probes=_probes())
    states = _states(report)
    assert states["vector_memory"] == "grey" and states["local_ai"] == "grey"
    assert report.overall == "green"  # rien de cassé : seulement non vérifié


def test_local_model_down_is_red() -> None:
    report = sh.check_services(settings=_settings(), probes=_probes(ollama=False))
    assert _states(report)["local_ai"] == "red" and report.overall == "orange"


def test_database_down_is_overall_red() -> None:
    report = sh.check_services(settings=_settings(), probes=_probes(db=False))
    assert _states(report)["database"] == "red" and report.overall == "red"


def test_probe_exceptions_count_as_unavailable() -> None:
    def boom():
        raise RuntimeError("x")

    probes = sh.Probes(database=boom, vector_extension=boom, embedding_service=boom, local_model=boom)
    states = _states(sh.check_services(settings=_settings(), probes=probes))
    assert states["database"] == "red" and states["local_ai"] == "red"


def test_labels_are_french_and_every_service_has_a_detail() -> None:
    report = sh.check_services(settings=_settings(), probes=_probes())
    assert [s.label for s in report.services] == ["API Imperium", "Base de données", "Mémoire vectorielle", "IA locale", "IA cloud"]
    assert all(s.detail for s in report.services)


def test_route_requires_authentication_and_is_registered() -> None:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.api.v1.router import api_router

    app = FastAPI()
    app.include_router(api_router, prefix="/api")
    response = TestClient(app).get("/api/health/services")
    assert response.status_code in (401, 403)


def test_real_probes_on_the_test_database() -> None:
    import os

    import pytest

    url = os.environ.get("IMPERIUM_TEST_DATABASE_URL")
    if not url:
        pytest.skip("IMPERIUM_TEST_DATABASE_URL not set.")
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    engine = create_engine(url, future=True)
    with Session(engine) as db:
        settings = _settings(embedding_base_url="http://127.0.0.1:9", qwen_base_url="http://127.0.0.1:9")
        report = sh.check_services(settings=settings, probes=sh.default_probes(db, settings))
    engine.dispose()
    states = _states(report)
    # Base réelle + pgvector présents ; GPU et Ollama injoignables sur ce port fermé.
    assert states["database"] == "green" and states["vector_memory"] == "orange" and states["local_ai"] == "red"
