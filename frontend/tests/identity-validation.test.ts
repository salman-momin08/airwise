import { describe, expect, it } from "vitest";
import {
  registerSchema,
  savedLocationCreateSchema,
} from "@/lib/validation/identity";

describe("Identity & Location Zod Schemas", () => {
  it("enforces password length and alphanumeric rules on registration", () => {
    const weak = registerSchema.safeParse({
      display_name: "Asha",
      email: "asha@example.com",
      password: "onlylettersnoangka",
      preferred_aqi_standard: "india_naqi",
      timezone: "Asia/Kolkata",
    });
    expect(weak.success).toBe(false);

    const strong = registerSchema.safeParse({
      display_name: "Asha Rao",
      email: "asha@example.com",
      password: "CleanAir2026Password",
      preferred_aqi_standard: "india_naqi",
      timezone: "Asia/Kolkata",
    });
    expect(strong.success).toBe(true);
  });

  it("allows coarse city locations without coordinates and requires coordinates for exact precision", () => {
    const cityOnly = savedLocationCreateSchema.safeParse({
      label: "home",
      display_name: "Home",
      city: "Delhi",
      state_region: "NCT of Delhi",
      country_code: "IN",
      postal_code: "",
      location_precision: "city",
      latitude: null,
      longitude: null,
      timezone: "Asia/Kolkata",
      is_primary: true,
    });
    expect(cityOnly.success).toBe(true);

    const exactMissingCoords = savedLocationCreateSchema.safeParse({
      label: "home",
      display_name: "Home",
      city: "Delhi",
      state_region: "NCT of Delhi",
      country_code: "IN",
      postal_code: "",
      location_precision: "exact",
      latitude: null,
      longitude: null,
      timezone: "Asia/Kolkata",
      is_primary: true,
    });
    expect(exactMissingCoords.success).toBe(false);
  });
});
