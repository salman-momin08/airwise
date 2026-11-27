"""Deterministic India NAQI (CPCB) and US EPA (2024 PM2.5) piecewise-linear AQI calculators."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum


class AQIStandard(StrEnum):
    US_EPA = "us_epa"
    INDIA_NAQI = "india_naqi"


class PollutantCode(StrEnum):
    PM25 = "pm25"
    PM10 = "pm10"
    NO2 = "no2"
    SO2 = "so2"
    CO = "co"
    O3 = "o3"


@dataclass(frozen=True)
class BreakpointBand:
    bp_low: float
    bp_high: float
    index_low: int
    index_high: int
    category: str


@dataclass(frozen=True)
class SubIndexResult:
    pollutant: PollutantCode
    sub_index: int
    category: str
    truncated_concentration: float
    unit: str


@dataclass(frozen=True)
class AQICalculationResult:
    standard: AQIStandard
    status: str  # "available" | "unavailable"
    aqi: int | None
    category: str | None
    dominant_pollutant: PollutantCode | None
    sub_indices: dict[PollutantCode, SubIndexResult]
    unavailable_reason: str | None = None


# India National AQI (CPCB) breakpoints:
# 24-hr for PM2.5, PM10, NO2, SO2 (ug/m3); 8-hr for CO (mg/m3), O3 (ug/m3)
INDIA_NAQI_BREAKPOINTS: dict[PollutantCode, tuple[str, tuple[BreakpointBand, ...]]] = {
    PollutantCode.PM25: (
        "ug/m3",
        (
            BreakpointBand(0, 30, 0, 50, "Good"),
            BreakpointBand(31, 60, 51, 100, "Satisfactory"),
            BreakpointBand(61, 90, 101, 200, "Moderate"),
            BreakpointBand(91, 120, 201, 300, "Poor"),
            BreakpointBand(121, 250, 301, 400, "Very Poor"),
            BreakpointBand(251, 380, 401, 500, "Severe"),
        ),
    ),
    PollutantCode.PM10: (
        "ug/m3",
        (
            BreakpointBand(0, 50, 0, 50, "Good"),
            BreakpointBand(51, 100, 51, 100, "Satisfactory"),
            BreakpointBand(101, 250, 101, 200, "Moderate"),
            BreakpointBand(251, 350, 201, 300, "Poor"),
            BreakpointBand(351, 430, 301, 400, "Very Poor"),
            BreakpointBand(431, 510, 401, 500, "Severe"),
        ),
    ),
    PollutantCode.NO2: (
        "ug/m3",
        (
            BreakpointBand(0, 40, 0, 50, "Good"),
            BreakpointBand(41, 80, 51, 100, "Satisfactory"),
            BreakpointBand(81, 180, 101, 200, "Moderate"),
            BreakpointBand(181, 280, 201, 300, "Poor"),
            BreakpointBand(281, 400, 301, 400, "Very Poor"),
            BreakpointBand(401, 520, 401, 500, "Severe"),
        ),
    ),
    PollutantCode.SO2: (
        "ug/m3",
        (
            BreakpointBand(0, 40, 0, 50, "Good"),
            BreakpointBand(41, 80, 51, 100, "Satisfactory"),
            BreakpointBand(81, 380, 101, 200, "Moderate"),
            BreakpointBand(381, 800, 201, 300, "Poor"),
            BreakpointBand(801, 1600, 301, 400, "Very Poor"),
            BreakpointBand(1601, 2400, 401, 500, "Severe"),
        ),
    ),
    PollutantCode.CO: (
        "mg/m3",
        (
            BreakpointBand(0.0, 1.0, 0, 50, "Good"),
            BreakpointBand(1.1, 2.0, 51, 100, "Satisfactory"),
            BreakpointBand(2.1, 10.0, 101, 200, "Moderate"),
            BreakpointBand(10.1, 17.0, 201, 300, "Poor"),
            BreakpointBand(17.1, 34.0, 301, 400, "Very Poor"),
            BreakpointBand(34.1, 51.0, 401, 500, "Severe"),
        ),
    ),
    PollutantCode.O3: (
        "ug/m3",
        (
            BreakpointBand(0, 50, 0, 50, "Good"),
            BreakpointBand(51, 100, 51, 100, "Satisfactory"),
            BreakpointBand(101, 168, 101, 200, "Moderate"),
            BreakpointBand(169, 208, 201, 300, "Poor"),
            BreakpointBand(209, 748, 301, 400, "Very Poor"),
            BreakpointBand(749, 1000, 401, 500, "Severe"),
        ),
    ),
}

# US EPA AQI (2024 Revised PM2.5 Breakpoints; canonical EPA units per pollutant)
US_EPA_BREAKPOINTS: dict[PollutantCode, tuple[str, int, tuple[BreakpointBand, ...]]] = {
    PollutantCode.PM25: (
        "ug/m3",
        1,
        (
            BreakpointBand(0.0, 9.0, 0, 50, "Good"),
            BreakpointBand(9.1, 35.4, 51, 100, "Moderate"),
            BreakpointBand(35.5, 55.4, 101, 150, "Unhealthy for Sensitive Groups"),
            BreakpointBand(55.5, 125.4, 151, 200, "Unhealthy"),
            BreakpointBand(125.5, 225.4, 201, 300, "Very Unhealthy"),
            BreakpointBand(225.5, 325.4, 301, 500, "Hazardous"),
        ),
    ),
    PollutantCode.PM10: (
        "ug/m3",
        0,
        (
            BreakpointBand(0, 54, 0, 50, "Good"),
            BreakpointBand(55, 154, 51, 100, "Moderate"),
            BreakpointBand(155, 254, 101, 150, "Unhealthy for Sensitive Groups"),
            BreakpointBand(255, 354, 151, 200, "Unhealthy"),
            BreakpointBand(355, 424, 201, 300, "Very Unhealthy"),
            BreakpointBand(425, 604, 301, 500, "Hazardous"),
        ),
    ),
    PollutantCode.O3: (
        "ppm",
        3,
        (
            BreakpointBand(0.000, 0.054, 0, 50, "Good"),
            BreakpointBand(0.055, 0.070, 51, 100, "Moderate"),
            BreakpointBand(0.071, 0.085, 101, 150, "Unhealthy for Sensitive Groups"),
            BreakpointBand(0.086, 0.105, 151, 200, "Unhealthy"),
            BreakpointBand(0.106, 0.200, 201, 300, "Very Unhealthy"),
            BreakpointBand(0.201, 0.604, 301, 500, "Hazardous"),
        ),
    ),
    PollutantCode.CO: (
        "ppm",
        1,
        (
            BreakpointBand(0.0, 4.4, 0, 50, "Good"),
            BreakpointBand(4.5, 9.4, 51, 100, "Moderate"),
            BreakpointBand(9.5, 12.4, 101, 150, "Unhealthy for Sensitive Groups"),
            BreakpointBand(12.5, 15.4, 151, 200, "Unhealthy"),
            BreakpointBand(15.5, 30.4, 201, 300, "Very Unhealthy"),
            BreakpointBand(30.5, 50.4, 301, 500, "Hazardous"),
        ),
    ),
    PollutantCode.SO2: (
        "ppb",
        0,
        (
            BreakpointBand(0, 35, 0, 50, "Good"),
            BreakpointBand(36, 75, 51, 100, "Moderate"),
            BreakpointBand(76, 185, 101, 150, "Unhealthy for Sensitive Groups"),
            BreakpointBand(186, 304, 151, 200, "Unhealthy"),
            BreakpointBand(305, 604, 201, 300, "Very Unhealthy"),
            BreakpointBand(605, 1004, 301, 500, "Hazardous"),
        ),
    ),
    PollutantCode.NO2: (
        "ppb",
        0,
        (
            BreakpointBand(0, 53, 0, 50, "Good"),
            BreakpointBand(54, 100, 51, 100, "Moderate"),
            BreakpointBand(101, 360, 101, 150, "Unhealthy for Sensitive Groups"),
            BreakpointBand(361, 649, 151, 200, "Unhealthy"),
            BreakpointBand(650, 1249, 201, 300, "Very Unhealthy"),
            BreakpointBand(1250, 2049, 301, 500, "Hazardous"),
        ),
    ),
}

# Standard reference conditions for gaseous unit conversions: 25°C (298.15 K), 1 atm -> 24.45 L/mol
MOLAR_VOLUME_25C_1ATM = 24.45
MOLECULAR_WEIGHTS_G_MOL: dict[PollutantCode, float] = {
    PollutantCode.NO2: 46.0055,
    PollutantCode.SO2: 64.066,
    PollutantCode.CO: 28.01,
    PollutantCode.O3: 48.00,
}


def _convert_to_india_naqi_gas_unit(
    pollutant: PollutantCode, concentration: float, normalized_unit: str, mw: float
) -> tuple[float, str] | None:
    if pollutant == PollutantCode.CO:
        co_factors: dict[str, float] = {
            "mg/m3": 1.0,
            "ug/m3": 1e-3,
            "ppm": mw / MOLAR_VOLUME_25C_1ATM,
            "ppb": mw / (MOLAR_VOLUME_25C_1ATM * 1000.0),
        }
        factor = co_factors.get(normalized_unit)
        return (concentration * factor, "mg/m3") if factor is not None else None

    ug_factors: dict[str, float] = {
        "ug/m3": 1.0,
        "ppb": mw / MOLAR_VOLUME_25C_1ATM,
        "ppm": (1000.0 * mw) / MOLAR_VOLUME_25C_1ATM,
    }
    factor = ug_factors.get(normalized_unit)
    return (concentration * factor, "ug/m3") if factor is not None else None


def _convert_to_us_epa_gas_unit(
    pollutant: PollutantCode, concentration: float, normalized_unit: str, mw: float
) -> tuple[float, str] | None:
    if pollutant in {PollutantCode.O3, PollutantCode.CO}:
        ppm_factors: dict[str, float] = {
            "ppm": 1.0,
            "ppb": 1e-3,
            "mg/m3": MOLAR_VOLUME_25C_1ATM / mw,
            "ug/m3": MOLAR_VOLUME_25C_1ATM / (mw * 1000.0),
        }
        factor = ppm_factors.get(normalized_unit)
        return (concentration * factor, "ppm") if factor is not None else None

    ppb_factors: dict[str, float] = {
        "ppb": 1.0,
        "ppm": 1000.0,
        "ug/m3": MOLAR_VOLUME_25C_1ATM / mw,
    }
    factor = ppb_factors.get(normalized_unit)
    return (concentration * factor, "ppb") if factor is not None else None


def convert_gas_unit_for_standard(
    pollutant: PollutantCode,
    concentration: float,
    unit: str,
    standard: AQIStandard,
) -> tuple[float, str] | None:
    """Explicitly convert gaseous pollutant units using 25°C, 1 atm molar volume (24.45 L/mol).

    Particulate matter (PM2.5, PM10) cannot be converted between mass and mixing ratios;
    returns None if units are incompatible.
    """
    normalized_unit = unit.strip().lower().replace("µg/m³", "ug/m3").replace("µg/m3", "ug/m3")
    if pollutant in {PollutantCode.PM25, PollutantCode.PM10}:
        return (concentration, "ug/m3") if normalized_unit == "ug/m3" else None

    mw = MOLECULAR_WEIGHTS_G_MOL.get(pollutant)
    if mw is None:
        return None
    if standard == AQIStandard.INDIA_NAQI:
        return _convert_to_india_naqi_gas_unit(pollutant, concentration, normalized_unit, mw)
    return _convert_to_us_epa_gas_unit(pollutant, concentration, normalized_unit, mw)


def _truncate_decimals(value: float, decimals: int) -> float:
    if decimals <= 0:
        return float(math.floor(value))
    factor = float(10**decimals)
    return float(math.floor(value * factor + 1e-9) / factor)


def _interpolate_band(conc: float, bands: tuple[BreakpointBand, ...]) -> tuple[int, str]:
    for band in bands:
        if band.bp_low <= conc <= band.bp_high:
            raw = (band.index_high - band.index_low) / (band.bp_high - band.bp_low) * (
                conc - band.bp_low
            ) + band.index_low
            return round(raw), band.category
    if conc > bands[-1].bp_high:
        return bands[-1].index_high, bands[-1].category
    return bands[0].index_low, bands[0].category


def _compute_india_naqi_sub_indices(
    measurements: dict[PollutantCode, tuple[float, str]],
) -> dict[PollutantCode, SubIndexResult]:
    sub_indices: dict[PollutantCode, SubIndexResult] = {}
    for pollutant, (value, unit) in measurements.items():
        if value < 0 or pollutant not in INDIA_NAQI_BREAKPOINTS:
            continue
        expected_unit, bands = INDIA_NAQI_BREAKPOINTS[pollutant]
        if unit != expected_unit:
            continue
        decimals = 1 if pollutant == PollutantCode.CO else 0
        truncated = round(value, decimals) if decimals == 1 else float(round(value))
        idx, cat = _interpolate_band(truncated, bands)
        sub_indices[pollutant] = SubIndexResult(
            pollutant=pollutant,
            sub_index=idx,
            category=cat,
            truncated_concentration=truncated,
            unit=unit,
        )
    return sub_indices


def _compute_us_epa_sub_indices(
    measurements: dict[PollutantCode, tuple[float, str]],
) -> dict[PollutantCode, SubIndexResult]:
    sub_indices: dict[PollutantCode, SubIndexResult] = {}
    for pollutant, (value, unit) in measurements.items():
        if value < 0 or pollutant not in US_EPA_BREAKPOINTS:
            continue
        expected_unit, decimals, bands = US_EPA_BREAKPOINTS[pollutant]
        if unit != expected_unit:
            continue
        truncated = _truncate_decimals(value, decimals)
        idx, cat = _interpolate_band(truncated, bands)
        sub_indices[pollutant] = SubIndexResult(
            pollutant=pollutant,
            sub_index=idx,
            category=cat,
            truncated_concentration=truncated,
            unit=unit,
        )
    return sub_indices


def calculate_aqi(
    standard: AQIStandard,
    measurements: dict[PollutantCode, tuple[float, str]],
) -> AQICalculationResult:
    """Calculate AQI strictly isolated to the requested standard.

    `measurements` maps PollutantCode -> (concentration, unit).
    Never mixes breakpoints or units across standards.
    """
    if standard == AQIStandard.INDIA_NAQI:
        sub_indices = _compute_india_naqi_sub_indices(measurements)
        has_pm = PollutantCode.PM25 in sub_indices or PollutantCode.PM10 in sub_indices
        if len(sub_indices) < 3 or not has_pm:
            return AQICalculationResult(
                standard=standard,
                status="unavailable",
                aqi=None,
                category=None,
                dominant_pollutant=None,
                sub_indices=sub_indices,
                unavailable_reason=(
                    "Official India NAQI requires at least 3 valid pollutants in canonical units, "
                    "including PM2.5 or PM10."
                ),
            )
    else:
        sub_indices = _compute_us_epa_sub_indices(measurements)
        if not sub_indices:
            return AQICalculationResult(
                standard=standard,
                status="unavailable",
                aqi=None,
                category=None,
                dominant_pollutant=None,
                sub_indices={},
                unavailable_reason="No valid US EPA pollutant concentrations were available.",
            )

    dominant = max(sub_indices.values(), key=lambda item: item.sub_index)
    return AQICalculationResult(
        standard=standard,
        status="available",
        aqi=dominant.sub_index,
        category=dominant.category,
        dominant_pollutant=dominant.pollutant,
        sub_indices=sub_indices,
    )
