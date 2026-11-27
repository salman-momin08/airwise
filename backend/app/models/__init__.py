"""SQLAlchemy 2.x ORM model registry imported by Alembic migrations and repositories."""

from __future__ import annotations

from app.models.assistant import (
    AIGenerationMetadata,
    ChatConversation,
    ChatMessage,
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeIngestionJob,
)
from app.models.community_alerts import (
    AlertRule,
    Community,
    CommunityAbuseReport,
    CommunityInitiative,
    CommunityMember,
    CommunityParticipation,
    Notification,
    NotificationDelivery,
)
from app.models.identity import (
    AuditLog,
    SavedLocation,
    SystemSetting,
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
    "AirQualityForecast",
    "AirQualityMeasurement",
    "AirQualitySource",
    "AirQualityStation",
    "AlertRule",
    "AuditLog",
    "ChatConversation",
    "ChatMessage",
    "Community",
    "CommunityAbuseReport",
    "CommunityInitiative",
    "CommunityMember",
    "CommunityParticipation",
    "DailyRoutine",
    "EmissionFactor",
    "ImpactEstimate",
    "KnowledgeChunk",
    "KnowledgeDocument",
    "KnowledgeIngestionJob",
    "Notification",
    "NotificationDelivery",
    "Recommendation",
    "RecommendationFeedback",
    "RoutineActivity",
    "SavedLocation",
    "SystemSetting",
    "User",
    "UserAction",
    "UserActionToken",
    "UserPreference",
    "UserProfile",
    "UserSession",
    "WeatherObservation",
]
