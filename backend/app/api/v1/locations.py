from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_response_meta
from app.schemas.common import ApiResponse, ResponseMeta

router = APIRouter(prefix="/locations", tags=["locations"])

SUPPORTED_GAZETTEER: tuple[dict[str, str], ...] = (
    {
        "city": "Delhi",
        "state_region": "NCT of Delhi",
        "country_code": "IN",
        "timezone": "Asia/Kolkata",
    },
    {
        "city": "Bengaluru",
        "state_region": "Karnataka",
        "country_code": "IN",
        "timezone": "Asia/Kolkata",
    },
    {
        "city": "Mumbai",
        "state_region": "Maharashtra",
        "country_code": "IN",
        "timezone": "Asia/Kolkata",
    },
    {
        "city": "Chennai",
        "state_region": "Tamil Nadu",
        "country_code": "IN",
        "timezone": "Asia/Kolkata",
    },
    {
        "city": "Kolkata",
        "state_region": "West Bengal",
        "country_code": "IN",
        "timezone": "Asia/Kolkata",
    },
)


@router.get("/search", response_model=ApiResponse[list[dict[str, str]]])
async def search_cities(
    q: Annotated[str, Query(min_length=1, max_length=80)],
    meta: Annotated[ResponseMeta, Depends(get_response_meta)],
) -> ApiResponse[list[dict[str, str]]]:
    needle = q.strip().lower()
    matches = [item for item in SUPPORTED_GAZETTEER if needle in item["city"].lower()]
    return ApiResponse(data=matches, meta=meta)
