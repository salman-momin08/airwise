from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import RequestPrincipal, require_authenticated_user
from app.core.exceptions import AirWiseError

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.get("/today")
async def get_today_recommendations(
    _principal: Annotated[RequestPrincipal, Depends(require_authenticated_user)],
) -> dict[str, object]:
    raise AirWiseError(
        code="NOT_IMPLEMENTED_PHASE_5",
        message="Hybrid personalized recommendation generation is scheduled for Phase 5.",
        status_code=501,
    )
