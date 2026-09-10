import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "@/test/render";
import { NtfyForm } from "./NtfyForm";
import { api } from "@/api/client";
import type { Settings } from "@/api/hooks";

// useUpdateNtfy es local a NtfyForm.tsx (mismo patrón que useUpdateRisk en
// RiskForm.tsx, M2-C3): no hay un hook exportado que mockear, así que se
// intercepta api.PUT directamente, igual que hooks.m2.test.tsx.
vi.mock("@/api/client", async (orig) => {
  const actual = await orig<typeof import("@/api/client")>();
  return { ...actual, api: { ...actual.api, PUT: vi.fn() } };
});

// jsdom no implementa ResizeObserver; @radix-ui/react-use-size (Switch, T22)
// lo necesita al montar. Ver la misma nota en WebhooksForm.test.tsx:
// src/test/setup.ts queda fuera del alcance de esta tarea.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver ??= ResizeObserverStub;

const settings: Settings = {
  schema_version: 1,
  enforcement: { mode: "observe", live_actions: [], allow_wipe: false, wipe_allowlist: [], action_cooldown_seconds: 3600 },
  webhook: { url: "", format: "native", events: [], enabled: false, secret_set: false },
  ntfy: { url: "https://ntfy.example.com/lucidfence", enabled: true, token_set: true },
  egress: { hosts: [], allow_private: false },
  risk: { shift_zones: {}, zone_risk: {}, off_hours_start: 20, off_hours_end: 7 },
  updated_at: "2026-09-05T12:00:00Z",
};

function setup(s: Settings = settings) {
  vi.mocked(api.PUT).mockResolvedValue({ data: s, response: { ok: true, status: 200 } } as never);
  renderWithProviders(<NtfyForm settings={s} />);
}

test("guardar con el canal activo y una URL https no manda token si no se tocó", async () => {
  setup();
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: "Guardar" }));
  await waitFor(() => expect(api.PUT).toHaveBeenCalledOnce());
  expect(api.PUT).toHaveBeenCalledWith("/api/v1/settings/ntfy", {
    body: { url: "https://ntfy.example.com/lucidfence", enabled: true },
  });
});

test("escribir un token lo incluye en el cuerpo", async () => {
  setup();
  const user = userEvent.setup();
  await user.type(screen.getByLabelText("Token"), "s3cr3t0");
  await user.click(screen.getByRole("button", { name: "Guardar" }));
  await waitFor(() => expect(api.PUT).toHaveBeenCalledOnce());
  expect(api.PUT).toHaveBeenCalledWith("/api/v1/settings/ntfy", {
    body: { url: "https://ntfy.example.com/lucidfence", enabled: true, token: "s3cr3t0" },
  });
});

test("vaciar el token con el botón manda la cadena vacía", async () => {
  setup();
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: "Eliminar" }));
  await user.click(screen.getByRole("button", { name: "Guardar" }));
  await waitFor(() => expect(api.PUT).toHaveBeenCalledOnce());
  expect(api.PUT).toHaveBeenCalledWith("/api/v1/settings/ntfy", {
    body: { url: "https://ntfy.example.com/lucidfence", enabled: true, token: "" },
  });
});

test("activar el canal con la URL vacía muestra el error y no guarda", async () => {
  setup({ ...settings, ntfy: { url: "", enabled: false, token_set: false } });
  const user = userEvent.setup();
  await user.click(screen.getByRole("switch"));
  await user.click(screen.getByRole("button", { name: "Guardar" }));
  expect(await screen.findByRole("alert")).toBeInTheDocument();
  expect(api.PUT).not.toHaveBeenCalled();
});
