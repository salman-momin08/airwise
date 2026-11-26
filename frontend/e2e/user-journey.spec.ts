import { expect, test } from "@playwright/test";

test("complete 13-step AirWise user journey from public AQI to account erasure", async ({
  page,
}) => {
  test.setTimeout(90_000);
  const uniqueEmail = `e2e.resident.${Date.now()}@example.com`;

  // Step 1: Guest opens / and navigates to /air-quality
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: /Evidence-grounded smog protection/i }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Public AQI" }).click();
  await expect(page).toHaveURL(/\/air-quality/);

  // Step 2: User selects a city manually without forced geolocation
  await page.locator("#aqi-city-selector").selectOption("Bengaluru");
  await page.locator("#aqi-city-selector").selectOption("Delhi");

  // Step 3: Verified air quality data loads with standard, timestamp, and provenance
  await expect(page.getByRole("status").first()).toContainText("India NAQI");
  await expect(page.getByText(/Source:/i).first()).toBeVisible();
  await expect(page.getByText(/Measured:/i).first()).toBeVisible();

  // Step 4: User registers an account
  await page.goto("/register");
  await page.locator("#reg-name").fill("Ananya Rao");
  await page.locator("#reg-email").fill(uniqueEmail);
  await page.locator("#reg-password").fill("CleanAirJourney2026");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/\/dashboard\/settings\/locations/);

  // Step 5: User configures household & commute preferences
  await page.goto("/dashboard/settings/preferences");
  await page
    .getByRole("checkbox", {
      name: /Household includes young children, older adults/i,
    })
    .check();
  await page.getByRole("checkbox", { name: "Metro / Urban Rail" }).check();
  await page.getByRole("button", { name: "Save preferences" }).click();
  await expect(
    page.getByText(/Household & commute preferences updated/i),
  ).toBeVisible();

  // Step 6 & Step 7: User asks AirWise Copilot & receives streamed tool-grounded guidance
  await page.goto("/dashboard/assistant");
  await page
    .getByLabel("Your environmental question")
    .fill("How should our household reduce indoor smoke exposure today?");
  await page.getByRole("checkbox", { name: /I agree to send/i }).check();
  await page.getByRole("button", { name: "Send question" }).click();
  await expect(
    page.getByRole("article", { name: "Assistant guidance" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Verified reference documents" }),
  ).toBeVisible();

  // Step 8: User generates, edits, and explicitly confirms a personalized daily routine
  await page.goto("/dashboard/routine-planner");
  await page
    .getByRole("button", { name: /Generate Morning–Night Draft/i })
    .click();
  await expect(page.getByText(/Unconfirmed Draft:/i)).toBeVisible();
  const firstActivityInput = page.getByLabel("Activity Title").first();
  await firstActivityInput.fill("Indoor Stretching & HEPA Room Recovery");
  await page
    .getByRole("button", { name: "Confirm & Save Schedule" })
    .click();
  await expect(
    page.getByText(/Schedule explicitly confirmed and saved/i),
  ).toBeVisible();

  // Step 9: User compares transportation alternatives with transparent CO2e & exposure math
  await page.goto("/dashboard/transport");
  await page.locator("#tx-city").fill("Delhi");
  await page.locator("#tx-baseline").selectOption("car_solo_petrol");
  await page.locator("#tx-alternative").selectOption("bicycle");
  await page
    .getByRole("button", { name: /Compare Exposure & CO₂e/i })
    .click();
  await expect(
    page.getByText(/Model Estimate \(is_estimate: true\)/i),
  ).toBeVisible();
  await expect(
    page.getByText(/Exposure-First Safety Override/i),
  ).toBeVisible();

  // Step 10: User generates & records feedback on a personalized recommendation
  await page.goto("/dashboard");
  await page
    .getByRole("button", { name: /Generate Today's 5 Cards/i })
    .click();
  await expect(page.getByText("Transport & Mobility")).toBeVisible();
  await page.getByRole("button", { name: "completed" }).first().click();
  await expect(page.getByText(/Recorded: completed/i)).toBeVisible();

  // Step 11: User configures a smart AQI alert with quiet hours
  await page.goto("/dashboard/alerts");
  await page
    .getByRole("button", { name: "Create Smart Alert Rule" })
    .click();
  await expect(
    page.getByText(/Quiet hours: 22:00–07:00 \(Asia\/Kolkata\)/i),
  ).toBeVisible();

  // Step 12: User joins a neighborhood community initiative & logs voluntary action
  await page.goto("/dashboard/community");
  await page
    .getByRole("button", { name: "Join Neighborhood Group" })
    .click();
  await expect(
    page.getByText(/Membership & privacy display consent updated/i),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Log Voluntary Action" })
    .first()
    .click();
  await page
    .getByRole("button", { name: "Submit Self-Reported Entry" })
    .click();
  await expect(page.getByText(/Voluntary action logged!/i)).toBeVisible();

  // Step 13: User exports account JSON and permanently deletes their account
  await page.goto("/dashboard/settings/privacy");
  await page
    .getByRole("button", { name: "Download JSON data export" })
    .click();
  await expect(
    page.getByText(/Your portable JSON data archive has been downloaded/i),
  ).toBeVisible();
  await page.locator("#confirm-delete").fill("DELETE");
  await page
    .getByRole("button", { name: "Permanently delete my account" })
    .click();
  await expect(page).toHaveURL("http://localhost:3000/");
});
