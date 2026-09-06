import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "@/test/render";
import { FencesPage } from "./FencesPage";
import { ApiError } from "@/api/client";
import * as hooks from "@/api/hooks";

vi.mock("@/api/hooks", async (orig) => ({ ...(await orig<typeof hooks>()), useFences: vi.fn(), useDeleteFence: vi.fn(), useMe: vi.fn() }));

test("lista, permisos y borrado con confirmación", async () => {
  const mutate = vi.fn();
  vi.mocked(hooks.useFences).mockReturnValue({ data: { items: [{ id: "demo-hq", name: "Demo HQ", kind: "circle", actions: [{}, {}] }], total: 1 }, isPending: false, error: null } as never);
  vi.mocked(hooks.useDeleteFence).mockReturnValue({ mutate, isPending: false, error: null } as never);
  vi.mocked(hooks.useMe).mockReturnValue({ data: { capabilities: ["fence:write", "fence:delete"] } } as never);
  renderWithProviders(<FencesPage />);
  expect(screen.getByRole("link", { name: "Nueva geocerca" })).toHaveAttribute("href", "/fences/new");
  expect(screen.getByRole("link", { name: "Demo HQ" })).toHaveAttribute("href", "/fences/demo-hq");
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: "Eliminar" }));
  expect(await screen.findByText("¿Eliminar la geocerca Demo HQ?")).toBeInTheDocument();
  await user.click(screen.getAllByRole("button", { name: "Eliminar" }).at(-1)!);
  expect(mutate).toHaveBeenCalledWith("demo-hq", expect.anything());
});

// M1-R27 (C13): un borrado rechazado por el servidor (403 sin capacidad, o
// cualquier otro error del store) cerraba el diálogo sin avisar; la fila
// seguía en la tabla y parecía que el botón no había hecho nada.
test("un borrado fallido muestra el error real en la página (M1-R27, C13)", async () => {
  const mutate = vi.fn();
  const error = new ApiError(403, "forbidden", "sin permiso");
  vi.mocked(hooks.useFences).mockReturnValue({ data: { items: [{ id: "demo-hq", name: "Demo HQ", kind: "circle", actions: [] }], total: 1 }, isPending: false, error: null } as never);
  vi.mocked(hooks.useDeleteFence).mockReturnValue({ mutate, isPending: false, error } as never);
  vi.mocked(hooks.useMe).mockReturnValue({ data: { capabilities: ["fence:write", "fence:delete"] } } as never);
  renderWithProviders(<FencesPage />);
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: "Eliminar" }));
  await user.click(screen.getAllByRole("button", { name: "Eliminar" }).at(-1)!);
  expect(mutate).toHaveBeenCalledWith("demo-hq", expect.anything());
  const alerts = screen.getAllByRole("alert");
  expect(alerts.some((a) => a.textContent?.includes("sin permiso"))).toBe(true);
});

// M1-R27 (C13): mientras la mutación está en curso, el botón de confirmar no
// debe permitir disparar un segundo borrado.
test("el botón de confirmar borrado se deshabilita mientras la mutación está en curso (M1-R27, C13)", async () => {
  vi.mocked(hooks.useFences).mockReturnValue({ data: { items: [{ id: "demo-hq", name: "Demo HQ", kind: "circle", actions: [] }], total: 1 }, isPending: false, error: null } as never);
  vi.mocked(hooks.useDeleteFence).mockReturnValue({ mutate: vi.fn(), isPending: true, error: null } as never);
  vi.mocked(hooks.useMe).mockReturnValue({ data: { capabilities: ["fence:write", "fence:delete"] } } as never);
  renderWithProviders(<FencesPage />);
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: "Eliminar" }));
  expect(screen.getAllByRole("button", { name: "Eliminar" }).at(-1)).toBeDisabled();
});

test("sin permisos no hay botones y vacío tiene acción", () => {
  vi.mocked(hooks.useFences).mockReturnValue({ data: { items: [], total: 0 }, isPending: false, error: null } as never);
  vi.mocked(hooks.useDeleteFence).mockReturnValue({ mutate: vi.fn(), isPending: false } as never);
  vi.mocked(hooks.useMe).mockReturnValue({ data: { capabilities: ["fence:read"] } } as never);
  renderWithProviders(<FencesPage />);
  expect(screen.getByText("Sin geocercas. Crea la primera.")).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "Nueva geocerca" })).toBeNull();
});
