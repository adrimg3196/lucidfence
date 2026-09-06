import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Routes, Route } from "react-router";
import { renderWithProviders } from "@/test/render";
import { FenceEditorPage } from "./FenceEditorPage";
import * as hooks from "@/api/hooks";

const navigate = vi.fn();
vi.mock("react-router", async (orig) => ({ ...(await orig<typeof import("react-router")>()), useNavigate: () => navigate }));
vi.mock("@/api/hooks", async (orig) => ({ ...(await orig<typeof hooks>()), useFence: vi.fn(), useCreateFence: vi.fn(), useUpdateFence: vi.fn() }));

test("crea un círculo con una acción al entrar", async () => {
  const mutateAsync = vi.fn().mockResolvedValue({});
  vi.mocked(hooks.useFence).mockReturnValue({ data: undefined, isPending: false, error: null } as never);
  vi.mocked(hooks.useCreateFence).mockReturnValue({ mutateAsync, isPending: false, error: null } as never);
  vi.mocked(hooks.useUpdateFence).mockReturnValue({ mutateAsync: vi.fn(), isPending: false, error: null } as never);
  renderWithProviders(
    <Routes>
      <Route path="/fences/new" element={<FenceEditorPage />} />
    </Routes>,
    { route: "/fences/new" },
  );
  const user = userEvent.setup();
  await user.type(screen.getByLabelText("Nombre"), "Oficina Norte");
  expect(screen.getByLabelText("Identificador")).toHaveValue("oficina-norte");
  await user.clear(screen.getByLabelText("Latitud"));
  await user.type(screen.getByLabelText("Latitud"), "40.45");
  await user.clear(screen.getByLabelText("Longitud"));
  await user.type(screen.getByLabelText("Longitud"), "-3.7");
  await user.clear(screen.getByLabelText("Radio (m)"));
  await user.type(screen.getByLabelText("Radio (m)"), "250");
  await user.click(screen.getByRole("button", { name: "Añadir acción" }));
  await user.type(screen.getByLabelText("Texto"), "Bienvenido");
  await user.click(screen.getByRole("button", { name: "Guardar" }));
  await waitFor(() => expect(mutateAsync).toHaveBeenCalled());
  expect(mutateAsync.mock.calls[0][0]).toMatchObject({ id: "oficina-norte", kind: "circle", center: { lat: 40.45, lng: -3.7 }, radius_m: 250, actions: [{ action: "message", when: "on_enter", params: { text: "Bienvenido" } }] });
  expect(navigate).toHaveBeenCalledWith("/fences");
});

// Fix round 1 (M1-R25, punto 3): quitar una acción debe eliminar su fila del
// formulario y no debe aparecer en el payload enviado al guardar.
test("quitar una acción la elimina del formulario y del payload enviado", async () => {
  const mutateAsync = vi.fn().mockResolvedValue({});
  vi.mocked(hooks.useFence).mockReturnValue({ data: undefined, isPending: false, error: null } as never);
  vi.mocked(hooks.useCreateFence).mockReturnValue({ mutateAsync, isPending: false, error: null } as never);
  vi.mocked(hooks.useUpdateFence).mockReturnValue({ mutateAsync: vi.fn(), isPending: false, error: null } as never);
  renderWithProviders(
    <Routes>
      <Route path="/fences/new" element={<FenceEditorPage />} />
    </Routes>,
    { route: "/fences/new" },
  );
  const user = userEvent.setup();
  await user.type(screen.getByLabelText("Nombre"), "Oficina Norte");
  await user.click(screen.getByRole("button", { name: "Añadir acción" }));
  await user.click(screen.getByRole("button", { name: "Añadir acción" }));
  const textInputs = screen.getAllByLabelText("Texto");
  await user.type(textInputs[0], "Primera");
  await user.type(textInputs[1], "Segunda");
  await user.click(screen.getAllByRole("button", { name: "Eliminar" })[0]);
  expect(screen.getAllByLabelText("Texto")).toHaveLength(1);
  await user.click(screen.getByRole("button", { name: "Guardar" }));
  await waitFor(() => expect(mutateAsync).toHaveBeenCalled());
  expect(mutateAsync.mock.calls[0][0].actions).toEqual([{ action: "message", when: "on_enter", enabled: true, params: { text: "Segunda" } }]);
});

// Fix round 1 (M1-R25, punto 1): PUT reemplaza el registro completo; editar
// sin tocar los campos de rules no debe borrarlas en el payload enviado.
test("editar una geocerca con rules y guardar sin tocarlas conserva las rules originales", async () => {
  const existing = {
    id: "hq",
    name: "HQ",
    kind: "circle" as const,
    center: { lat: 40.42, lng: -3.71 },
    radius_m: 300,
    rules: { violation_interval_cycles: 3, dwell_seconds: 60 },
    actions: [],
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  };
  const mutateAsync = vi.fn().mockResolvedValue({});
  vi.mocked(hooks.useFence).mockReturnValue({ data: existing, isPending: false, error: null } as never);
  vi.mocked(hooks.useCreateFence).mockReturnValue({ mutateAsync: vi.fn(), isPending: false, error: null } as never);
  vi.mocked(hooks.useUpdateFence).mockReturnValue({ mutateAsync, isPending: false, error: null } as never);
  renderWithProviders(
    <Routes>
      <Route path="/fences/:id" element={<FenceEditorPage />} />
    </Routes>,
    { route: "/fences/hq" },
  );
  const user = userEvent.setup();
  await waitFor(() => expect(screen.getByLabelText("Nombre")).toHaveValue("HQ"));
  await user.click(screen.getByRole("button", { name: "Guardar" }));
  await waitFor(() => expect(mutateAsync).toHaveBeenCalled());
  expect(mutateAsync.mock.calls[0][0]).toMatchObject({ rules: { violation_interval_cycles: 3, dwell_seconds: 60 } });
});

test("evita el id reservado 'none' al generar el slug desde el nombre (M1-R12)", async () => {
  vi.mocked(hooks.useFence).mockReturnValue({ data: undefined, isPending: false, error: null } as never);
  vi.mocked(hooks.useCreateFence).mockReturnValue({ mutateAsync: vi.fn(), isPending: false, error: null } as never);
  vi.mocked(hooks.useUpdateFence).mockReturnValue({ mutateAsync: vi.fn(), isPending: false, error: null } as never);
  renderWithProviders(
    <Routes>
      <Route path="/fences/new" element={<FenceEditorPage />} />
    </Routes>,
    { route: "/fences/new" },
  );
  const user = userEvent.setup();
  await user.type(screen.getByLabelText("Nombre"), "None");
  expect(screen.getByLabelText("Identificador")).not.toHaveValue("none");
});
