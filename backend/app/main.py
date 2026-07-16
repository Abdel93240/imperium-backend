from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.router import api_router
from app.core.config import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    if settings.runner_scheduler_autostart:
        from app.services.runner.scheduler import shutdown_runner, start_runner

        start_runner()
        try:
            yield
        finally:
            shutdown_runner()
    else:
        yield


def create_app() -> FastAPI:
    settings = get_settings()
    settings.validate_for_startup()
    app = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
        version="0.1.0",
        lifespan=lifespan,
    )
    app.include_router(api_router, prefix=settings.api_v1_prefix)
    return app


app = create_app()
