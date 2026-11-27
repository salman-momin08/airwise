from __future__ import annotations

from datetime import UTC, datetime, time

import pytest
from pydantic import ValidationError

from app.schemas.community import CreateCommunityRequest, LogParticipationRequest
from app.services.alerts.alert_service import is_within_quiet_hours

def test_timezone_aware_quiet_hours_overnight_and_daytime_windows() -> None:
    # 20:00 UTC == 01:30 IST (+05:30) next day -> inside 22:00..07:00 IST overnight quiet hours
    assert (
        is_within_quiet_hours(
            utc_now=datetime(2026, 11, 26, 20, 0, tzinfo=UTC),
            timezone_name="Asia/Kolkata",
            quiet_start=time(22, 0),
            quiet_end=time(7, 0),
        )
        is True
    )

    # 01:30 UTC == 07:00 IST exact end boundary -> outside quiet hours
    assert (
        is_within_quiet_hours(
            utc_now=datetime(2026, 11, 26, 1, 30, tzinfo=UTC),
            timezone_name="Asia/Kolkata",
            quiet_start=time(22, 0),
            quiet_end=time(7, 0),
        )
        is False
    )

    # Same 20:00 UTC in America/New_York (15:00 EST) -> outside 22:00..07:00 EST
    assert (
        is_within_quiet_hours(
            utc_now=datetime(2026, 11, 26, 20, 0, tzinfo=UTC),
            timezone_name="America/New_York",
            quiet_start=time(22, 0),
            quiet_end=time(7, 0),
        )
        is False
    )

    # Daytime window 13:00..15:00 UTC
    assert (
        is_within_quiet_hours(
            utc_now=datetime(2026, 11, 26, 14, 15, tzinfo=UTC),
            timezone_name="UTC",
            quiet_start=time(13, 0),
            quiet_end=time(15, 0),
        )
        is True
    )

@pytest.mark.parametrize(
    "unsafe_text",
    [
        "Flat 402, Green Park Residency",
        "Apartment #12B near station",
        "28.6139, 77.2090",
        "Reach out at organizer@example.com",
        "Call +91 98765 43210",
    ],
)
def test_community_schemas_reject_exact_addresses_coordinates_and_pii(
    unsafe_text: str,
) -> None:
    with pytest.raises(ValidationError):
        CreateCommunityRequest(
            slug="clean-air-group",
            name="Clean Air Group",
            city="Delhi",
            coarse_boundary_label=unsafe_text,
            description="Neighborhood clean commute group.",
        )

    with pytest.raises(ValidationError):
        LogParticipationRequest(
            self_reported_actions_count=1,
            commute_distance_saved_km=5.0,
            note=unsafe_text,
        )

def test_community_schema_accepts_coarse_neighborhood_label() -> None:
    valid = CreateCommunityRequest(
        slug="south-delhi-metro-circle",
        name="South Delhi Metro Circle",
        city="Delhi",
        coarse_boundary_label="South Delhi · Yellow Line Corridor",
        description="Voluntary metro rail and school-gate no-idling challenge group.",
    )
    assert valid.coarse_boundary_label == "South Delhi · Yellow Line Corridor"
