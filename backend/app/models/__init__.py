from __future__ import annotations

from app.models.assistant import (
    AIGenerationMetadata,
    ChatConversation,
    ChatMessage,
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeIngestionJob,
)
from app.models.identity import (
    AuditLog,
    SavedLocation,
    User,
    UserActionToken,
    UserPreference,
    UserProfile,
    UserSession,
)
from app.models.planning import (
    DailyRoutine,
    EmissionFactor,
    ImpactEstimate,
    Recommendation,
    RecommendationFeedback,
    RoutineActivity,
    UserAction,
)
from app.models.telemetry import (
    AirQualityForecast,
    AirQualityMeasurement,
    AirQualitySource,
    AirQualityStation,
    WeatherObservation,
)

__all__ = [
    "AIGenerationMetadata",
    "ChatConversation",
    "ChatMessage",
    "KnowledgeChunk",
    "KnowledgeDocument",
    "KnowledgeIngestionJob",
    "AirQualityForecast",
    "AirQualityMeasurement",
    "AirQualitySource",
    "AirQualityStation",
    "AuditLog",
    "DailyRoutine",
    "EmissionFactor",
    "ImpactEstimate",
    "Recommendation",
    "RecommendationFeedback",
    "RoutineActivity",
    "SavedLocation",
    "User",
    "UserAction",
    "UserActionToken",
    "UserPreference",
    "UserProfile",
    "UserSession",
    "WeatherObservation",
]