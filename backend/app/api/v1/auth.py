from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import RequestPrincipal, get_current_principal, get_response_meta
from app.schemas.common import ApiResponse, ResponseMeta

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me", response_model=ApiResponse[dict[str, str | None]])
async def get_current_session_principal(
    principal: Annotated[RequestPrincipal, Depends(get_current_principal)],
    meta: Annotated[ResponseMeta, Depends(get_response_meta)],
) -> ApiResponse[dict[str, str | None]]:
    return ApiResponse(
        data={
            "user_id": str(principal.user_id) if principal.user_id else None,
            "role": principal.role.value,
        },
        meta=meta,
    )
