import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "@/test/render";
import { PlaybooksPage } from "./PlaybooksPage";
import * as hooks from "@/api/hooks";

vi.mock("@/api/hooks", async (orig) => ({
  ...(await orig<typeof hooks>()),
  usePlaybooks: vi.fn(),
  useDeletePlaybook: vi.fn(),
  useMe: vi.fn(),
}));

const soar = {
  id: "soar-noncompliant-outside",
  name: "No conforme y fuera de geocerca",
  description: "Bloqueo con aprobación humana y aviso al SOC.",
  when: [{ field: "compliant", op: "eq", value: false }, { field: "fence_state", op: "eq", value: "outside" }],
  actions: [{ action: "lock" }, { action: "notify" }],
  enabled: true,
  severity: "high",
  created_at: "2026-09-06T08:00:00Z",
  updated_at: "2026-09-06T08:00:00Z",
} as hooks.Playbook;

const soloAviso = { ...soar, id: "soar-locate-unknown", name: "Sin ubicación", actions: [{ action: "locate" }], severity: "medium", enabled: false } as hooks.Playbook;

test("lista, marca la aprobación humana y enlaza al editor", () => {
  vi.mocked(hooks.usePlaybooks).mockReturnValue({ data: { items: [soar, soloAviso], total: 2 }, isPending: false, error: null } as never);
  vi.mocked(hooks.useDeletePlaybook).mockReturnValue({ mutate: vi.fn(), isPending: false, error: null } as never);
  vi.mocked(hooks.useMe).mockReturnValue({ data: { capabilities: ["policy:read", "playbook:write"] } } as never);
  renderWithProviders(<PlaybooksPage />);
  expect(screen.getByRole("link", { name: "Nuevo playbook" })).toHaveAttribute("href", "/playbooks/new");
  expect(screen.getByRole("link", { name: "No conforme y fuera de geocerca" })).toHaveAttribute("href", "/playbooks/soar-noncompliant-outside");
  // el lock del primero exige aprobación; el locate del segundo no
  expect(screen.getAllByText("aprobación humana")).toHaveLength(1);
  expect(screen.getByText("Activo")).toBeInTheDocument();
  expect(screen.getByText("Inactivo")).toBeInTheDocument();
});

test("vacío, error y borrado con confirmación", async () => {
  vi.mocked(hooks.useMe).mockReturnValue({ data: { capabilities: ["policy:read", "playbook:write"] } } as never);
  const mutate = vi.fn();
  vi.mocked(hooks.useDeletePlaybook).mockReturnValue({ mutate, isPending: false, error: null } as never);

  vi.mocked(hooks.usePlaybooks).mockReturnValue({ data: { items: [], total: 0 }, isPending: false, error: null } as never);
  const vacio = renderWithProviders(<PlaybooksPage />);
  expect(screen.getByText("Sin playbooks. Crea uno para automatizar la respuesta.")).toBeInTheDocument();
  vacio.unmount();

  const refetch = vi.fn();
  vi.mocked(hooks.usePlaybooks).mockReturnValue({ data: undefined, isPending: false, error: new Error("store caído"), refetch } as never);
  const fallo = renderWithProviders(<PlaybooksPage />);
  expect(screen.getByRole("alert")).toHaveTextContent("store caído");
  fallo.unmount();

  vi.mocked(hooks.usePlaybooks).mockReturnValue({ data: { items: [soar], total: 1 }, isPending: false, error: null } as never);
  renderWithProviders(<PlaybooksPage />);
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: "Eliminar" }));
  expect(await screen.findByText("¿Eliminar el playbook No conforme y fuera de geocerca?")).toBeInTheDocument();
  await user.click(screen.getAllByRole("button", { name: "Eliminar" }).at(-1)!);
  expect(mutate).toHaveBeenCalledWith("soar-noncompliant-outside", expect.anything());
});

test("sin playbook:write no hay botones de escritura", () => {
  vi.mocked(hooks.usePlaybooks).mockReturnValue({ data: { items: [soar], total: 1 }, isPending: false, error: null } as never);
  vi.mocked(hooks.useDeletePlaybook).mockReturnValue({ mutate: vi.fn(), isPending: false, error: null } as never);
  vi.mocked(hooks.useMe).mockReturnValue({ data: { capabilities: ["policy:read"] } } as never);
  renderWithProviders(<PlaybooksPage />);
  expect(screen.queryByRole("link", { name: "Nuevo playbook" })).toBeNull();
  expect(screen.queryByRole("button", { name: "Eliminar" })).toBeNull();
});
