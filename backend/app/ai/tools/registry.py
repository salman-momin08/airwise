from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

class ToolAuthScope(StrEnum):
    PUBLIC_OR_USER = "public_or_user"
    AUTHENTICATED_SELF = "authenticated_self"

@dataclass(frozen=True)
class AllowlistedToolSpec:
    name: str
    description: str
    auth_scope: ToolAuthScope
    requires_preference_consent: bool = False

ALLOWLISTED_AI_TOOLS: tuple[AllowlistedToolSpec, ...] = (
    AllowlistedToolSpec(
        name="get_current_air_quality",
        description=(
            "Retrieve verified current pollutant concentrations and standard-isolated AQI "
            "for a city or saved location."
        ),
        auth_scope=ToolAuthScope.PUBLIC_OR_USER,
    ),
    AllowlistedToolSpec(
        name="get_air_quality_forecast",
        description="Retrieve hourly/daily air quality forecast and confidence metadata.",
        auth_scope=ToolAuthScope.PUBLIC_OR_USER,
    ),
    AllowlistedToolSpec(
        name="get_historical_air_quality",
        description="Retrieve verified 24h, 7d, or 30d historical pollutant trends.",
        auth_scope=ToolAuthScope.PUBLIC_OR_USER,
    ),
    AllowlistedToolSpec(
        name="get_weather_conditions",
        description=(
            "Retrieve temperature, humidity, wind speed, and atmospheric dispersion context."
        ),
        auth_scope=ToolAuthScope.PUBLIC_OR_USER,
    ),
    AllowlistedToolSpec(
        name="get_user_preferences",
        description=(
            "Retrieve consented household, schedule, commute, and purifier preferences "
            "for the active user."
        ),
        auth_scope=ToolAuthScope.AUTHENTICATED_SELF,
        requires_preference_consent=True,
    ),
    AllowlistedToolSpec(
        name="get_saved_locations",
        description="Retrieve coarse metadata for locations saved by the authenticated user.",
        auth_scope=ToolAuthScope.AUTHENTICATED_SELF,
    ),
    AllowlistedToolSpec(
        name="retrieve_environmental_guidelines",
        description=(
            "Run hybrid pgvector + lexical RAG search over curated WHO, EPA, and "
            "public-health guidance."
        ),
        auth_scope=ToolAuthScope.PUBLIC_OR_USER,
    ),
    AllowlistedToolSpec(
        name="calculate_transport_emissions",
        description="Invoke the deterministic passenger-km CO2e transport calculator.",
        auth_scope=ToolAuthScope.PUBLIC_OR_USER,
    ),
    AllowlistedToolSpec(
        name="estimate_exposure_change",
        description="Invoke the deterministic relative exposure comparison calculator.",
        auth_scope=ToolAuthScope.PUBLIC_OR_USER,
    ),
    AllowlistedToolSpec(
        name="compare_daily_routines",
        description=(
            "Compare exposure and schedule trade-offs across candidate routine time blocks."
        ),
        auth_scope=ToolAuthScope.AUTHENTICATED_SELF,
    ),
    AllowlistedToolSpec(
        name="generate_sustainable_alternatives",
        description=(
            "Retrieve exposure-screened lower-emission mobility and household alternatives."
        ),
        auth_scope=ToolAuthScope.PUBLIC_OR_USER,
    ),
    AllowlistedToolSpec(
        name="get_community_initiatives",
        description="List active neighborhood clean-air challenges and aggregate participation.",
        auth_scope=ToolAuthScope.PUBLIC_OR_USER,
    ),
)

ALLOWLISTED_TOOL_NAMES: frozenset[str] = frozenset(tool.name for tool in ALLOWLISTED_AI_TOOLS)
MAX_TOOL_CALL_DEPTH: int = 4
