import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Routes, Route } from "react-router";
import { renderWithProviders } from "@/test/render";
import { PolicyEditorPage } from "./PolicyEditorPage";
import * as hooks from "@/api/hooks";

const navigate = vi.fn();
vi.mock("react-router", async (orig) => ({ ...(await orig<typeof import("react-router")>()), useNavigate: () => navigate }));
vi.mock("@/api/hooks", async (orig) => ({
  ...(await orig<typeof hooks>()),
  usePolicy: vi.fn(),
  usePolicyFields: vi.fn(),
  usePolicyTemplates: vi.fn(),
  useCreatePolicy: vi.fn(),
  useUpdatePolicy: vi.fn(),
  useReplayPolicy: vi.fn(),
}));

// El catálogo del servidor es deliberadamente corto y no contiene "platform":
// si el desplegable lo ofreciera, la lista sería local y el test lo canta.
const catalog = { fields: ["fence_state", "route_deviation_m"], ops: ["eq", "gt"] };

const template = {
  id: "tpl-ciso-deviation-500",
  name: "Avisar al CISO si la desviación supera 500 m",
  description: "Desviación de ruta mayor de 500 m: notifica al CISO sin tocar el dispositivo.",
  when: [{ field: "signal:route_state.route_deviation_m", op: "gt", value: 500 }],
  actions: [{ action: "notify", params: { channel: "ciso", msg: "Comercial con desviación de ruta mayor de 500 m" } }],
  enabled: true,
  severity: "high",
  source: "template",
  template_id: "tpl-ciso-deviation-500",
  created_at: "",
  updated_at: "",
};

function mocks(opts: { existing?: unknown; create?: ReturnType<typeof vi.fn>; update?: ReturnType<typeof vi.fn> } = {}) {
  vi.mocked(hooks.usePolicy).mockReturnValue({ data: opts.existing, isPending: false, error: null } as never);
  vi.mocked(hooks.usePolicyFields).mockReturnValue({ data: catalog, isPending: false, error: null } as never);
  vi.mocked(hooks.usePolicyTemplates).mockReturnValue({ data: { items: [template], total: 1 }, isPending: false, error: null } as never);
  vi.mocked(hooks.useCreatePolicy).mockReturnValue({ mutateAsync: opts.create ?? vi.fn().mockResolvedValue({}), isPending: false, error: null } as never);
  vi.mocked(hooks.useUpdatePolicy).mockReturnValue({ mutateAsync: opts.update ?? vi.fn().mockResolvedValue({}), isPending: false, error: null } as never);
  vi.mocked(hooks.useReplayPolicy).mockReturnValue({ mutate: vi.fn(), data: undefined, isPending: false, error: null } as never);
}

function render(route: string) {
  return renderWithProviders(
    <Routes>
      <Route path="/policies/new" element={<PolicyEditorPage />} />
      <Route path="/policies/:id" element={<PolicyEditorPage />} />
    </Routes>,
    { route },
  );
}

test("el desplegable de campos viene del catálogo del servidor, no de una lista local", async () => {
  mocks();
  render("/policies/new");
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: "Añadir condición" }));
  expect(screen.getByRole("option", { name: "estado de geocerca" })).toBeInTheDocument();
  expect(screen.getByRole("option", { name: "desviación de ruta" })).toBeInTheDocument();
  expect(screen.queryByRole("option", { name: "plataforma" })).toBeNull();
  expect(screen.getByRole("option", { name: "es" })).toBeInTheDocument();
  expect(screen.getByRole("option", { name: "mayor que" })).toBeInTheDocument();
  expect(screen.queryByRole("option", { name: "contiene" })).toBeNull();
});

test("añadir y quitar filas de condición", async () => {
  mocks();
  render("/policies/new");
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: "Añadir condición" }));
  await user.click(screen.getByRole("button", { name: "Añadir condición" }));
  expect(screen.getAllByLabelText("Campo")).toHaveLength(2);
  await user.click(screen.getAllByRole("button", { name: "Quitar condición" })[0]);
  expect(screen.getAllByLabelText("Campo")).toHaveLength(1);
});

test("un valor no numérico en un campo numérico muestra el error debajo del campo", async () => {
  const create = vi.fn().mockResolvedValue({});
  mocks({ create });
  render("/policies/new");
  const user = userEvent.setup();
  await user.type(screen.getByLabelText("Nombre"), "Desviación");
  await user.click(screen.getByRole("button", { name: "Añadir condición" }));
  await user.selectOptions(screen.getByLabelText("Campo"), "route_deviation_m");
  await user.type(screen.getByLabelText("Valor"), "muchos");
  await user.click(screen.getByRole("button", { name: "Guardar" }));
  expect(await screen.findByText("Debe ser un número")).toBeInTheDocument();
  expect(screen.getByLabelText("Valor")).toHaveAttribute("aria-invalid", "true");
  expect(create).not.toHaveBeenCalled();
});

test("guardar llama a useCreatePolicy con el cuerpo exacto", async () => {
  const create = vi.fn().mockResolvedValue({});
  mocks({ create });
  render("/policies/new");
  const user = userEvent.setup();
  await user.type(screen.getByLabelText("Nombre"), "Avisar fuera de geocerca");
  expect(screen.getByLabelText("Identificador")).toHaveValue("avisar-fuera-de-geocerca");
  await user.click(screen.getByRole("button", { name: "Añadir condición" }));
  await user.selectOptions(screen.getByLabelText("Campo"), "fence_state");
  await user.type(screen.getByLabelText("Valor"), "outside");
  await user.click(screen.getByRole("button", { name: "Añadir acción" }));
  await user.selectOptions(screen.getByLabelText("Acción"), "message");
  await user.type(screen.getByLabelText("Texto"), "Vuelve a la zona");
  await user.selectOptions(screen.getByLabelText("Severidad"), "high");
  await user.click(screen.getByRole("button", { name: "Guardar" }));
  await waitFor(() => expect(create).toHaveBeenCalled());
  expect(create.mock.calls[0][0]).toEqual({
    id: "avisar-fuera-de-geocerca",
    name: "Avisar fuera de geocerca",
    when: [{ field: "fence_state", op: "eq", value: "outside" }],
    actions: [{ action: "message", params: { text: "Vuelve a la zona" } }],
    enabled: true,
    severity: "high",
    created_at: expect.any(String),
    updated_at: expect.any(String),
  });
  expect(navigate).toHaveBeenCalledWith("/policies");
});

test("editar preserva created_at y solo cambia updated_at", async () => {
  const update = vi.fn().mockResolvedValue({});
  const existing = { ...template, id: "ciso-500", source: "manual", template_id: "", created_at: "2026-01-02T03:04:05Z", updated_at: "2026-01-02T03:04:05Z" };
  mocks({ existing, update });
  render("/policies/ciso-500");
  const user = userEvent.setup();
  await waitFor(() => expect(screen.getByLabelText("Nombre")).toHaveValue(existing.name));
  await user.click(screen.getByRole("button", { name: "Guardar" }));
  await waitFor(() => expect(update).toHaveBeenCalled());
  const sent = update.mock.calls[0][0];
  expect(sent.created_at).toBe("2026-01-02T03:04:05Z");
  expect(sent.updated_at).not.toBe("2026-01-02T03:04:05Z");
  expect(sent.actions).toEqual(existing.actions);
});

test("elegir una plantilla rellena el formulario y deja source template", async () => {
  const create = vi.fn().mockResolvedValue({});
  mocks({ create });
  render("/policies/new?plantillas=1");
  const user = userEvent.setup();
  expect(await screen.findByText("Avisar al CISO si la desviación supera 500 m")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Usar" }));
  await waitFor(() => expect(screen.getByLabelText("Nombre")).toHaveValue(template.name));
  expect(screen.getByLabelText("Identificador")).toHaveValue("tpl-ciso-deviation-500");
  expect(screen.getByLabelText("Valor")).toHaveValue("500");
  await user.click(screen.getByRole("button", { name: "Guardar" }));
  await waitFor(() => expect(create).toHaveBeenCalled());
  expect(create.mock.calls[0][0]).toMatchObject({ source: "template", template_id: "tpl-ciso-deviation-500", severity: "high", when: [{ field: "signal:route_state.route_deviation_m", op: "gt", value: 500 }] });
});
