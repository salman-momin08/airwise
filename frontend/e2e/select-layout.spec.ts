import { expect, test } from "@playwright/test";

for (const width of [375, 1280]) {
  for (const theme of ["light", "dark"]) {
    test(`selector chevrons stay centered and inset at ${width}px in ${theme} mode`, async ({
      page,
    }) => {
      await page.setViewportSize({ width, height: 900 });
      await page.addInitScript((value) => {
        localStorage.setItem("theme", value);
      }, theme);
      await page.goto("/register");

      const select = page.getByLabel("Preferred AQI standard", { exact: true });
      await expect(select).toBeVisible();
      const layout = await select.evaluate((element) => {
        const style = getComputedStyle(element);
        const rootFontSize = parseFloat(getComputedStyle(document.documentElement).fontSize);
        return {
          appearance: style.appearance,
          image: style.backgroundImage,
          position: style.backgroundPosition,
          size: style.backgroundSize,
          padding: parseFloat(style.paddingInlineEnd) / rootFontSize,
          repeat: style.backgroundRepeat,
          fitsViewport: element.getBoundingClientRect().right <= window.innerWidth,
        };
      });

      expect(layout.appearance).toBe("none");
      expect(layout.image).toContain(theme === "dark" ? "%239DB4BC" : "%2360747C");
      expect(layout.position).toBe("calc(100% - 12px) 50%");
      expect(layout.size).toBe("16px 16px");
      expect(layout.repeat).toBe("no-repeat");
      expect(layout.padding).toBeGreaterThanOrEqual(2.5);
      expect(layout.fitsViewport).toBe(true);

      await select.focus();
      await page.keyboard.press("Home");
      await page.keyboard.press("ArrowDown");
      await page.keyboard.press("Enter");
      await expect(select).toHaveValue("us_epa");

      await select.evaluate((element) => element.setAttribute("dir", "rtl"));
      await expect(select).toHaveCSS("background-position", "12px 50%");
      await expect(select).toHaveCSS("padding-left", "40px");
    });
  }
}

test("selectors retain a native arrow in forced-colors mode", async ({ page }) => {
  await page.emulateMedia({ forcedColors: "active" });
  await page.goto("/register");
  const select = page.getByLabel("Preferred AQI standard", { exact: true });
  await expect(select).toHaveCSS("appearance", "auto");
  await expect(select).toHaveCSS("background-image", "none");
  await select.selectOption("us_epa");
  await expect(select).toHaveValue("us_epa");
});
