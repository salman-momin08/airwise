from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import RequestPrincipal, get_response_meta, require_admin_user
from app.schemas.common import ApiResponse, ResponseMeta

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/status", response_model=ApiResponse[dict[str, str]])
async def get_admin_status(
    principal: Annotated[RequestPrincipal, Depends(require_admin_user)],
    meta: Annotated[ResponseMeta, Depends(get_response_meta)],
) -> ApiResponse[dict[str, str]]:
    return ApiResponse(
        data={"admin_user_id": str(principal.user_id), "status": "authorized"},
        meta=meta,
    )
