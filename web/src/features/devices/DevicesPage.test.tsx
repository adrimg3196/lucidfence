import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "@/test/render";
import { DevicesPage } from "./DevicesPage";
import * as hooks from "@/api/hooks";

vi.mock("@/api/hooks", async (orig) => ({ ...(await orig<typeof hooks>()), useDevices: vi.fn() }));

const items = [
  { id: "dev-001", name: "Tablet Campo A1", platform: "android", fence_state: "inside", inventory: { assigned_user: "Lucía" }, last_report_at: "2026-09-05T12:00:00Z", risk: { score: 50, severity: "medium" } },
  { id: "dev-004", name: "Portátil Ventas", platform: "macos", fence_state: "outside", inventory: { assigned_user: "Sara" }, last_report_at: "2026-09-05T12:00:00Z", risk: { score: null, severity: "unknown" } },
  { id: "dev-002", name: "Móvil Reparto", platform: "ios", fence_state: "inside", inventory: { assigned_user: "Marco" }, last_report_at: "2026-09-05T12:00:00Z", risk: { score: 10, severity: "low" } },
];

test("lista, filtra por estado y busca con debounce de 250 ms", async () => {
  vi.mocked(hooks.useDevices).mockReturnValue({ data: { items, total: 3 }, isPending: false, error: null } as never);
  renderWithProviders(<DevicesPage />);
  expect(screen.getByRole("link", { name: /Tablet Campo A1/ })).toHaveAttribute("href", "/devices/dev-001");

  const user = userEvent.setup();
  await user.click(screen.getByRole("tab", { name: "dentro" }));
  await waitFor(() => expect(vi.mocked(hooks.useDevices)).toHaveBeenLastCalledWith({ state: "inside", q: "", severity: "" }));

  await user.type(screen.getByRole("searchbox"), "sara");
  // justo tras escribir, el debounce (250 ms) todavía no ha vencido.
  expect(vi.mocked(hooks.useDevices)).not.toHaveBeenLastCalledWith({ state: "inside", q: "sara", severity: "" });
  await waitFor(() => expect(vi.mocked(hooks.useDevices)).toHaveBeenLastCalledWith({ state: "inside", q: "sara", severity: "" }));
});

test("filtra por severidad", async () => {
  vi.mocked(hooks.useDevices).mockReturnValue({ data: { items, total: 3 }, isPending: false, error: null } as never);
  renderWithProviders(<DevicesPage />);
  const user = userEvent.setup();
  await user.selectOptions(screen.getByLabelText("Severidad"), "high");
  await waitFor(() => expect(vi.mocked(hooks.useDevices)).toHaveBeenLastCalledWith({ state: "", q: "", severity: "high" }));
});

test("ordena la columna de riesgo al pulsar su cabecera, dejando los dispositivos sin evaluar al final", async () => {
  vi.mocked(hooks.useDevices).mockReturnValue({ data: { items, total: 3 }, isPending: false, error: null } as never);
  renderWithProviders(<DevicesPage />);
  const user = userEvent.setup();
  const names = () => screen.getAllByRole("row").slice(1).map((r) => within(r).getAllByRole("link")[0].textContent);

  await user.click(screen.getByRole("button", { name: "Riesgo" }));
  expect(names()).toEqual(["Móvil Reparto", "Tablet Campo A1", "Portátil Ventas"]);

  await user.click(screen.getByRole("button", { name: "Riesgo" }));
  expect(names()).toEqual(["Tablet Campo A1", "Móvil Reparto", "Portátil Ventas"]);
});

test("vacío y error", () => {
  vi.mocked(hooks.useDevices).mockReturnValue({ data: { items: [], total: 0 }, isPending: false, error: null } as never);
  const { unmount } = renderWithProviders(<DevicesPage />);
  expect(screen.getByText("Sin dispositivos. Ejecuta un ciclo del motor.")).toBeInTheDocument();
  unmount();
  vi.mocked(hooks.useDevices).mockReturnValue({ data: undefined, isPending: false, error: new Error("caído"), refetch: vi.fn() } as never);
  renderWithProviders(<DevicesPage />);
  expect(screen.getByRole("alert")).toHaveTextContent("caído");
});
