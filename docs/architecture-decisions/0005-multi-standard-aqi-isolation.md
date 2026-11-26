# ADR 0005: Strict Multi-Standard AQI Isolation (`us_epa` vs `india_naqi`)

- **Status:** Accepted
- **Date:** 2026-11-19

## Context
Different countries and providers use fundamentally different Air Quality Index scales. For example, a 24-hour `PM2.5` reading of `90 µg/m³` maps to **200 (Moderate)** on the India National AQI scale (`61–90 µg/m³ -> 101–200`), whereas on the US EPA scale (`2024 PM2.5 breakpoints`), `90 µg/m³` maps to **~174 (Unhealthy)**. Mixing category names, color bands, or breakpoints across standards misleads families about exposure risk.

## Decision
Store raw normalized pollutant concentrations (`pm25`, `pm10`, `no2`, `so2`, `co`, `o3` with units and averaging periods) independently from AQI indices, and compute/serve AQI through isolated standard-specific calculators (`AQIStandard.US_EPA` and `AQIStandard.INDIA_NAQI`). Every API response, alert rule, and UI component must carry an explicit `standard` identifier, and return `unavailable` if the standard's scientific preconditions are not met.

## Consequences
- **Positive:** Scientifically accurate reporting for both Indian cities (NAQI default) and global comparisons (US EPA); users can switch standards transparently without corrupting underlying station data.
- **Requirement:** Frontend AQI color tokens and category labels are keyed by `(standard, category_code)` and never hardcoded to a single scale.
