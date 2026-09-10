import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router";
import { renderWithProviders } from "@/test/render";
import { IncidentDetailPage } from "./IncidentDetailPage";
import * as hooks from "@/api/hooks";
import { ApiError } from "@/api/client";

vi.mock("@/api/hooks", async (orig) => ({ ...(await orig<typeof hooks>()), useIncident: vi.fn(), usePatchIncident: vi.fn(), useMe: vi.fn() }));

const incident = {
  id: "inc-1",
  device_id: "dev-004",
  device_name: "Portátil Ventas",
  kind: "geofence_exit",
  severity: "high",
  title: "Portátil Ventas está fuera de geocerca",
  recommendation: "Validar la ubicación reciente y contactar con la persona responsable.",
  status: "open" as const,
  risk_score: 62,
  count: 2,
  evidence: ["fence_state=outside", "last_inside_fence=demo-hq"],
  opened_at: "2026-09-06T10:00:00Z",
  updated_at: "2026-09-06T11:00:00Z",
  timeline: [{ at: "2026-09-06T11:00:00Z", actor: "sistema", from: "", to: "open", note: "abierto por el ciclo" }],
};

function renderDetail() {
  return renderWithProviders(
    <Routes>
      <Route path="/incidents/:id" element={<IncidentDetailPage />} />
    </Routes>,
    { route: "/incidents/inc-1" },
  );
}

function mockAll(inc: unknown = incident, caps = ["incident:read", "incident:write"], patch: unknown = { mutate: vi.fn(), isPending: false }) {
  vi.mocked(hooks.useIncident).mockReturnValue({ data: inc, isPending: false, error: null } as never);
  vi.mocked(hooks.usePatchIncident).mockReturnValue(patch as never);
  vi.mocked(hooks.useMe).mockReturnValue({ data: { capabilities: caps } } as never);
}

test("muestra dispositivo, recomendación, evidencia e historial con autor y nota", () => {
  mockAll();
  renderDetail();
  expect(screen.getByRole("heading", { name: "Portátil Ventas está fuera de geocerca" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Portátil Ventas" })).toHaveAttribute("href", "/devices/dev-004");
  expect(screen.getByText("Validar la ubicación reciente y contactar con la persona responsable.")).toBeInTheDocument();
  expect(screen.getByText("last_inside_fence=demo-hq")).toBeInTheDocument();
  expect(screen.getByText(/sistema/)).toBeInTheDocument();
  expect(screen.getByText(/abierto por el ciclo/)).toBeInTheDocument();
});

test("reconocer manda status ack sin nota", async () => {
  const mutate = vi.fn();
  mockAll(incident, ["incident:read", "incident:write"], { mutate, isPending: false });
  renderDetail();
  await userEvent.setup().click(screen.getByRole("button", { name: "Reconocer" }));
  expect(mutate).toHaveBeenCalledWith({ id: "inc-1", patch: { status: "ack" } });
});

test("cerrar pide la nota y la envía", async () => {
  const mutate = vi.fn();
  mockAll(incident, ["incident:read", "incident:write"], { mutate, isPending: false });
  renderDetail();
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: "Cerrar" }));
  expect(await screen.findByText("Cerrar el incidente")).toBeInTheDocument();
  const confirmar = screen.getAllByRole("button", { name: "Cerrar" }).at(-1)!;
  expect(confirmar).toBeDisabled();
  await user.type(screen.getByLabelText("Nota"), "Recuperado en almacén");
  expect(confirmar).toBeEnabled();
  await user.click(confirmar);
  // El cierre manda un segundo argumento a mutate (onSuccess, para vaciar el
  // formulario cuando el servidor confirma): se comprueba con un matcher, no
  // con igualdad estricta de argumentos.
  expect(mutate).toHaveBeenCalledWith({ id: "inc-1", patch: { status: "closed", note: "Recuperado en almacén" } }, expect.anything());
});

test("un incidente cerrado solo ofrece reabrir", () => {
  mockAll({ ...incident, status: "closed", closed_at: "2026-09-06T12:00:00Z" });
  renderDetail();
  expect(screen.getByRole("button", { name: "Reabrir" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Reconocer" })).toBeNull();
  expect(screen.queryByRole("button", { name: "Cerrar" })).toBeNull();
});

test("con rol viewer no se renderiza ningún botón de transición", () => {
  mockAll(incident, ["incident:read"]);
  renderDetail();
  for (const label of ["Reconocer", "Cerrar", "Reabrir"]) expect(screen.queryByRole("button", { name: label })).toBeNull();
});

test("un id inexistente muestra el estado de error", () => {
  const refetch = vi.fn();
  vi.mocked(hooks.useIncident).mockReturnValue({ data: undefined, isPending: false, error: new ApiError(404, "not_found", "incidente no encontrado"), refetch } as never);
  vi.mocked(hooks.usePatchIncident).mockReturnValue({ mutate: vi.fn(), isPending: false } as never);
  vi.mocked(hooks.useMe).mockReturnValue({ data: { capabilities: ["incident:read"] } } as never);
  renderDetail();
  expect(screen.getByRole("alert")).toHaveTextContent("incidente no encontrado (not_found)");
});
