import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "@/test/render";
import { PoliciesPage } from "./PoliciesPage";
import { ApiError } from "@/api/client";
import * as hooks from "@/api/hooks";

vi.mock("@/api/hooks", async (orig) => ({ ...(await orig<typeof hooks>()), usePolicies: vi.fn(), useUpdatePolicy: vi.fn(), useMe: vi.fn() }));

const policy = {
  id: "ciso-500",
  name: "Avisar al CISO",
  when: [{ field: "signal:route_state.route_deviation_m", op: "gt", value: 500 }],
  actions: [{ action: "notify", params: { channel: "ciso" } }],
  enabled: true,
  severity: "high",
  created_at: "2026-09-01T10:00:00Z",
  updated_at: "2026-09-01T10:00:00Z",
};

function mockAll(query: unknown, caps: string[] = ["policy:read", "policy:write"], mutate = vi.fn()) {
  vi.mocked(hooks.usePolicies).mockReturnValue(query as never);
  vi.mocked(hooks.useUpdatePolicy).mockReturnValue({ mutate, isPending: false, error: null } as never);
  vi.mocked(hooks.useMe).mockReturnValue({ data: { capabilities: caps } } as never);
  return mutate;
}

test("los cuatro estados: cargando, error, vacío y contenido", async () => {
  // Desviación: el brief montaba aquí un primer render antes de configurar
  // ningún mock ("const cargando = renderWithProviders(...)" seguido de
  // mockAll y un unmount sin ninguna aserción entre medias); con
  // `usePolicies`/`useMe` como `vi.fn()` sin implementar, ese primer render
  // devuelve `undefined` y `me.data` (mismo patrón que `FencesPage.tsx`, sin
  // el `?.` extra) revienta antes de que el `mockAll` que le sigue pueda
  // hacer nada, así que la app real nunca ve ese estado. Se retira y se deja
  // solo el render de "cargando" que sí tiene mock y aserción.
  mockAll({ data: undefined, isPending: true, error: null });
  const a = renderWithProviders(<PoliciesPage />);
  expect(screen.getByRole("status")).toBeInTheDocument();
  a.unmount();

  mockAll({ data: undefined, isPending: false, error: new ApiError(500, "internal", "error interno"), refetch: vi.fn() });
  const b = renderWithProviders(<PoliciesPage />);
  expect(screen.getByRole("alert")).toHaveTextContent("error interno");
  b.unmount();

  mockAll({ data: { items: [], total: 0 }, isPending: false, error: null });
  const c = renderWithProviders(<PoliciesPage />);
  expect(screen.getByText("Sin políticas. Parte de una plantilla o crea la primera.")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Partir de una plantilla" })).toHaveAttribute("href", "/policies/new?plantillas=1");
  c.unmount();

  mockAll({ data: { items: [policy], total: 1 }, isPending: false, error: null });
  renderWithProviders(<PoliciesPage />);
  expect(screen.getByRole("link", { name: "Avisar al CISO" })).toHaveAttribute("href", "/policies/ciso-500");
});

test("el resumen de condiciones se muestra traducido, no como gramática cruda", () => {
  mockAll({ data: { items: [policy], total: 1 }, isPending: false, error: null });
  renderWithProviders(<PoliciesPage />);
  expect(screen.getByText("desviación de ruta mayor que 500")).toBeInTheDocument();
  expect(screen.queryByText(/signal:route_state/)).toBeNull();
  expect(screen.getByText("Notificar")).toBeInTheDocument();
});

test("el interruptor guarda la política entera con enabled invertido", async () => {
  const mutate = mockAll({ data: { items: [policy], total: 1 }, isPending: false, error: null });
  renderWithProviders(<PoliciesPage />);
  const user = userEvent.setup();
  const toggle = screen.getByRole("switch", { name: "Habilitar o deshabilitar Avisar al CISO" });
  expect(toggle).toHaveAttribute("aria-checked", "true");
  await user.click(toggle);
  expect(mutate).toHaveBeenCalledWith({ ...policy, enabled: false }, expect.anything());
});

test("un viewer no ve el botón de crear ni puede usar el interruptor", () => {
  mockAll({ data: { items: [policy], total: 1 }, isPending: false, error: null }, ["policy:read"]);
  renderWithProviders(<PoliciesPage />);
  expect(screen.queryByRole("link", { name: "Nueva política" })).toBeNull();
  expect(screen.getByRole("switch")).toBeDisabled();
});
