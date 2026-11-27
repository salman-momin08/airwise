/**
 * Lightweight Zustand store holding ephemeral active city and AQI standard selection.
 */

import { create } from "zustand";
import type { AQIStandard } from "@/types/api";

interface LocationUIState {
  selectedCity: string;
  aqiStandard: AQIStandard;
  setSelectedCity: (city: string) => void;
  setAqiStandard: (standard: AQIStandard) => void;
}

export const useLocationStore = create<LocationUIState>((set) => ({
  selectedCity: "Delhi",
  aqiStandard: "india_naqi",
  setSelectedCity: (selectedCity) => set({ selectedCity }),
  setAqiStandard: (aqiStandard) => set({ aqiStandard }),
}));
