from fastapi import APIRouter

from backend.app.core.config import get_settings
from backend.app.schemas.info import InfoResponse

router = APIRouter(tags=["system"])


@router.get("/info", response_model=InfoResponse)
def get_info() -> InfoResponse:
    settings = get_settings()
    return InfoResponse(
        name=settings.app_name,
        purpose="Evidence-grounded maintenance assistance",
        safety_notice="Recommendations require human verification",
    )
