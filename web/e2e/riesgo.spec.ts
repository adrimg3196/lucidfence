import { test, expect } from "@playwright/test";
import { E2E_EMAIL, E2E_PASSWORD } from "./credentials";

test.describe.serial("riesgo y acciones", () => {
  test("política desde plantilla → what-if → ciclo → riesgo explicado → incidente reconocido → handoff aprobado en dry-run", async ({ page }) => {
    // Retoma la sesión donde la deja demo.spec.ts: asistente completado, modo
    // demo activo, un ciclo ya ejecutado. Contexto de navegador nuevo → sin
    // cookies → entra por /login, no por el asistente.
    await page.goto("/");
    await expect(page).toHaveURL(/\/login$/);

    // Ninguna vista de este flujo puede dejar un console.error: es la única
    // aserción que cubre todas las pantallas a la vez, no solo un paso. El
    // listener se engancha aquí, tras resolver el redirect a /login, no antes
    // de `page.goto`: AuthGate (T7) comprueba la sesión con GET /auth/me en
    // cuanto monta, que en un contexto sin cookies responde 401 por diseño
    // (es la comprobación que produce el propio redirect a /login), y Chrome
    // registra ese 401, junto con un aviso informativo de CSP por la
    // cabecera `default-src` sin `script-src` explícito (internal/api/
    // middleware.go, sin cambios en esta tarea), como console.error aunque
    // ninguno de los dos sea un fallo de la aplicación. Enganchar el listener
    // después de confirmar /login descarta ese ruido de arranque, anterior a
    // la sesión, sin dejar de cubrir todo lo que ocurre desde que el usuario
    // ya está autenticado.
    const consoleErrors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") consoleErrors.push(msg.text());
    });

    await page.getByLabel("Email").fill(E2E_EMAIL);
    await page.getByLabel("Contraseña").fill(E2E_PASSWORD);
    await page.getByRole("button", { name: "Entrar" }).click();
    await expect(page).toHaveURL(/\/$/);

    // --- Políticas: plantilla, what-if, guardar ---
    await page.getByRole("link", { name: "Políticas" }).click();
    await expect(page.getByRole("heading", { name: "Políticas" })).toBeVisible();

    await page.getByRole("link", { name: "Partir de una plantilla" }).click();
    await expect(page).toHaveURL(/\/policies\/new\?plantillas=1$/);

    const templatesDialog = page.getByRole("dialog");
    await expect(templatesDialog).toBeVisible();
    const cisoName = "Avisar al CISO si la desviación supera 500 m";
    // El diálogo repite el nombre de la plantilla en varios ancestros
    // anidados (la propia tarjeta, el contenedor de la lista, el diálogo
    // entero): filtrar por las tarjetas que además contienen su botón "Usar"
    // y quedarse con la más interna (.last()) aísla la tarjeta en sí. El
    // locator de "Usar" que alimenta `has` se construye desde `page`, no
    // desde `templatesDialog`: un `has` construido sobre un locator que ya
    // arrastra el propio `role=dialog` en su cadena exige un `[role=dialog]`
    // anidado dentro de cada candidato para poder casar, y ninguna tarjeta lo
    // tiene, así que el filtro no encuentra nada (comprobado con una réplica
    // mínima de esta misma estructura DOM: 0 resultados con el locator
    // anclado en el diálogo, 1 con el locator anclado en `page`).
    const useButtons = page.getByRole("button", { name: "Usar" });
    const cisoCard = templatesDialog.locator("div", { hasText: cisoName }).filter({ has: useButtons }).last();
    await expect(cisoCard).toBeVisible();
    await cisoCard.getByRole("button", { name: "Usar" }).click();
    await expect(templatesDialog).toBeHidden();
    await expect(page.getByRole("heading", { name: "Nueva política" })).toBeVisible();

    await expect(page.getByLabel("Nombre")).toHaveValue(cisoName);
    await expect(page.getByLabel("Identificador")).toHaveValue("tpl-ciso-deviation-500");

    const whatIf = page.locator("section", { hasText: "Simulador what-if" });
    await expect(whatIf.getByRole("heading", { name: "Simulador what-if" })).toBeVisible();
    await whatIf.getByRole("button", { name: "Simular" }).click();
    const firings = whatIf.getByText("Disparos", { exact: true });
    const noFirings = whatIf.getByText("No habría disparado ni una vez");
    // El histórico real de la flota demo decide si la plantilla dispara o no
    // (T17 corre contra el trail real, no contra datos fijos). Las dos
    // salidas son honestas por diseño (T23): lo único que no puede pasar es
    // un error.
    await expect(firings.or(noFirings)).toBeVisible({ timeout: 15_000 });
    await expect(whatIf.getByRole("alert")).toHaveCount(0);
    if (await firings.isVisible()) {
      await expect(whatIf.getByText("Ventana", { exact: true })).toBeVisible();
    } else {
      await expect(noFirings).toBeVisible();
    }

    await page.getByRole("button", { name: "Guardar" }).click();
    await expect(page).toHaveURL(/\/policies$/);
    await expect(page.getByRole("link", { name: cisoName })).toBeVisible();

    // --- Ciclo desde la visión general ---
    await page.getByRole("link", { name: "Visión general" }).click();
    const runCycle = page.getByRole("button", { name: "Ejecutar ciclo ahora" });
    await runCycle.click();
    await expect(runCycle).toBeEnabled();

    // --- Riesgo explicado en el detalle de dev-004 ---
    await page.getByRole("link", { name: "Dispositivos" }).click();
    await page.getByRole("link", { name: /Portátil Ventas/ }).click();
    await expect(page.getByText("Sin evaluar")).toHaveCount(0);
    // "dispositivo no conforme" es la razón dorada de risk.Evaluate para todo
    // dispositivo con compliant=false (T3, TestCompliantNilNoSuma25):
    // determinista con independencia del resto de señales de la flota.
    await expect(page.getByText("dispositivo no conforme")).toBeVisible();

    // --- Incidentes: reconocer el que abrió dev-004 ---
    const incidentTitle = "Portátil Ventas está fuera de geocerca";
    await page.getByRole("link", { name: "Incidentes" }).click();
    await expect(page.getByRole("heading", { name: "Incidentes" })).toBeVisible();
    await page.getByRole("link", { name: incidentTitle }).click();
    await expect(page.getByRole("heading", { name: incidentTitle })).toBeVisible();
    await page.getByRole("button", { name: "Reconocer" }).click();
    // La insignia de estado usa incident.status.ack = "Reconocido" como texto
    // exacto (M2-R70): un único match. El historial (IncidentTimeline) mete
    // la transición entera en un <span> ("Abierto" + flecha + "Reconocido"),
    // así que ningún nodo tiene "Reconocido" como texto exacto; se comprueba
    // por separado que la entrada del historial contiene ese texto como
    // subcadena, que es lo que demuestra que la transición quedó registrada.
    await expect(page.getByText("Reconocido", { exact: true })).toHaveCount(1);
    await expect(page.getByRole("listitem").filter({ hasText: "Reconocido" })).toHaveCount(1);

    // El detalle del incidente trae su propio enlace "Volver a incidentes"
    // (T24), que "Incidentes" también casa como subcadena por defecto: el
    // enlace de navegación necesita exact:true aquí para no ambiguar entre
    // los dos (la primera vez que se pulsa este enlace, desde el detalle de
    // dispositivo, no hay ambigüedad porque esa página no tiene ese enlace).
    await page.getByRole("link", { name: "Incidentes", exact: true }).click();
    await expect(page.getByRole("link", { name: incidentTitle })).toHaveCount(0);
    await page.getByRole("tab", { name: "Reconocidos" }).click();
    await expect(page.getByRole("link", { name: incidentTitle })).toBeVisible();

    // --- Handoffs: aprobar el pendiente del playbook de fábrica ---
    await page.getByRole("link", { name: "Aprobaciones" }).click();
    await expect(page.getByRole("heading", { name: "Bandeja de handoffs" })).toBeVisible();

    const handoffCard = page.locator("article", { hasText: "Portátil Ventas" });
    await expect(handoffCard).toBeVisible();
    await expect(handoffCard.getByText("Bloquear", { exact: true })).toBeVisible();
    await expect(handoffCard.getByText("No conforme y fuera de geocerca")).toBeVisible();
    await handoffCard.getByRole("button", { name: "Aprobar" }).click();

    // El fondo queda aria-hidden mientras el diálogo está abierto (T25), así
    // que las consultas por rol de aquí en adelante no chocan con los mismos
    // textos de la tarjeta que sigue debajo.
    const decisionDialog = page.getByRole("dialog");
    await expect(decisionDialog.getByText("Aprobar Bloquear")).toBeVisible();
    await decisionDialog
      .getByLabel("Nota de la decisión (obligatoria)")
      .fill("Aprobado en el e2e: bloqueo confirmado tras revisar el incidente de dev-004.");
    await decisionDialog.getByRole("button", { name: "Aprobar" }).click();
    await expect(decisionDialog).toBeHidden();

    // La bandeja arranca filtrada por "pendiente" y aprobar invalida la
    // consulta de handoffs: el refetch retira la tarjeta de esa pestaña en
    // cuanto el servidor deja de listarla como pendiente (M2-R71). La
    // garantía visible de que observe no ha tocado el dispositivo se
    // comprueba en la pestaña "Ejecutada", donde la tarjeta reaparece de
    // forma estable: el resultado se anuncia como dry-run, nunca como
    // "Ejecutado" a secas.
    await page.getByRole("tab", { name: "Ejecutada" }).click();
    await expect(handoffCard.getByText("Ejecutado en dry-run (modo observe)")).toBeVisible();
    await expect(handoffCard.getByText("Ejecutado", { exact: true })).toHaveCount(0);

    expect(consoleErrors).toEqual([]);
  });
});
