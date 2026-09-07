"""Serve the same-origin demo; model credentials never cross this boundary."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.app.core.config import Settings
from backend.app.services.document_ingestion import MAX_UPLOAD_BYTES

WEB_ROOT = Path(__file__).resolve().parents[3] / "frontend"


def install_workbench(application: FastAPI, settings: Settings) -> None:
    application.mount("/static", StaticFiles(directory=WEB_ROOT / "static"), name="static")

    @application.get("/", include_in_schema=False)
    def workbench() -> FileResponse:
        return FileResponse(WEB_ROOT / "index.html")

    @application.get("/app-config", include_in_schema=False)
    def public_config() -> dict[str, object]:
        return {
            "api_prefix": settings.api_prefix,
            "answer_generator": settings.answer_generator,
            "auth_required": bool(
                settings.api_access_token and settings.api_access_token.get_secret_value().strip()
            ),
            "max_upload_bytes": MAX_UPLOAD_BYTES,
            "agent_max_steps": settings.agent_max_steps,
        }
