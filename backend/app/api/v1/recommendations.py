"""Personalized exposure-first daily recommendation cards and user feedback endpoints."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    AuthenticatedPrincipal,
    enforce_csrf_protection,
    get_app_settings,
    get_response_meta,
    require_authenticated_user,
)
from app.core.config import Settings
from app.core.rate_limit import rate_limiter
from app.db.session import get_db_session
from app.schemas.common import ApiResponse, ResponseMeta
from app.schemas.recommendations import (
    GenerateRecommendationsRequest,
    RecommendationCardSchema,
    RecommendationFeedbackRequest,
    RecommendationFeedbackSchema,
)
from app.services.recommendations.recommendation_service import HybridRecommendationService

router = APIRouter(prefix="/recommendations", tags=["recommendations"])

Principal = Annotated[AuthenticatedPrincipal, Depends(require_authenticated_user)]
Database = Annotated[AsyncSession, Depends(get_db_session)]
AppSettings = Annotated[Settings, Depends(get_app_settings)]
Meta = Annotated[ResponseMeta, Depends(get_response_meta)]


@router.post(
    "/generate",
    response_model=ApiResponse[list[RecommendationCardSchema]],
    dependencies=[Depends(enforce_csrf_protection)],
)
async def generate_recommendations_endpoint(
    payload: GenerateRecommendationsRequest,
    principal: Principal,
    db: Database,
    settings: AppSettings,
    meta: Meta,
) -> ApiResponse[list[RecommendationCardSchema]]:
    await rate_limiter.check("recommendations_generate", str(principal.user_id), 15, 60)
    service = HybridRecommendationService(session=db, settings=settings)
    cards = await service.generate_recommendations(user_id=principal.user_id, payload=payload)
    return ApiResponse(data=cards, meta=meta)


@router.get("/today", response_model=ApiResponse[list[RecommendationCardSchema]])
async def get_today_recommendations(
    principal: Principal,
    db: Database,
    settings: AppSettings,
    meta: Meta,
) -> ApiResponse[list[RecommendationCardSchema]]:
    service = HybridRecommendationService(session=db, settings=settings)
    cards = await service.get_today_recommendations(user_id=principal.user_id)
    return ApiResponse(data=cards, meta=meta)


@router.post(
    "/{recommendation_id}/feedback",
    response_model=ApiResponse[RecommendationFeedbackSchema],
    dependencies=[Depends(enforce_csrf_protection)],
)
async def record_recommendation_feedback(
    recommendation_id: uuid.UUID,
    payload: RecommendationFeedbackRequest,
    principal: Principal,
    db: Database,
    settings: AppSettings,
    meta: Meta,
) -> ApiResponse[RecommendationFeedbackSchema]:
    service = HybridRecommendationService(session=db, settings=settings)
    feedback = await service.submit_feedback(
        user_id=principal.user_id,
        recommendation_id=recommendation_id,
        payload=payload,
    )
    return ApiResponse(data=feedback, meta=meta)
