import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "@/test/render";
import { FencesPage } from "./FencesPage";
import * as hooks from "@/api/hooks";

vi.mock("@/api/hooks", async (orig) => ({ ...(await orig<typeof hooks>()), useFences: vi.fn(), useDeleteFence: vi.fn(), useMe: vi.fn() }));

test("lista, permisos y borrado con confirmación", async () => {
  const mutate = vi.fn();
  vi.mocked(hooks.useFences).mockReturnValue({ data: { items: [{ id: "demo-hq", name: "Demo HQ", kind: "circle", actions: [{}, {}] }], total: 1 }, isPending: false, error: null } as never);
  vi.mocked(hooks.useDeleteFence).mockReturnValue({ mutate, isPending: false } as never);
  vi.mocked(hooks.useMe).mockReturnValue({ data: { capabilities: ["fence:write", "fence:delete"] } } as never);
  renderWithProviders(<FencesPage />);
  expect(screen.getByRole("link", { name: "Nueva geocerca" })).toHaveAttribute("href", "/fences/new");
  expect(screen.getByRole("link", { name: "Demo HQ" })).toHaveAttribute("href", "/fences/demo-hq");
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: "Eliminar" }));
  expect(await screen.findByText("¿Eliminar la geocerca Demo HQ?")).toBeInTheDocument();
  await user.click(screen.getAllByRole("button", { name: "Eliminar" }).at(-1)!);
  expect(mutate).toHaveBeenCalledWith("demo-hq");
});

test("sin permisos no hay botones y vacío tiene acción", () => {
  vi.mocked(hooks.useFences).mockReturnValue({ data: { items: [], total: 0 }, isPending: false, error: null } as never);
  vi.mocked(hooks.useDeleteFence).mockReturnValue({ mutate: vi.fn(), isPending: false } as never);
  vi.mocked(hooks.useMe).mockReturnValue({ data: { capabilities: ["fence:read"] } } as never);
  renderWithProviders(<FencesPage />);
  expect(screen.getByText("Sin geocercas. Crea la primera.")).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "Nueva geocerca" })).toBeNull();
});
