import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "@/test/render";
import { EnforcementForm } from "./EnforcementForm";
import * as hooks from "@/api/hooks";
import type { Settings } from "@/api/hooks";

vi.mock("@/api/hooks", async (orig) => ({ ...(await orig<typeof hooks>()), useUpdateEnforcement: vi.fn() }));

// jsdom no implementa ResizeObserver; @radix-ui/react-use-size (Switch y
// Checkbox, T22) lo necesita para medir su miniatura al montar. Ningún test
// anterior a T26 llegó a renderizar estos dos componentes (grep confirma que
// nada fuera de settings/ los usa todavía), así que src/test/setup.ts nunca
// necesitó el stub; se declara aquí, local a este fichero, en vez de tocar
// un fichero compartido fuera del alcance de esta tarea.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver ??= ResizeObserverStub;

// Tipado explícitamente contra Settings (no `as never`, spuriamente
// habitual en fixtures de test): así la propiedad `.enforcement` que usan
// los tests de abajo compila, y el literal ya encaja letra a letra con la
// forma real del contrato de T21.
const settings: Settings = {
  schema_version: 1,
  enforcement: { mode: "observe", live_actions: [], allow_wipe: false, wipe_allowlist: [], action_cooldown_seconds: 3600 },
  webhook: { url: "", format: "native", events: [], enabled: false, secret_set: false },
  ntfy: { url: "", enabled: false, token_set: false },
  egress: { hosts: [], allow_private: false },
  risk: { shift_zones: {}, zone_risk: {}, off_hours_start: 20, off_hours_end: 7 },
  updated_at: "2026-09-05T12:00:00Z",
};

function setup() {
  const mutateAsync = vi.fn().mockResolvedValue(settings.enforcement);
  vi.mocked(hooks.useUpdateEnforcement).mockReturnValue({ mutateAsync, isPending: false, error: null } as never);
  renderWithProviders(<EnforcementForm settings={settings} />);
  return mutateAsync;
}

test("en observe las llaves de wipe están deshabilitadas", () => {
  setup();
  expect(screen.getByRole("checkbox", { name: "Permitir borrado completo" })).toBeDisabled();
});

test("pasar a enforce habilita las llaves de wipe y muestra el aviso", async () => {
  setup();
  const user = userEvent.setup();
  expect(screen.queryByText(/tocarán dispositivos reales/)).toBeNull();
  await user.click(screen.getByRole("switch"));
  expect(screen.getByRole("checkbox", { name: "Permitir borrado completo" })).not.toBeDisabled();
  expect(screen.getByText(/tocarán dispositivos reales/)).toBeInTheDocument();
});

test("guardar envía live_actions como lista del enum", async () => {
  const mutateAsync = setup();
  const user = userEvent.setup();
  await user.click(screen.getByRole("checkbox", { name: "Bloquear" }));
  await user.click(screen.getByRole("checkbox", { name: "Localizar" }));
  await user.click(screen.getByRole("button", { name: "Guardar" }));
  await waitFor(() => expect(mutateAsync).toHaveBeenCalledOnce());
  expect(mutateAsync).toHaveBeenCalledWith(expect.objectContaining({ live_actions: ["lock", "locate"] }));
});

test("un wipe_allowlist con un id vacío muestra el error", async () => {
  setup();
  const user = userEvent.setup();
  await user.click(screen.getByRole("switch"));
  await user.click(screen.getByRole("button", { name: "Añadir" }));
  await user.click(screen.getByRole("button", { name: "Guardar" }));
  expect(await screen.findByRole("alert")).toBeInTheDocument();
});

test("vaciar el enfriamiento no lo guarda como 0: muestra el error", async () => {
  const mutateAsync = setup();
  const user = userEvent.setup();
  await user.clear(screen.getByLabelText("Enfriamiento entre acciones (s)"));
  await user.click(screen.getByRole("button", { name: "Guardar" }));
  expect(await screen.findByRole("alert")).toBeInTheDocument();
  expect(mutateAsync).not.toHaveBeenCalled();
});
