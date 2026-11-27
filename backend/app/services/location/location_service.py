from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import AirWiseError, ResourceNotFoundError
from app.core.security import hash_ip_address
from app.repositories.identity_repository import IdentityRepository
from app.schemas.identity import (
    GazetteerLocationMatch,
    SavedLocationCreateRequest,
    SavedLocationData,
    SavedLocationUpdateRequest,
)
from app.services.auth.user_service import serialize_saved_location

MAX_SAVED_LOCATIONS_PER_USER = 10

SUPPORTED_GAZETTEER: tuple[GazetteerLocationMatch, ...] = (
    GazetteerLocationMatch(
        city="Delhi",
        state_region="NCT of Delhi",
        country_code="IN",
        postal_prefix="110",
        timezone="Asia/Kolkata",
    ),
    GazetteerLocationMatch(
        city="Gurugram",
        state_region="Haryana",
        country_code="IN",
        postal_prefix="122",
        timezone="Asia/Kolkata",
    ),
    GazetteerLocationMatch(
        city="Noida",
        state_region="Uttar Pradesh",
        country_code="IN",
        postal_prefix="201",
        timezone="Asia/Kolkata",
    ),
    GazetteerLocationMatch(
        city="Bengaluru",
        state_region="Karnataka",
        country_code="IN",
        postal_prefix="560",
        timezone="Asia/Kolkata",
    ),
    GazetteerLocationMatch(
        city="Mumbai",
        state_region="Maharashtra",
        country_code="IN",
        postal_prefix="400",
        timezone="Asia/Kolkata",
    ),
    GazetteerLocationMatch(
        city="Chennai",
        state_region="Tamil Nadu",
        country_code="IN",
        postal_prefix="600",
        timezone="Asia/Kolkata",
    ),
    GazetteerLocationMatch(
        city="Kolkata",
        state_region="West Bengal",
        country_code="IN",
        postal_prefix="700",
        timezone="Asia/Kolkata",
    ),
    GazetteerLocationMatch(
        city="Hyderabad",
        state_region="Telangana",
        country_code="IN",
        postal_prefix="500",
        timezone="Asia/Kolkata",
    ),
    GazetteerLocationMatch(
        city="Pune",
        state_region="Maharashtra",
        country_code="IN",
        postal_prefix="411",
        timezone="Asia/Kolkata",
    ),
    GazetteerLocationMatch(
        city="Lucknow",
        state_region="Uttar Pradesh",
        country_code="IN",
        postal_prefix="226",
        timezone="Asia/Kolkata",
    ),
)

def search_gazetteer(query: str) -> list[GazetteerLocationMatch]:
    needle = query.strip().lower()
    if not needle:
        return []
    return [
        entry
        for entry in SUPPORTED_GAZETTEER
        if needle in entry.city.lower()
        or needle in entry.state_region.lower()
        or entry.postal_prefix.startswith(needle[:3])
        or needle.startswith(entry.postal_prefix)
    ]

class LocationService:
    """Service enforcing coarse-by-default location precision and user ownership."""

    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._repo = IdentityRepository(session)
        self._settings = settings

    async def list_locations(self, *, user_id: uuid.UUID) -> list[SavedLocationData]:
        records = await self._repo.list_saved_locations(user_id=user_id)
        return [serialize_saved_location(row) for row in records]

    async def create_location(
        self,
        *,
        user_id: uuid.UUID,
        payload: SavedLocationCreateRequest,
        client_ip: str | None,
    ) -> SavedLocationData:
        existing = await self._repo.list_saved_locations(user_id=user_id)
        if len(existing) >= MAX_SAVED_LOCATIONS_PER_USER:
            raise AirWiseError(
                code="SAVED_LOCATION_LIMIT_REACHED",
                message=f"You can save up to {MAX_SAVED_LOCATIONS_PER_USER} locations.",
                status_code=400,
            )

        make_primary = payload.is_primary or len(existing) == 0
        if make_primary:
            await self._repo.clear_primary_locations_for_user(user_id=user_id)

        record = await self._repo.create_saved_location(
            user_id=user_id,
            label=payload.label,
            display_name=payload.display_name.strip(),
            city=payload.city.strip(),
            state_region=payload.state_region.strip() if payload.state_region else None,
            country_code=payload.country_code,
            postal_code=payload.postal_code.strip() if payload.postal_code else None,
            latitude=payload.latitude,
            longitude=payload.longitude,
            location_precision=payload.location_precision,
            timezone=payload.timezone,
            is_primary=make_primary,
        )
        await self._repo.append_audit_log(
            actor_user_id=user_id,
            action="location.created",
            target_type="saved_location",
            target_id=str(record.id),
            metadata_redacted={
                "label": payload.label,
                "location_precision": payload.location_precision,
            },
            ip_hash=hash_ip_address(client_ip, self._settings.auth_secret_key),
        )
        await self._session.commit()
        return serialize_saved_location(record)

    async def update_location(
        self,
        *,
        user_id: uuid.UUID,
        location_id: uuid.UUID,
        payload: SavedLocationUpdateRequest,
        client_ip: str | None,
    ) -> SavedLocationData:
        record = await self._repo.get_saved_location_for_user(
            user_id=user_id, location_id=location_id
        )
        if record is None:
            raise ResourceNotFoundError("Saved location not found.")

        updates = payload.model_dump(exclude_unset=True)
        if updates.get("is_primary") is True:
            await self._repo.clear_primary_locations_for_user(user_id=user_id)
            record.is_primary = True
        elif updates.get("is_primary") is False:
            record.is_primary = False

        for attr in (
            "label",
            "display_name",
            "city",
            "state_region",
            "country_code",
            "postal_code",
            "location_precision",
            "timezone",
        ):
            if attr in updates and updates[attr] is not None:
                val = updates[attr]
                setattr(record, attr, val.strip() if isinstance(val, str) else val)
            elif attr in {"state_region", "postal_code"} and attr in updates:
                setattr(record, attr, None)

        new_precision = record.location_precision
        if new_precision == "city":
            self._repo.update_saved_location_coordinates(
                record, latitude=None, longitude=None
            )
        elif "latitude" in updates and "longitude" in updates:
            self._repo.update_saved_location_coordinates(
                record,
                latitude=updates["latitude"],
                longitude=updates["longitude"],
            )

        if record.location_precision == "exact" and (
            record.latitude is None or record.longitude is None
        ):
            raise AirWiseError(
                code="VALIDATION_ERROR",
                message="Exact location precision requires consented latitude and longitude.",
                status_code=422,
            )

        await self._repo.append_audit_log(
            actor_user_id=user_id,
            action="location.updated",
            target_type="saved_location",
            target_id=str(record.id),
            metadata_redacted={"location_precision": record.location_precision},
            ip_hash=hash_ip_address(client_ip, self._settings.auth_secret_key),
        )
        await self._session.commit()
        return serialize_saved_location(record)

    async def delete_location(
        self,
        *,
        user_id: uuid.UUID,
        location_id: uuid.UUID,
        client_ip: str | None,
    ) -> None:
        record = await self._repo.get_saved_location_for_user(
            user_id=user_id, location_id=location_id
        )
        if record is None:
            raise ResourceNotFoundError("Saved location not found.")

        was_primary = record.is_primary
        await self._repo.delete_saved_location(record)
        await self._session.flush()

        if was_primary:
            remaining = await self._repo.list_saved_locations(user_id=user_id)
            if remaining:
                remaining[0].is_primary = True

        await self._repo.append_audit_log(
            actor_user_id=user_id,
            action="location.deleted",
            target_type="saved_location",
            target_id=str(location_id),
            metadata_redacted={},
            ip_hash=hash_ip_address(client_ip, self._settings.auth_secret_key),
        )
        await self._session.commit()
