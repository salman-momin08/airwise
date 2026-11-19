from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import get_response_meta
from app.schemas.common import ApiResponse, ResponseMeta

router = APIRouter(prefix="/communities", tags=["community"])


@router.get("", response_model=ApiResponse[list[dict[str, object]]])
async def list_communities(
    meta: Annotated[ResponseMeta, Depends(get_response_meta)],
) -> ApiResponse[list[dict[str, object]]]:
    return ApiResponse(data=[], meta=meta)
