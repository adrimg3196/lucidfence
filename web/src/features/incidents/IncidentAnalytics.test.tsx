import { screen } from "@testing-library/react";
import { renderWithProviders } from "@/test/render";
import { IncidentAnalytics } from "./IncidentAnalytics";
import * as hooks from "@/api/hooks";

vi.mock("@/api/hooks", async (orig) => ({ ...(await orig<typeof hooks>()), useIncidentAnalytics: vi.fn(), useMe: vi.fn() }));

const analytics = {
  total: 4,
  open: 2,
  ack: 1,
  closed: 1,
  by_severity: { high: 3, medium: 1 },
  by_kind: { geofence_exit: 3, device_non_compliant: 1 },
  by_day: [
    { day: "2026-09-05", count: 1 },
    { day: "2026-09-06", count: 3 },
  ],
  mttr_seconds: null as number | null,
  top_devices: [{ device_id: "dev-004", device_name: "Portátil Ventas", count: 3 }],
};

function mockAll(data: unknown = analytics, caps: string[] = ["incident:read", "report:export"]) {
  vi.mocked(hooks.useIncidentAnalytics).mockReturnValue({ data, isPending: false, error: null } as never);
  vi.mocked(hooks.useMe).mockReturnValue({ data: { capabilities: caps } } as never);
}

test("mttr_seconds nulo se lee 'Sin datos' y nunca '0 s'", () => {
  mockAll();
  renderWithProviders(<IncidentAnalytics />);
  expect(screen.getByText("Sin datos")).toBeInTheDocument();
  expect(screen.queryByText("0 s")).toBeNull();
});

test("mttr_seconds con valor se formatea en horas y minutos", () => {
  mockAll({ ...analytics, mttr_seconds: 8100 });
  renderWithProviders(<IncidentAnalytics />);
  expect(screen.getByText("2 h 15 min")).toBeInTheDocument();
  expect(screen.queryByText("Sin datos")).toBeNull();
});

test("sin incidentes muestra el vacío y no dibuja ningún gráfico", () => {
  mockAll({ ...analytics, total: 0, open: 0, ack: 0, closed: 0, by_severity: {}, by_kind: {}, by_day: [], top_devices: [] });
  const { container } = renderWithProviders(<IncidentAnalytics />);
  expect(screen.getByText("Sin incidentes que analizar todavía")).toBeInTheDocument();
  expect(container.querySelector(".recharts-responsive-container")).toBeNull();
});

test("el enlace de exportar solo aparece con report:export", () => {
  mockAll();
  const conPermiso = renderWithProviders(<IncidentAnalytics />);
  expect(screen.getByRole("link", { name: "Exportar CSV" })).toHaveAttribute("href", "/api/v1/incidents/export");
  conPermiso.unmount();

  mockAll(analytics, ["incident:read"]);
  renderWithProviders(<IncidentAnalytics />);
  expect(screen.queryByRole("link", { name: "Exportar CSV" })).toBeNull();
});
