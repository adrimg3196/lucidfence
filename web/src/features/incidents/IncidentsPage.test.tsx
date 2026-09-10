import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "@/test/render";
import { IncidentsPage } from "./IncidentsPage";
import * as hooks from "@/api/hooks";
import { ApiError } from "@/api/client";

vi.mock("@/api/hooks", async (orig) => ({
  ...(await orig<typeof hooks>()),
  useIncidents: vi.fn(),
  usePatchIncident: vi.fn(),
  useDevices: vi.fn(),
  useRunOnce: vi.fn(),
  useMe: vi.fn(),
}));
// La analítica tiene su propio test; aquí solo estorbaría (Recharts no mide en jsdom).
vi.mock("./IncidentAnalytics", () => ({ IncidentAnalytics: () => null }));

const incident = {
  id: "inc-geofence_exit-dev-004",
  device_id: "dev-004",
  device_name: "Portátil Ventas",
  kind: "geofence_exit",
  severity: "high",
  title: "Portátil Ventas está fuera de geocerca",
  recommendation: "Validar la ubicación reciente.",
  status: "open" as const,
  risk_score: 62,
  count: 3,
  evidence: ["fence_state=outside"],
  opened_at: "2026-09-06T10:00:00Z",
  updated_at: "2026-09-06T11:00:00Z",
  timeline: [],
};

function mockAll(over: Partial<Record<"incidents" | "patch", unknown>> = {}, caps = ["incident:read", "incident:write", "engine:run"]) {
  vi.mocked(hooks.useIncidents).mockReturnValue((over.incidents ?? { data: { items: [incident], total: 1 }, isPending: false, error: null }) as never);
  vi.mocked(hooks.usePatchIncident).mockReturnValue((over.patch ?? { mutate: vi.fn(), isPending: false }) as never);
  vi.mocked(hooks.useDevices).mockReturnValue({ data: { items: [{ id: "dev-004", name: "Portátil Ventas" }], total: 1 }, isPending: false, error: null } as never);
  vi.mocked(hooks.useRunOnce).mockReturnValue({ mutate: vi.fn(), isPending: false } as never);
  vi.mocked(hooks.useMe).mockReturnValue({ data: { capabilities: caps } } as never);
}

test("los cuatro estados de la bandeja", () => {
  mockAll({ incidents: { data: undefined, isPending: true, error: null } });
  const cargando = renderWithProviders(<IncidentsPage />);
  expect(screen.getByRole("status")).toBeInTheDocument();
  cargando.unmount();

  mockAll({ incidents: { data: { items: [], total: 0 }, isPending: false, error: null } });
  const vacio = renderWithProviders(<IncidentsPage />);
  expect(screen.getByText("Sin incidentes: el motor aún no ha derivado ninguno.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Ejecutar ciclo ahora" })).toBeInTheDocument();
  vacio.unmount();

  const refetch = vi.fn();
  mockAll({ incidents: { data: undefined, isPending: false, error: new ApiError(500, "internal", "error interno"), refetch } });
  const fallo = renderWithProviders(<IncidentsPage />);
  expect(screen.getByRole("alert")).toHaveTextContent("error interno (internal)");
  fallo.unmount();

  mockAll();
  renderWithProviders(<IncidentsPage />);
  expect(screen.getByRole("link", { name: /Portátil Ventas está fuera de geocerca/ })).toHaveAttribute("href", "/incidents/inc-geofence_exit-dev-004");
});

test("la pestaña y el filtro por dispositivo se propagan a la consulta", async () => {
  mockAll();
  renderWithProviders(<IncidentsPage />);
  expect(vi.mocked(hooks.useIncidents)).toHaveBeenLastCalledWith({ status: "open", device_id: undefined });

  const user = userEvent.setup();
  await user.click(screen.getByRole("tab", { name: "Cerrados" }));
  await waitFor(() => expect(vi.mocked(hooks.useIncidents)).toHaveBeenLastCalledWith({ status: "closed", device_id: undefined }));

  await user.click(screen.getByRole("tab", { name: "Todos" }));
  await waitFor(() => expect(vi.mocked(hooks.useIncidents)).toHaveBeenLastCalledWith({ status: undefined, device_id: undefined }));

  await user.selectOptions(screen.getByLabelText("Dispositivo"), "dev-004");
  await waitFor(() => expect(vi.mocked(hooks.useIncidents)).toHaveBeenLastCalledWith({ status: undefined, device_id: "dev-004" }));
});

test("reconocer desde la lista, y un viewer no ve los botones de acción", async () => {
  const mutate = vi.fn();
  mockAll({ patch: { mutate, isPending: false } });
  const conPermiso = renderWithProviders(<IncidentsPage />);
  await userEvent.setup().click(screen.getByRole("button", { name: "Reconocer" }));
  // usePatchIncident (T22, hooks.m2.ts) manda { id, patch: IncidentPatch }, no
  // el status plano: ver "Desviaciones" del informe de esta tarea.
  expect(mutate).toHaveBeenCalledWith({ id: "inc-geofence_exit-dev-004", patch: { status: "ack" } });
  conPermiso.unmount();

  mockAll({}, ["incident:read"]);
  renderWithProviders(<IncidentsPage />);
  expect(screen.queryByRole("button", { name: "Reconocer" })).toBeNull();
});
