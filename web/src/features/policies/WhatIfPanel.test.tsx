import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Routes, Route } from "react-router";
import { renderWithProviders } from "@/test/render";
import { WhatIfPanel } from "./WhatIfPanel";
import { PolicyEditorPage } from "./PolicyEditorPage";
import * as hooks from "@/api/hooks";

vi.mock("react-router", async (orig) => ({ ...(await orig<typeof import("react-router")>()), useNavigate: () => vi.fn() }));
vi.mock("@/api/hooks", async (orig) => ({
  ...(await orig<typeof hooks>()),
  usePolicy: vi.fn(),
  usePolicyFields: vi.fn(),
  usePolicyTemplates: vi.fn(),
  useCreatePolicy: vi.fn(),
  useUpdatePolicy: vi.fn(),
  useReplayPolicy: vi.fn(),
}));

const policy = {
  id: "pol-lock-outside",
  name: "Bloquear al salir",
  when: [{ field: "fence_state", op: "eq", value: "outside" }],
  actions: [{ action: "lock", params: {} }],
  enabled: true,
  severity: "high",
  created_at: "2026-09-01T10:00:00Z",
  updated_at: "2026-09-01T10:00:00Z",
};

// Caso dorado portado de legacy/tests/test_policy_replay.py: dos disparos de
// un solo dispositivo, la ventana completa del trail y cada ejemplo con su
// razón (evidence gate).
const result = {
  policy_id: "pol-lock-outside",
  points_evaluated: 5,
  devices_evaluated: 2,
  firings: 2,
  by_device: { "dev-a": 2 },
  by_action: { lock: 2 },
  approximation: false,
  notes: [],
  from: "2026-08-10T09:00:00Z",
  to: "2026-08-10T23:30:00Z",
  samples: [
    { at: "2026-08-10T10:00:00Z", device_id: "dev-a", device_name: "Portátil Ventas", fence_state: "outside", score: 62, severity: "high", reasons: ["fuera de la geocerca permitida"] },
    { at: "2026-08-10T23:30:00Z", device_id: "dev-a", device_name: "Portátil Ventas", fence_state: "outside", score: 71, severity: "high", reasons: ["fuera de la geocerca permitida", "fuera de horario"] },
  ],
};

function mockReplay(over: Partial<{ data: unknown; isPending: boolean; error: unknown }> = {}) {
  const mutate = vi.fn((_body, opts) => opts?.onSuccess?.(over.data ?? result));
  vi.mocked(hooks.useReplayPolicy).mockReturnValue({ mutate, data: over.data, isPending: over.isPending ?? false, error: over.error ?? null } as never);
  return mutate;
}

test("ejecutar el what-if muestra disparos, dispositivos y ejemplos con sus razones", async () => {
  const mutate = mockReplay();
  // Desviación: el brief usaba `rerender(<WhatIfPanel .../>)` aquí, pero
  // `rerender` de RTL sustituye literalmente el árbol por el elemento que se
  // le pasa, sin volver a envolverlo en `I18nProvider`/`QueryClientProvider`
  // (esos los añade `renderWithProviders`, no `rerender`), así que revienta
  // con "useT fuera de I18nProvider". Un nuevo `renderWithProviders` tras
  // desmontar (mismo patrón que `PoliciesPage.test.tsx`) sí conserva los
  // providers y, de paso, recoge el nuevo valor mockeado de `useReplayPolicy`
  // (un mock estático no se vuelve reactivo solo con `mutate()`).
  const view = renderWithProviders(<WhatIfPanel policy={policy as never} />);
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: "Simular" }));
  expect(mutate).toHaveBeenCalled();
  view.unmount();
  mockReplay({ data: result });
  renderWithProviders(<WhatIfPanel policy={policy as never} />);
  expect(screen.getByText("Disparos")).toBeInTheDocument();
  expect(screen.getByText("2")).toBeInTheDocument();
  expect(screen.getAllByText("Portátil Ventas").length).toBeGreaterThan(0);
  // Desviación: "lock: 2" vive dentro del mismo <p> que su etiqueta ("Por
  // acción: lock: 2", un solo nodo de texto compuesto por varios hijos JSX);
  // `getByText` con una cadena exige que el texto COMPLETO del elemento
  // coincida, así que "lock: 2" solo no encuentra nada. Una expresión
  // regular sí hace coincidencia parcial, que es lo que la aserción necesita.
  expect(screen.getByText(/lock: 2/)).toBeInTheDocument();
  expect(screen.getByText(/fuera de horario/)).toBeInTheDocument();
});

test("approximation true muestra el aviso de que las señales no espaciales son las de hoy", () => {
  mockReplay({ data: { ...result, approximation: true, notes: ["la postura se ha tomado del estado actual"] } });
  renderWithProviders(<WhatIfPanel policy={policy as never} />);
  expect(screen.getByText(/las señales no espaciales/)).toBeInTheDocument();
  expect(screen.getByText("la postura se ha tomado del estado actual")).toBeInTheDocument();
});

test("un resultado de cero disparos es un vacío explicado, no un error", () => {
  mockReplay({ data: { ...result, firings: 0, by_device: {}, by_action: {}, samples: [] } });
  renderWithProviders(<WhatIfPanel policy={policy as never} />);
  expect(screen.getByText("No habría disparado ni una vez")).toBeInTheDocument();
  expect(screen.getByText("Se han simulado 5 puntos del histórico y ninguno cumple las condiciones.")).toBeInTheDocument();
  expect(screen.queryByRole("alert")).toBeNull();
});

// El editor entero montado con los hooks de T22 mockeados: la puerta vive en
// él (es quien tiene el botón de guardar), pero es el what-if quien la abre.
function editorMontado() {
  vi.mocked(hooks.usePolicy).mockReturnValue({ data: undefined, isPending: false, error: null } as never);
  vi.mocked(hooks.usePolicyFields).mockReturnValue({ data: { fields: ["fence_state"], ops: ["eq"] }, isPending: false, error: null } as never);
  vi.mocked(hooks.usePolicyTemplates).mockReturnValue({ data: { items: [], total: 0 }, isPending: false, error: null } as never);
  vi.mocked(hooks.useCreatePolicy).mockReturnValue({ mutateAsync: vi.fn(), isPending: false, error: null } as never);
  vi.mocked(hooks.useUpdatePolicy).mockReturnValue({ mutateAsync: vi.fn(), isPending: false, error: null } as never);
  renderWithProviders(
    <Routes>
      <Route path="/policies/new" element={<PolicyEditorPage />} />
    </Routes>,
    { route: "/policies/new" },
  );
  return userEvent.setup();
}

test("con una acción destructiva el guardar está deshabilitado hasta ejecutar el what-if", async () => {
  const mutate = mockReplay();
  const user = editorMontado();
  await user.click(screen.getByRole("button", { name: "Añadir acción" }));
  await user.selectOptions(screen.getByLabelText("Acción"), "wipe");
  await waitFor(() => expect(screen.getByRole("button", { name: "Guardar" })).toBeDisabled());
  expect(screen.getByText("Esta política incluye una acción destructiva: ejecuta el what-if antes de guardarla.")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Simular" }));
  expect(mutate).toHaveBeenCalled();
  await waitFor(() => expect(screen.getByRole("button", { name: "Guardar" })).toBeEnabled());
});

test("volver destructiva una acción ya simulada cierra otra vez la puerta", async () => {
  mockReplay();
  const user = editorMontado();
  await user.click(screen.getByRole("button", { name: "Añadir acción" }));
  await user.click(screen.getByRole("button", { name: "Simular" }));
  await waitFor(() => expect(screen.getByRole("button", { name: "Guardar" })).toBeEnabled());
  await user.selectOptions(screen.getByLabelText("Acción"), "wipe");
  await waitFor(() => expect(screen.getByRole("button", { name: "Guardar" })).toBeDisabled());
  expect(screen.getByText("Esta política incluye una acción destructiva: ejecuta el what-if antes de guardarla.")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Simular" }));
  await waitFor(() => expect(screen.getByRole("button", { name: "Guardar" })).toBeEnabled());
});

test("cambiar una condición después de simular cierra otra vez la puerta", async () => {
  mockReplay();
  const user = editorMontado();
  await user.click(screen.getByRole("button", { name: "Añadir condición" }));
  await user.click(screen.getByRole("button", { name: "Añadir acción" }));
  await user.selectOptions(screen.getByLabelText("Acción"), "wipe");
  await user.click(screen.getByRole("button", { name: "Simular" }));
  await waitFor(() => expect(screen.getByRole("button", { name: "Guardar" })).toBeEnabled());
  await user.type(screen.getByLabelText("Valor"), "outside");
  await waitFor(() => expect(screen.getByRole("button", { name: "Guardar" })).toBeDisabled());
});
