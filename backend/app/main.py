from fastapi import FastAPI

from backend.app.api.routes.health import router as health_router
from backend.app.api.routes.info import router as info_router
from backend.app.api.routes.search import router as search_router
from backend.app.core.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Evidence-grounded maintenance assistant for industrial IoT equipment.",
    )
    application.include_router(health_router, prefix=settings.api_prefix)
    application.include_router(info_router, prefix=settings.api_prefix)
    application.include_router(
        search_router,
        prefix=settings.api_prefix,
    )
    return application


app = create_app()
