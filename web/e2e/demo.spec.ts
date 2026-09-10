import { test, expect } from "@playwright/test";
import { E2E_EMAIL, E2E_PASSWORD } from "./credentials";

// El asistente solo se completa una vez por proceso del servidor de e2e (un
// único webServer para toda la ejecución de `npm run e2e`), así que
// riesgo.spec.ts entra por /login con las mismas credenciales (compartidas
// vía ./credentials, M2-R69) en vez de repetir el alta.

test.describe.serial("núcleo demo", () => {
  test("asistente → demo → visión general → mapa → dispositivo → geocerca → ciclo", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveURL(/\/setup$/);
    await page.getByLabel("Email").fill(E2E_EMAIL);
    await page.getByLabel("Nombre").fill("E2E");
    await page.getByLabel(/Contraseña/).fill(E2E_PASSWORD);
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
    // 40.47 / -3.60 no toca a ningún dispositivo de la flota demo (todos
    // agrupados entre 40.40/-3.71 y 40.45/-3.65, ver default_seed.json). Con
    // las coordenadas originales de M1 (40.45 / -3.65) esta geocerca coincidía
    // exactamente con dev-004 "Portátil Ventas" (radio 400 m, distancia 0) y
    // lo habría metido "dentro" en el primer ciclo: riesgo.spec.ts (T29)
    // depende de que dev-004 siga fuera de toda geocerca, que es lo que
    // dispara el incidente geofence_exit y el handoff del playbook de fábrica
    // soar-noncompliant-outside (T5, T16).
    await page.getByLabel("Latitud").fill("40.47");
    await page.getByLabel("Longitud").fill("-3.60");
    await page.getByLabel("Radio (m)").fill("400");
    await page.getByRole("button", { name: "Guardar" }).click();
    await expect(page.getByRole("link", { name: "Oficina Norte" })).toBeVisible();

    await page.getByRole("link", { name: "Visión general" }).click();
    await page.getByRole("button", { name: "Ejecutar ciclo ahora" }).click();
    await expect(page.getByText("demo-hq:inside").first()).toBeVisible();
  });
});
