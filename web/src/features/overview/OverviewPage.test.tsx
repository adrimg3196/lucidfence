import { screen } from "@testing-library/react";
import { renderWithProviders } from "@/test/render";
import { OverviewPage } from "./OverviewPage";
import * as hooks from "@/api/hooks";
import { ApiError } from "@/api/client";

vi.mock("@/api/hooks", async (orig) => ({
  ...(await orig<typeof hooks>()),
  useDevices: vi.fn(),
  useEngineStatus: vi.fn(),
  useEvents: vi.fn(),
  useRunOnce: vi.fn(),
  useMe: vi.fn(),
  useHandoffs: vi.fn(),
}));

// Ancla nextSibling de forma determinista sobre el severity de la insignia,
// igual que el resto de este fichero hace con Kpi.
vi.mock("@/components/SeverityBadge", () => ({
  SeverityBadge: ({ severity }: { severity: string }) => <span data-testid={`sev-${severity}`}>{severity}</span>,
}));

const device = (id: string, fence_state: string, compliant: boolean | null, severity = "unknown") => ({ id, name: id, fence_state, compliant, risk: { severity } });

function mock(over: Partial<Record<"devices" | "engine" | "events" | "handoffs", unknown>> = {}) {
  vi.mocked(hooks.useDevices).mockReturnValue({
    data: { items: [device("a", "inside", true, "low"), device("b", "outside", false, "high"), device("c", "unknown", null, "high")], total: 3 },
    isPending: false,
    error: null,
    refetch: vi.fn(),
    ...(over.devices as object),
  } as never);
  vi.mocked(hooks.useEngineStatus).mockReturnValue({
    data: {
      mode: "simulation",
      enforcement: { mode: "observe", live_actions: null, allow_wipe: false, wipe_allowlist: null, action_cooldown_seconds: 3600 },
      interval_seconds: 900,
      running: true,
      cycles: 2,
      providers: { simulation: { ok: true, devices: 3, latency_ms: 4 } },
      last_cycle: { at: "2026-09-05T12:00:00Z" },
    },
    isPending: false,
    error: null,
    ...(over.engine as object),
  } as never);
  vi.mocked(hooks.useEvents).mockReturnValue({
    data: { items: [{ at: "2026-09-05T12:00:00Z", device_id: "a", device_name: "a", from: "none:unknown", to: "demo-hq:inside" }] },
    isPending: false,
    error: null,
    ...(over.events as object),
  } as never);
  vi.mocked(hooks.useRunOnce).mockReturnValue({ mutate: vi.fn(), isPending: false } as never);
  vi.mocked(hooks.useMe).mockReturnValue({ data: { capabilities: ["engine:run"] } } as never);
  vi.mocked(hooks.useHandoffs).mockReturnValue({ data: { items: [{ id: "ho-1" }], total: 1 }, isPending: false, error: null, refetch: vi.fn(), ...(over.handoffs as object) } as never);
}

test("contenido: KPIs, motor, riesgo de la flota, handoffs, transiciones y proveedores", () => {
  mock();
  renderWithProviders(<OverviewPage />);
  expect(screen.getByText("Dispositivos").nextSibling).toHaveTextContent("3");
  expect(screen.getByText("Dentro").nextSibling).toHaveTextContent("1");
  expect(screen.getByText("Cumplimiento").nextSibling).toHaveTextContent("33 %");
  expect(screen.getByRole("button", { name: "Ejecutar ciclo ahora" })).toBeEnabled();
  expect(screen.getByText("demo-hq:inside")).toBeInTheDocument();
  expect(screen.getAllByText("simulation")).toHaveLength(2);
  expect(screen.getByTestId("sev-low").nextSibling).toHaveTextContent("1");
  expect(screen.getByTestId("sev-high").nextSibling).toHaveTextContent("2");
  expect(screen.getByTestId("handoffs-pending-count")).toHaveTextContent("1");
});

test("cargando, vacío y error", () => {
  mock({ devices: { data: undefined, isPending: true }, events: { data: { items: [] } }, engine: { data: undefined, error: new Error("boom"), isPending: false } });
  renderWithProviders(<OverviewPage />);
  expect(screen.getAllByRole("status").length).toBeGreaterThan(0);
  expect(screen.getByText("Aún no hay transiciones. Ejecuta un ciclo.")).toBeInTheDocument();
  expect(screen.getByRole("alert")).toHaveTextContent("boom");
});

test("sin engine:run no se muestra el botón", () => {
  mock();
  vi.mocked(hooks.useMe).mockReturnValue({ data: { capabilities: [] } } as never);
  renderWithProviders(<OverviewPage />);
  expect(screen.queryByRole("button", { name: "Ejecutar ciclo ahora" })).toBeNull();
});

test("un 409 de run-once se muestra como texto", () => {
  mock();
  vi.mocked(hooks.useRunOnce).mockReturnValue({ mutate: vi.fn(), isPending: false, error: new ApiError(409, "cycle_in_progress", "ciclo en curso") } as never);
  renderWithProviders(<OverviewPage />);
  expect(screen.getByRole("alert")).toHaveTextContent("ciclo en curso");
});

test("last_error del motor se muestra como texto", () => {
  mock({
    engine: {
      data: {
        mode: "simulation",
        enforcement: { mode: "observe", live_actions: null, allow_wipe: false, wipe_allowlist: null, action_cooldown_seconds: 3600 },
        interval_seconds: 900,
        running: true,
        cycles: 2,
        providers: { simulation: { ok: true, devices: 3, latency_ms: 4 } },
        last_cycle: { at: "2026-09-05T12:00:00Z" },
        last_error: "proveedor simulation: tiempo agotado",
      },
    },
  });
  renderWithProviders(<OverviewPage />);
  expect(screen.getByText("proveedor simulation: tiempo agotado")).toBeInTheDocument();
});

test("un error de la bandeja de handoffs no rompe el resto de la página", () => {
  mock({ handoffs: { data: undefined, error: new ApiError(500, "internal", "error interno"), refetch: vi.fn() } });
  renderWithProviders(<OverviewPage />);
  expect(screen.getByRole("heading", { name: "Visión general" })).toBeInTheDocument();
  expect(screen.getAllByRole("alert").some((a) => a.textContent?.includes("error interno"))).toBe(true);
});
