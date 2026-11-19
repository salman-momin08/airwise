from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import RequestPrincipal, require_authenticated_user
from app.core.exceptions import AirWiseError

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("")
async def list_alert_rules(
    _principal: Annotated[RequestPrincipal, Depends(require_authenticated_user)],
) -> dict[str, object]:
    raise AirWiseError(
        code="NOT_IMPLEMENTED_PHASE_6",
        message="Smart alert rule management is scheduled for Phase 6.",
        status_code=501,
    )
