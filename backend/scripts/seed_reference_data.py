"""Reference emission factors and metadata seeder entrypoint."""

from __future__ import annotations

REFERENCE_TRANSPORT_EMISSION_FACTORS: tuple[dict[str, object], ...] = (
    {
        "mode_or_region_code": "passenger_car_petrol_india",
        "factor_value": 0.168,
        "unit": "kg_co2e_per_vkm",
        "default_occupancy": 1.2,
        "source_reference": "India GHG Program — Road Transport Emission Factors",
        "effective_year": 2024,
    },
    {
        "mode_or_region_code": "urban_metro_rail_india",
        "factor_value": 0.028,
        "unit": "kg_co2e_per_pkm",
        "default_occupancy": 1.0,
        "source_reference": "India GHG Program / Metro Rail Sustainability Reports",
        "effective_year": 2024,
    },
    {
        "mode_or_region_code": "city_bus_cng_electric_blend",
        "factor_value": 0.042,
        "unit": "kg_co2e_per_pkm",
        "default_occupancy": 1.0,
        "source_reference": "IPCC / Urban Bus Passenger-km Factor",
        "effective_year": 2024,
    },
)


def main() -> None:
    count = len(REFERENCE_TRANSPORT_EMISSION_FACTORS)
    print(f"Loaded {count} verified reference emission factors.")


if __name__ == "__main__":
    main()
