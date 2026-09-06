import { test, expect } from "@playwright/test";

test.describe.serial("núcleo demo", () => {
  test("asistente → demo → visión general → mapa → dispositivo → geocerca → ciclo", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveURL(/\/setup$/);
    await page.getByLabel("Email").fill("e2e@lucidfence.local");
    await page.getByLabel("Nombre").fill("E2E");
    await page.getByLabel(/Contraseña/).fill("contraseña-e2e-2026");
    await page.getByLabel("Demo local con flota simulada").check();
    await page.getByRole("button", { name: "Crear cuenta y entrar" }).click();

    await expect(page).toHaveURL(/\/$/);
    await expect(page.getByRole("heading", { name: "Visión general" })).toBeVisible();
    await expect(page.locator("p", { hasText: /^Dispositivos$/ }).locator("xpath=following-sibling::p")).toHaveText("6");

    await page.getByRole("link", { name: "Mapa" }).click();
    await expect(page.getByText("Dentro de geocerca")).toBeVisible();
    await expect(page.locator(".maplibregl-canvas")).toBeVisible();

    await page.getByRole("link", { name: "Dispositivos" }).click();
    await expect(page.getByRole("row")).toHaveCount(7);
    await page.getByRole("link", { name: /Tablet Campo A1/ }).click();
    await expect(page.getByText("Samsung Galaxy Tab Active5")).toBeVisible();

    await page.getByRole("link", { name: "Geocercas" }).click();
    await expect(page.getByRole("link", { name: "Demo HQ · Madrid" })).toBeVisible();
    await page.getByRole("link", { name: "Nueva geocerca" }).click();
    await page.getByLabel("Nombre").fill("Oficina Norte");
    await page.getByLabel("Latitud").fill("40.45");
    await page.getByLabel("Longitud").fill("-3.65");
    await page.getByLabel("Radio (m)").fill("400");
    await page.getByRole("button", { name: "Guardar" }).click();
    await expect(page.getByRole("link", { name: "Oficina Norte" })).toBeVisible();

    await page.getByRole("link", { name: "Visión general" }).click();
    await page.getByRole("button", { name: "Ejecutar ciclo ahora" }).click();
    await expect(page.getByText("demo-hq:inside").first()).toBeVisible();
  });
});
