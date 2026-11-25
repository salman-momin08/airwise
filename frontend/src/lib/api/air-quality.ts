import { apiRequest } from "@/lib/api/client";
import type {
  AirQualityForecast,
  AQIStandard,
  CurrentAirQuality,
  CurrentWeather,
  HistoricalAirQuality,
  HistoryPeriod,
  MonitoringStation,
  StationGeoJsonCollection,
} from "@/types/api";

export const airQualityApi = {
  getCurrent: (city: string, standard: AQIStandard) =>
    apiRequest<CurrentAirQuality>(
      `/air-quality/current?city=${encodeURIComponent(city)}&standard=${encodeURIComponent(standard)}`,
    ),

  getHistory: (city: string, standard: AQIStandard, period: HistoryPeriod) =>
    apiRequest<HistoricalAirQuality>(
      `/air-quality/history?city=${encodeURIComponent(city)}&standard=${encodeURIComponent(standard)}&period=${encodeURIComponent(period)}`,
    ),

  getForecast: (city: string, standard: AQIStandard, hours = 24) =>
    apiRequest<AirQualityForecast>(
      `/air-quality/forecast?city=${encodeURIComponent(city)}&standard=${encodeURIComponent(standard)}&hours=${hours}`,
    ),

  getStations: (city: string, standard: AQIStandard, radiusKm = 30) =>
    apiRequest<MonitoringStation[]>(
      `/air-quality/stations?city=${encodeURIComponent(city)}&standard=${encodeURIComponent(standard)}&radius_km=${radiusKm}`,
    ),

  getMapGeoJson: (city: string, standard: AQIStandard) =>
    apiRequest<StationGeoJsonCollection>(
      `/air-quality/map?city=${encodeURIComponent(city)}&standard=${encodeURIComponent(standard)}`,
    ),

  getCurrentWeather: (city: string) =>
    apiRequest<CurrentWeather>(`/weather/current?city=${encodeURIComponent(city)}`),
};
