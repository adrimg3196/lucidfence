import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Routes, Route } from "react-router";
import { renderWithProviders } from "@/test/render";
import { SettingsPage } from "./SettingsPage";
import * as hooks from "@/api/hooks";

vi.mock("@/api/hooks", async (orig) => ({
  ...(await orig<typeof hooks>()),
  useMe: vi.fn(),
  useSettings: vi.fn(),
  useUpdateEnforcement: vi.fn(),
  useUpdateWebhooks: vi.fn(),
  useUpdateEgress: vi.fn(),
  useValidateSettings: vi.fn(),
}));

// jsdom no implementa ResizeObserver; @radix-ui/react-use-size (Switch y
// Checkbox, T22) lo necesita al montar cualquier pestaña con enforcement o
// webhooks. Ver la misma nota en EnforcementForm.test.tsx: src/test/setup.ts
// queda fuera del alcance de esta tarea.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver ??= ResizeObserverStub;

const settings = {
  schema_version: 1,
  enforcement: { mode: "observe", live_actions: [], allow_wipe: false, wipe_allowlist: [], action_cooldown_seconds: 3600 },
  webhook: { url: "", format: "native", events: [], enabled: false, secret_set: false },
  ntfy: { url: "", enabled: false, token_set: false },
  egress: { hosts: [], allow_private: false },
  risk: { shift_zones: {}, zone_risk: {}, off_hours_start: 20, off_hours_end: 7 },
  updated_at: "2026-09-05T12:00:00Z",
} as never;

function mockFormHooks() {
  vi.mocked(hooks.useUpdateEnforcement).mockReturnValue({ mutateAsync: vi.fn(), isPending: false, error: null } as never);
  vi.mocked(hooks.useUpdateWebhooks).mockReturnValue({ mutateAsync: vi.fn(), isPending: false, error: null } as never);
  vi.mocked(hooks.useUpdateEgress).mockReturnValue({ mutateAsync: vi.fn(), isPending: false, isSuccess: false, error: null } as never);
  vi.mocked(hooks.useValidateSettings).mockReturnValue({ mutate: vi.fn(), isPending: false, data: undefined, error: null } as never);
}

function tree() {
  return (
    <Routes>
      <Route path="/settings" element={<SettingsPage />} />
      <Route path="/" element={<p>HOME</p>} />
    </Routes>
  );
}

test("cargando", () => {
  vi.mocked(hooks.useMe).mockReturnValue({ data: { capabilities: ["engine:config"] }, isPending: true } as never);
  vi.mocked(hooks.useSettings).mockReturnValue({ data: undefined, isPending: true, error: null } as never);
  renderWithProviders(tree(), { route: "/settings" });
  expect(screen.getByRole("status")).toBeInTheDocument();
});

test("error", () => {
  vi.mocked(hooks.useMe).mockReturnValue({ data: { capabilities: ["engine:config"] }, isPending: false } as never);
  vi.mocked(hooks.useSettings).mockReturnValue({ data: undefined, isPending: false, error: new Error("caído"), refetch: vi.fn() } as never);
  renderWithProviders(tree(), { route: "/settings" });
  expect(screen.getByRole("alert")).toHaveTextContent("caído");
});

test("un rol sin engine:config no ve la vista y el router redirige", () => {
  vi.mocked(hooks.useMe).mockReturnValue({ data: { capabilities: ["device:read"] }, isPending: false } as never);
  vi.mocked(hooks.useSettings).mockReturnValue({ data: settings, isPending: false, error: null } as never);
  renderWithProviders(tree(), { route: "/settings" });
  expect(screen.getByText("HOME")).toBeInTheDocument();
  expect(screen.queryByText("Ajustes")).toBeNull();
});

test("con engine:config muestra las cinco pestañas", () => {
  mockFormHooks();
  vi.mocked(hooks.useMe).mockReturnValue({ data: { capabilities: ["engine:config"] }, isPending: false } as never);
  vi.mocked(hooks.useSettings).mockReturnValue({ data: settings, isPending: false, error: null } as never);
  renderWithProviders(tree(), { route: "/settings" });
  expect(screen.getByRole("heading", { name: "Ajustes" })).toBeInTheDocument();
  expect(screen.getByRole("tab", { name: "Enforcement" })).toBeInTheDocument();
  expect(screen.getByRole("tab", { name: "Notificaciones" })).toBeInTheDocument();
  expect(screen.getByRole("tab", { name: "ntfy" })).toBeInTheDocument();
  expect(screen.getByRole("tab", { name: "Salida de red" })).toBeInTheDocument();
  expect(screen.getByRole("tab", { name: "Riesgo" })).toBeInTheDocument();
});

// M2-C3: la pestaña de riesgo (shift_zones/zone_risk contra PUT
// /api/v1/settings/risk) valida con zod igual que las otras tres; esta tarea
// no tiene permitido crear RiskForm.test.tsx, así que su validación se
// comprueba aquí, a través de la pestaña real dentro de SettingsPage.
test("una fila de riesgo por geocerca sin geocerca muestra el error en la pestaña de riesgo", async () => {
  mockFormHooks();
  vi.mocked(hooks.useMe).mockReturnValue({ data: { capabilities: ["engine:config"] }, isPending: false } as never);
  vi.mocked(hooks.useSettings).mockReturnValue({ data: settings, isPending: false, error: null } as never);
  renderWithProviders(tree(), { route: "/settings" });
  const user = userEvent.setup();
  await user.click(screen.getByRole("tab", { name: "Riesgo" }));
  const addButtons = screen.getAllByRole("button", { name: "Añadir" });
  await user.click(addButtons[addButtons.length - 1]);
  await user.click(screen.getByRole("button", { name: "Guardar" }));
  expect(await screen.findByRole("alert")).toBeInTheDocument();
});
