import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "@/test/render";
import { WebhooksForm } from "./WebhooksForm";
import * as hooks from "@/api/hooks";
import type { Settings } from "@/api/hooks";

vi.mock("@/api/hooks", async (orig) => ({ ...(await orig<typeof hooks>()), useUpdateWebhooks: vi.fn() }));

// jsdom no implementa ResizeObserver; @radix-ui/react-use-size (Switch y
// Checkbox, T22) lo necesita al montar. Ver la misma nota en
// EnforcementForm.test.tsx: src/test/setup.ts queda fuera del alcance de
// esta tarea.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver ??= ResizeObserverStub;

const settings: Settings = {
  schema_version: 1,
  enforcement: { mode: "observe", live_actions: [], allow_wipe: false, wipe_allowlist: [], action_cooldown_seconds: 3600 },
  webhook: { url: "https://hooks.example.com/lucidfence", format: "native", events: ["incident.opened"], enabled: true, secret_set: true },
  ntfy: { url: "", enabled: false, token_set: false },
  egress: { hosts: [], allow_private: false },
  risk: { shift_zones: {}, zone_risk: {}, off_hours_start: 20, off_hours_end: 7 },
  updated_at: "2026-09-05T12:00:00Z",
};

function setup() {
  const mutateAsync = vi.fn().mockResolvedValue(settings.webhook);
  vi.mocked(hooks.useUpdateWebhooks).mockReturnValue({ mutateAsync, isPending: false, error: null } as never);
  renderWithProviders(<WebhooksForm settings={settings} />);
  return mutateAsync;
}

test("el secreto nunca se rellena con el valor del servidor aunque secret_set sea true", () => {
  setup();
  expect(screen.getByLabelText("Secreto de firma")).toHaveValue("");
  expect(screen.getByText("Configurado")).toBeInTheDocument();
});

test("guardar sin tocar el secreto no lo envía", async () => {
  const mutateAsync = setup();
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: "Guardar" }));
  await waitFor(() => expect(mutateAsync).toHaveBeenCalledOnce());
  expect(mutateAsync.mock.calls[0][0]).not.toHaveProperty("secret");
});

test("vaciar el secreto explícitamente envía la cadena vacía", async () => {
  const mutateAsync = setup();
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: "Eliminar" }));
  await user.click(screen.getByRole("button", { name: "Guardar" }));
  await waitFor(() => expect(mutateAsync).toHaveBeenCalledOnce());
  expect(mutateAsync.mock.calls[0][0]).toMatchObject({ secret: "" });
});

test("escribir un secreto nuevo lo envía en claro", async () => {
  const mutateAsync = setup();
  const user = userEvent.setup();
  await user.type(screen.getByLabelText("Secreto de firma"), "s3cr3t0");
  await user.click(screen.getByRole("button", { name: "Guardar" }));
  await waitFor(() => expect(mutateAsync).toHaveBeenCalledOnce());
  expect(mutateAsync.mock.calls[0][0]).toMatchObject({ secret: "s3cr3t0" });
});

test("elegir OCSF avisa de que el evento no viaja en el sobre nativo", async () => {
  setup();
  const user = userEvent.setup();
  await user.selectOptions(screen.getByLabelText("Formato"), "ocsf");
  expect(screen.getByText(/sobre nativo/)).toBeInTheDocument();
});
