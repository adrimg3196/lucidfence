import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "@/test/render";
import { DeviceActions } from "./DeviceActions";
import * as hooks from "@/api/hooks";
import { ApiError } from "@/api/client";
import { formatDateTime } from "@/lib/format";
import type { Device } from "@/api/hooks";

vi.mock("@/api/hooks", async (orig) => ({ ...(await orig<typeof hooks>()), useMe: vi.fn(), useDeviceAction: vi.fn() }));

const device = {
  id: "dev-001",
  name: "Tablet Campo A1",
  platform: "android",
  compliant: true,
  provider: "simulation",
  location: { source: "gps", observed_at: "2026-09-05T12:00:00Z" },
  network: {},
  inventory: {},
  fence_state: "inside",
  inside_fence: "demo-hq",
  last_inside_fence: "demo-hq",
  route_state: "unassigned",
  risk: { score: null, severity: "unknown", reasons: [], matched_policies: [], provenance: "none", verified: false },
  last_report_at: "2026-09-05T12:00:00Z",
} as unknown as Device;

function mockMe(capabilities: string[]) {
  vi.mocked(hooks.useMe).mockReturnValue({ data: { capabilities } } as never);
}

test("sin capacidad device:action no se renderiza nada", () => {
  mockMe([]);
  vi.mocked(hooks.useDeviceAction).mockReturnValue({ mutate: vi.fn(), isPending: false, data: undefined, error: null } as never);
  const { container } = renderWithProviders(<DeviceActions device={device} />);
  expect(container).toBeEmptyDOMElement();
});

test("lanzar locate llama a useDeviceAction con el cuerpo exacto", async () => {
  mockMe(["device:action"]);
  const mutate = vi.fn();
  vi.mocked(hooks.useDeviceAction).mockReturnValue({ mutate, isPending: false, data: undefined, error: null } as never);
  renderWithProviders(<DeviceActions device={device} />);
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: "Localizar" }));
  expect(mutate).toHaveBeenCalledWith({ id: "dev-001", action: "locate" });
});

test("wipe exige la confirmación por id", async () => {
  mockMe(["device:action"]);
  const mutate = vi.fn();
  vi.mocked(hooks.useDeviceAction).mockReturnValue({ mutate, isPending: false, data: undefined, error: null } as never);
  renderWithProviders(<DeviceActions device={device} />);
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: "Borrado completo" }));
  const confirmButton = screen.getByRole("button", { name: "Confirmar" });
  expect(confirmButton).toBeDisabled();
  const input = screen.getByLabelText("Escribe dev-001 para confirmar.");
  await user.type(input, "algo-que-no-es-el-id");
  expect(confirmButton).toBeDisabled();
  await user.clear(input);
  await user.type(input, "dev-001");
  expect(confirmButton).toBeEnabled();
  await user.click(confirmButton);
  expect(mutate).toHaveBeenCalledWith({ id: "dev-001", action: "wipe" });
});

test("la respuesta con dry_run true dice 'simulada (modo observe)'", () => {
  mockMe(["device:action"]);
  vi.mocked(hooks.useDeviceAction).mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
    error: null,
    data: { adapter: "simulation", ok: true, device_id: "dev-001", device_name: "Tablet Campo A1", action: "locate", dry_run: true, simulated: true, at: "2026-09-05T12:05:00Z" },
  } as never);
  renderWithProviders(<DeviceActions device={device} />);
  expect(screen.getByText("Simulada (modo observe)")).toBeInTheDocument();
});

test("un 409 de cooldown muestra cuándo volverá a estar disponible", () => {
  mockMe(["device:action"]);
  const retryAfter = "2026-09-05T13:00:00Z";
  vi.mocked(hooks.useDeviceAction).mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
    data: undefined,
    error: new ApiError(409, "cooldown", "acción suprimida por cooldown", { retry_after: retryAfter }),
  } as never);
  renderWithProviders(<DeviceActions device={device} />);
  expect(screen.getByRole("alert")).toHaveTextContent(formatDateTime(retryAfter, "es"));
});

// La dirección de set_compliance viaja en los params: es la única acción cuyo
// nombre no dice qué se ejecutó.
function mockResult(over: Record<string, unknown>) {
  vi.mocked(hooks.useDeviceAction).mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
    error: null,
    data: { adapter: "simulation", ok: true, device_id: "dev-001", device_name: "Tablet Campo A1", dry_run: false, simulated: true, at: "2026-09-05T12:05:00Z", ...over },
  } as never);
}

test("el resultado de marcar cumple no se anuncia como incumplimiento", () => {
  mockMe(["device:action"]);
  mockResult({ action: "set_compliance", params: { compliant: true } });
  renderWithProviders(<DeviceActions device={device} />);
  const banner = screen.getByRole("status");
  expect(banner).toHaveTextContent("Marcar cumple");
  expect(banner).not.toHaveTextContent("Marcar incumplimiento");
});

test("el resultado de marcar incumplimiento sí se anuncia como incumplimiento", () => {
  mockMe(["device:action"]);
  mockResult({ action: "set_compliance", params: { compliant: false } });
  renderWithProviders(<DeviceActions device={device} />);
  expect(screen.getByRole("status")).toHaveTextContent("Marcar incumplimiento");
});
