"use client";

/**
 * Interactive MapLibre station map paired with an accessible keyboard-navigable station list.
 */

import { useEffect, useRef, useState } from "react";
import "maplibre-gl/dist/maplibre-gl.css";
import { AQIBadge } from "@/components/air-quality/aqi-badge";
import type { MonitoringStation } from "@/types/api";

interface StationsMapPanelProps {
  stations: MonitoringStation[];
  isLoading: boolean;
  isError: boolean;
}

export function StationsMapPanel({
  stations,
  isLoading,
  isError,
}: StationsMapPanelProps) {
  const mapContainerRef = useRef<HTMLDivElement | null>(null);
  const [mapSupported, setMapSupported] = useState<boolean>(true);

  useEffect(() => {
    const container = mapContainerRef.current;
    const primaryStation = stations[0];
    if (!container || !primaryStation) return;

    let cancelled = false;
    let cleanupMap: (() => void) | undefined;

    import("maplibre-gl")
      .then((maplibre) => {
        if (cancelled || !mapContainerRef.current) return;
        try {
          const map = new maplibre.Map({
            container: mapContainerRef.current,
            style: {
              version: 8,
              sources: {
                osm: {
                  type: "raster",
                  tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
                  tileSize: 256,
                  attribution: "© OpenStreetMap contributors",
                },
              },
              layers: [
                {
                  id: "osm-tiles",
                  type: "raster",
                  source: "osm",
                },
              ],
            },
            center: [primaryStation.longitude, primaryStation.latitude],
            zoom: 10.5,
          });

          for (const st of stations) {
            const el = document.createElement("div");
            el.className =
              "rounded-full border-2 border-white bg-brand-primary px-2 py-0.5 text-xs font-bold text-white dark:text-background shadow";
            el.textContent = st.aqi !== null ? `${st.aqi}` : "N/A";
            el.setAttribute(
              "aria-label",
              `${st.name}: AQI ${st.aqi ?? "Unavailable"} (${st.category ?? "Unavailable"})`,
            );

            new maplibre.Marker({ element: el })
              .setLngLat([st.longitude, st.latitude])
              .setPopup(
                new maplibre.Popup({ offset: 16 }).setText(
                  `${st.name} — AQI ${st.aqi ?? "Unavailable"} (${st.category ?? "Unavailable"})`,
                ),
              )
              .addTo(map);
          }

          cleanupMap = () => map.remove();
        } catch {
          setMapSupported(false);
        }
      })
      .catch(() => {
        if (!cancelled) setMapSupported(false);
      });

    return () => {
      cancelled = true;
      if (cleanupMap) cleanupMap();
    };
  }, [stations]);

  if (isLoading) {
    return (
      <div
        aria-busy="true"
        className="h-72 animate-pulse rounded-card border border-border bg-surface p-6"
      />
    );
  }

  if (isError) {
    return (
      <section className="rounded-card border border-border bg-surface p-6 text-sm text-text-secondary">
        <h2 className="text-lg font-semibold text-text-primary">Monitoring Stations</h2>
        <p className="mt-2">Nearby monitoring stations could not be loaded right now.</p>
      </section>
    );
  }

  return (
    <section className="rounded-card border border-border bg-surface p-6 shadow-sm">
      <h2 className="text-lg font-semibold text-text-primary">
        Nearby Monitoring Stations &amp; Spatial Layer
      </h2>
      <p className="mt-1 text-xs text-text-secondary">
        Ground stations and modeled grid nodes are explicitly distinguished so regional estimates
        are never mistaken for street-level sensors.
      </p>

      {stations.length === 0 ? (
        <p className="mt-4 rounded-lg border border-dashed border-border p-5 text-sm text-text-secondary">
          No active monitoring stations found within radius.
        </p>
      ) : (
        <div className="mt-4 grid gap-6 lg:grid-cols-2">
          {mapSupported ? (
            <div
              ref={mapContainerRef}
              aria-label="Interactive monitoring station map"
              className="h-72 w-full overflow-hidden rounded-card border border-border bg-background"
            />
          ) : (
            <div className="flex h-72 items-center justify-center rounded-card border border-dashed border-border bg-background p-6 text-center text-xs text-text-secondary">
              Interactive WebGL map canvas is unavailable on this device. Full accessible station
              telemetry is listed alongside.
            </div>
          )}

          <ul className="space-y-3" aria-label="Monitoring stations list">
            {stations.map((st) => (
              <li
                key={st.station_id}
                className="rounded-card border border-border bg-background p-4"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <h3 className="text-sm font-semibold text-text-primary">{st.name}</h3>
                    <p className="text-xs text-text-secondary">
                      {st.source_type === "station" ? "Ground Station" : "Modeled Grid"} ·{" "}
                      {st.distance_km !== null ? `${st.distance_km} km from center · ` : ""}
                      ({st.latitude.toFixed(3)}, {st.longitude.toFixed(3)})
                    </p>
                  </div>
                  <AQIBadge
                    standard={st.standard}
                    aqi={st.aqi}
                    category={st.category}
                  />
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
