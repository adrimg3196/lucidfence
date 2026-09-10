import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "@/test/render";
import { HandoffsPage } from "./HandoffsPage";
import { ApiError } from "@/api/client";
import * as hooks from "@/api/hooks";

vi.mock("@/api/hooks", async (orig) => ({
  ...(await orig<typeof hooks>()),
  useHandoffs: vi.fn(),
  useApproveHandoff: vi.fn(),
  useRejectHandoff: vi.fn(),
  useMe: vi.fn(),
}));

// pendiente es la foto que devuelve GET /api/v1/handoffs: el mismo handoff
// que T20 usa en sus casos ("ho-lock"/"ho-wipe"), recortado a los campos que
// la tarjeta pinta.
function pendiente(over: Partial<hooks.Handoff> = {}): hooks.Handoff {
  return {
    id: "ho-lock",
    device_id: "dev-001",
    device_name: "Tablet Campo A1",
    playbook_id: "soar-noncompliant-outside",
    playbook_name: "No conforme y fuera de geocerca",
    action: "lock",
    reason: "compliant=false, fence_state=outside",
    severity: "high",
    status: "pending",
    requested_at: "2026-09-06T09:00:00Z",
    // El brief original no aplicaba `over` (parámetro declarado y nunca usado):
    // los dos casos de wipe ("ho-wipe", action: "wipe") se quedaban en el lock
    // por defecto y fallaban por una razón ajena a lo que decían comprobar.
    ...over,
  } as hooks.Handoff;
}

function mockBandeja(items: hooks.Handoff[], extra: Record<string, unknown> = {}) {
  const refetch = vi.fn();
  vi.mocked(hooks.useHandoffs).mockReturnValue({ data: { items, total: items.length }, isPending: false, error: null, refetch, ...extra } as never);
  return refetch;
}

function mockDecisiones(approve: ReturnType<typeof vi.fn>, reject = vi.fn()) {
  vi.mocked(hooks.useApproveHandoff).mockReturnValue({ mutate: approve, isPending: false, error: null } as never);
  vi.mocked(hooks.useRejectHandoff).mockReturnValue({ mutate: reject, isPending: false, error: null } as never);
}

beforeEach(() => {
  vi.mocked(hooks.useMe).mockReturnValue({ data: { capabilities: ["incident:read", "handoff:approve"] } } as never);
  mockDecisiones(vi.fn());
});

test("los cuatro estados de la vista", () => {
  vi.mocked(hooks.useHandoffs).mockReturnValue({ data: undefined, isPending: true, error: null, refetch: vi.fn() } as never);
  const cargando = renderWithProviders(<HandoffsPage />);
  expect(screen.getByRole("status")).toBeInTheDocument();
  cargando.unmount();

  mockBandeja([]);
  const vacio = renderWithProviders(<HandoffsPage />);
  expect(screen.getByText("Nada pendiente de aprobación.")).toBeInTheDocument();
  vacio.unmount();

  const refetch = vi.fn();
  vi.mocked(hooks.useHandoffs).mockReturnValue({ data: undefined, isPending: false, error: new Error("motor caído"), refetch } as never);
  const fallo = renderWithProviders(<HandoffsPage />);
  expect(screen.getByRole("alert")).toHaveTextContent("motor caído");
  fallo.unmount();

  mockBandeja([pendiente()]);
  renderWithProviders(<HandoffsPage />);
  expect(screen.getByText("Tablet Campo A1")).toBeInTheDocument();
  expect(screen.getByText("No conforme y fuera de geocerca")).toBeInTheDocument();
  expect(screen.getByText("compliant=false, fence_state=outside")).toBeInTheDocument();
});

test("aprobar abre el diálogo y no llama a la mutación hasta confirmar", async () => {
  const approve = vi.fn();
  mockBandeja([pendiente()]);
  mockDecisiones(approve);
  renderWithProviders(<HandoffsPage />);
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: "Aprobar" }));
  expect(await screen.findByRole("dialog")).toHaveTextContent("Bloquear sobre Tablet Campo A1 (dev-001)");
  expect(approve).not.toHaveBeenCalled();
  // sin nota el botón de confirmar sigue deshabilitado: la nota es obligatoria
  const confirmar = screen.getAllByRole("button", { name: "Aprobar" }).at(-1)!;
  expect(confirmar).toBeDisabled();
  await user.type(screen.getByLabelText("Nota de la decisión (obligatoria)"), "confirmado por el SOC");
  await user.click(confirmar);
  expect(approve).toHaveBeenCalledWith({ id: "ho-lock", note: "confirmado por el SOC" }, expect.anything());
});

test("un wipe exige teclear el identificador del dispositivo", async () => {
  const approve = vi.fn();
  mockBandeja([pendiente({ id: "ho-wipe", action: "wipe", severity: "critical" })]);
  mockDecisiones(approve);
  renderWithProviders(<HandoffsPage />);
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: "Aprobar" }));
  await user.type(screen.getByLabelText("Nota de la decisión (obligatoria)"), "aprobado por dirección");
  const confirmar = screen.getAllByRole("button", { name: "Aprobar" }).at(-1)!;
  expect(confirmar).toBeDisabled();
  const idInput = screen.getByLabelText("Escribe dev-001 para confirmar el borrado");
  await user.type(idInput, "dev-00");
  expect(confirmar).toBeDisabled();
  await user.type(idInput, "1");
  await waitFor(() => expect(confirmar).toBeEnabled());
  await user.click(confirmar);
  expect(approve).toHaveBeenCalledWith({ id: "ho-wipe", note: "aprobado por dirección" }, expect.anything());
});

test("en observe la respuesta se muestra como dry-run, no como ejecutado", async () => {
  const decidido = {
    ...pendiente(),
    status: "executed",
    decided_by: "adri@example.com",
    note: "confirmado por el SOC",
    decided_at: "2026-09-06T09:05:00Z",
    result: { adapter: "simulation", ok: true, device_id: "dev-001", device_name: "Tablet Campo A1", action: "lock", dry_run: true, simulated: true, at: "2026-09-06T09:05:00Z", trigger: "handoff" },
  } as hooks.Handoff;
  const approve = vi.fn((_vars, opts) => opts.onSuccess(decidido));
  mockBandeja([pendiente()]);
  mockDecisiones(approve);
  renderWithProviders(<HandoffsPage />);
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: "Aprobar" }));
  await user.type(screen.getByLabelText("Nota de la decisión (obligatoria)"), "confirmado por el SOC");
  await user.click(screen.getAllByRole("button", { name: "Aprobar" }).at(-1)!);
  expect(await screen.findByText("Ejecutado en dry-run (modo observe)")).toBeInTheDocument();
  expect(screen.queryByText("Ejecutado")).toBeNull();
  expect(screen.getByText("adri@example.com")).toBeInTheDocument();
});

test("un bloqueo del guardarraíl muestra su motivo, no un éxito", async () => {
  const bloqueado = {
    ...pendiente({ id: "ho-wipe", action: "wipe", severity: "critical" }),
    status: "executed",
    decided_by: "adri@example.com",
    result: {
      adapter: "simulation", ok: false, device_id: "dev-001", device_name: "Tablet Campo A1", action: "wipe",
      dry_run: false, simulated: false, blocked: true, error_type: "wipe_not_allowed",
      error: "la doble llave del wipe está cerrada: enforcement.allow_wipe desactivado",
      at: "2026-09-06T09:05:00Z", trigger: "handoff",
    },
  } as hooks.Handoff;
  const approve = vi.fn((_vars, opts) => opts.onSuccess(bloqueado));
  mockBandeja([pendiente({ id: "ho-wipe", action: "wipe", severity: "critical" })]);
  mockDecisiones(approve);
  renderWithProviders(<HandoffsPage />);
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: "Aprobar" }));
  await user.type(screen.getByLabelText("Nota de la decisión (obligatoria)"), "aprobado por dirección");
  await user.type(screen.getByLabelText("Escribe dev-001 para confirmar el borrado"), "dev-001");
  await user.click(screen.getAllByRole("button", { name: "Aprobar" }).at(-1)!);
  expect(await screen.findByText(/Bloqueado por el guardarraíl: la doble llave del wipe está cerrada/)).toBeInTheDocument();
  expect(screen.getByText("wipe_not_allowed")).toBeInTheDocument();
});

test("un 409 dice que ya estaba decidido y refresca la bandeja", async () => {
  const approve = vi.fn((_vars, opts) => opts.onError(new ApiError(409, "conflict", "handoff ho-lock ya decidido (approved)")));
  const refetch = mockBandeja([pendiente()]);
  mockDecisiones(approve);
  renderWithProviders(<HandoffsPage />);
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: "Aprobar" }));
  await user.type(screen.getByLabelText("Nota de la decisión (obligatoria)"), "yo primero");
  await user.click(screen.getAllByRole("button", { name: "Aprobar" }).at(-1)!);
  expect(await screen.findByText("Este handoff ya estaba decidido. La bandeja se ha actualizado.")).toBeInTheDocument();
  expect(refetch).toHaveBeenCalled();
});

test("un viewer lee la bandeja pero no ve los botones de decisión", () => {
  vi.mocked(hooks.useMe).mockReturnValue({ data: { capabilities: ["incident:read"] } } as never);
  mockBandeja([pendiente()]);
  renderWithProviders(<HandoffsPage />);
  expect(screen.getByText("Tablet Campo A1")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Aprobar" })).toBeNull();
  expect(screen.queryByRole("button", { name: "Rechazar" })).toBeNull();
});
