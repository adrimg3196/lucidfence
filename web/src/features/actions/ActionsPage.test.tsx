import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "@/test/render";
import { ActionsPage } from "./ActionsPage";
import * as hooks from "@/api/hooks";

vi.mock("@/api/hooks", async (orig) => ({ ...(await orig<typeof hooks>()), useActionsPage: vi.fn() }));

const blocked = {
  adapter: "simulation",
  ok: false,
  device_id: "dev-001",
  device_name: "Tablet Campo A1",
  action: "wipe",
  dry_run: false,
  simulated: true,
  at: "2026-09-05T12:00:00Z",
  trigger: "policy",
  policy_id: "pol-1",
  severity: "critical",
  blocked: true,
  error_type: "wipe_not_allowed",
  error: "el borrado no está permitido con los ajustes de enforcement actuales",
};
const dryRun = {
  adapter: "simulation",
  ok: true,
  device_id: "dev-002",
  device_name: "Portátil Ventas",
  action: "message",
  dry_run: true,
  simulated: true,
  at: "2026-09-05T12:05:00Z",
  trigger: "on_enter",
  fence_id: "demo-hq",
};

test("cargando", () => {
  vi.mocked(hooks.useActionsPage).mockReturnValue({ data: undefined, isPending: true, isFetching: true, error: null, refetch: vi.fn() } as never);
  renderWithProviders(<ActionsPage />);
  expect(screen.getByRole("status")).toBeInTheDocument();
});

test("vacío", () => {
  vi.mocked(hooks.useActionsPage).mockReturnValue({ data: { items: [], next_cursor: "" }, isPending: false, isFetching: false, error: null, refetch: vi.fn() } as never);
  renderWithProviders(<ActionsPage />);
  expect(screen.getByText("Sin acciones registradas.")).toBeInTheDocument();
});

test("error", () => {
  vi.mocked(hooks.useActionsPage).mockReturnValue({ data: undefined, isPending: false, isFetching: false, error: new Error("caído"), refetch: vi.fn() } as never);
  renderWithProviders(<ActionsPage />);
  expect(screen.getByRole("alert")).toHaveTextContent("caído");
});

test("una acción bloqueada muestra el motivo en ámbar y una simulada se etiqueta como tal", () => {
  vi.mocked(hooks.useActionsPage).mockReturnValue({
    data: { items: [blocked, dryRun], next_cursor: "" },
    isPending: false,
    isFetching: false,
    error: null,
    refetch: vi.fn(),
  } as never);
  renderWithProviders(<ActionsPage />);
  const bloqueada = screen.getByText("Bloqueada");
  expect(bloqueada.className).toContain("sev-medium");
  expect(screen.getByText("el borrado no está permitido con los ajustes de enforcement actuales")).toBeInTheDocument();
  expect(screen.getByText("wipe_not_allowed")).toBeInTheDocument();
  expect(screen.getByText("Simulada")).toBeInTheDocument();
});

test("una acción de playbook se etiqueta como playbook, no como transición", async () => {
  const playbook = { ...dryRun, trigger: "playbook", fence_id: undefined, playbook_id: "soar-noncompliant-outside" };
  vi.mocked(hooks.useActionsPage).mockReturnValue({
    data: { items: [playbook], next_cursor: "" },
    isPending: false,
    isFetching: false,
    error: null,
    refetch: vi.fn(),
  } as never);
  renderWithProviders(<ActionsPage />);
  expect(await screen.findByText(/Playbook · soar-noncompliant-outside/)).toBeInTheDocument();
  expect(screen.queryByText(/Transición/)).toBeNull();
});

test("un disparador que la UI no conoce se enseña tal cual", async () => {
  const desconocido = { ...dryRun, trigger: "teletransporte", fence_id: undefined };
  vi.mocked(hooks.useActionsPage).mockReturnValue({
    data: { items: [desconocido], next_cursor: "" },
    isPending: false,
    isFetching: false,
    error: null,
    refetch: vi.fn(),
  } as never);
  renderWithProviders(<ActionsPage />);
  expect(await screen.findByText("teletransporte")).toBeInTheDocument();
  expect(screen.queryByText(/Transición/)).toBeNull();
});

test("cargar más pagina el registro de acciones con el cursor devuelto", async () => {
  const page1 = { items: [dryRun], next_cursor: "c2" };
  const page2 = { items: [blocked], next_cursor: "" };
  vi.mocked(hooks.useActionsPage).mockImplementation(
    ((cursor?: string) =>
      cursor === "c2"
        ? { data: page2, isPending: false, isFetching: false, error: null, refetch: vi.fn() }
        : { data: page1, isPending: false, isFetching: false, error: null, refetch: vi.fn() }) as never,
  );
  renderWithProviders(<ActionsPage />);
  expect(screen.getByText("Portátil Ventas")).toBeInTheDocument();
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: "Cargar más" }));
  await waitFor(() => expect(screen.getByText("Tablet Campo A1")).toBeInTheDocument());
  expect(screen.queryByRole("button", { name: "Cargar más" })).toBeNull();
});
