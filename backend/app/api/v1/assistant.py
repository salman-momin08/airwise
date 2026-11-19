from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.ai.prompts.system_prompts import PROMPT_VERSION
from app.ai.tools.registry import ALLOWLISTED_AI_TOOLS, MAX_TOOL_CALL_DEPTH
from app.api.dependencies import get_response_meta
from app.schemas.common import ApiResponse, ResponseMeta

router = APIRouter(prefix="/assistant", tags=["assistant"])


@router.get("/capabilities", response_model=ApiResponse[dict[str, object]])
async def get_assistant_capabilities(
    meta: Annotated[ResponseMeta, Depends(get_response_meta)],
) -> ApiResponse[dict[str, object]]:
    return ApiResponse(
        data={
            "assistant_name": "AirWise Copilot",
            "prompt_version": PROMPT_VERSION,
            "max_tool_call_depth": MAX_TOOL_CALL_DEPTH,
            "allowlisted_tools": [
                {"name": t.name, "auth_scope": t.auth_scope.value, "description": t.description}
                for t in ALLOWLISTED_AI_TOOLS
            ],
        },
        meta=meta,
    )
