import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "@/test/render";
import { DevicesPage } from "./DevicesPage";
import * as hooks from "@/api/hooks";

vi.mock("@/api/hooks", async (orig) => ({ ...(await orig<typeof hooks>()), useDevices: vi.fn() }));

const items = [
  { id: "dev-001", name: "Tablet Campo A1", platform: "android", fence_state: "inside", inventory: { assigned_user: "Lucía" }, last_report_at: "2026-09-05T12:00:00Z" },
  { id: "dev-004", name: "Portátil Ventas", platform: "macos", fence_state: "outside", inventory: { assigned_user: "Sara" }, last_report_at: "2026-09-05T12:00:00Z" },
];

test("lista, filtra por estado y busca", async () => {
  vi.mocked(hooks.useDevices).mockReturnValue({ data: { items, total: 2 }, isPending: false, error: null } as never);
  renderWithProviders(<DevicesPage />);
  expect(screen.getByRole("link", { name: /Tablet Campo A1/ })).toHaveAttribute("href", "/devices/dev-001");
  const user = userEvent.setup();
  await user.click(screen.getByRole("tab", { name: "dentro" }));
  await waitFor(() => expect(vi.mocked(hooks.useDevices)).toHaveBeenLastCalledWith({ state: "inside", q: "" }));
  await user.type(screen.getByRole("searchbox"), "sara");
  await waitFor(() => expect(vi.mocked(hooks.useDevices)).toHaveBeenLastCalledWith({ state: "inside", q: "sara" }));
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
