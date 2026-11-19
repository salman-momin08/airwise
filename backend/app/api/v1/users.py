from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import RequestPrincipal, require_authenticated_user
from app.core.exceptions import AirWiseError

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me")
async def get_user_profile(
    _principal: Annotated[RequestPrincipal, Depends(require_authenticated_user)],
) -> dict[str, object]:
    raise AirWiseError(
        code="NOT_IMPLEMENTED_PHASE_2",
        message="User profile persistence is scheduled for Phase 2 (Authentication & Profiles).",
        status_code=501,
    )
