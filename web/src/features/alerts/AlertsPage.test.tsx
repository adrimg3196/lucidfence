import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "@/test/render";
import { AlertsPage } from "./AlertsPage";
import * as hooks from "@/api/hooks";

vi.mock("@/api/hooks", async (orig) => ({
  ...(await orig<typeof hooks>()),
  useAlerts: vi.fn(),
  useCreateAlert: vi.fn(),
  useUpdateAlert: vi.fn(),
  useDeleteAlert: vi.fn(),
  useEvaluateAlerts: vi.fn(),
  useMe: vi.fn(),
}));

const rule = { id: "fuera-30", name: "Fuera 30 min", kind: "outside_duration" as const, threshold: 30, severity: "high", enabled: true };

function mockAll(over: { create?: unknown; evaluate?: unknown } = {}, caps = ["incident:read", "alert:write"]) {
  vi.mocked(hooks.useAlerts).mockReturnValue({ data: { items: [rule], total: 1 }, isPending: false, error: null } as never);
  vi.mocked(hooks.useCreateAlert).mockReturnValue((over.create ?? { mutateAsync: vi.fn().mockResolvedValue(rule), isPending: false, error: null }) as never);
  vi.mocked(hooks.useUpdateAlert).mockReturnValue({ mutateAsync: vi.fn().mockResolvedValue(rule), isPending: false, error: null } as never);
  vi.mocked(hooks.useDeleteAlert).mockReturnValue({ mutate: vi.fn(), isPending: false, error: null } as never);
  vi.mocked(hooks.useEvaluateAlerts).mockReturnValue((over.evaluate ?? { mutate: vi.fn(), data: undefined, isPending: false, error: null }) as never);
  vi.mocked(hooks.useMe).mockReturnValue({ data: { capabilities: caps } } as never);
}

test("crear una regla envía el tipo y el umbral correctos", async () => {
  const mutateAsync = vi.fn().mockResolvedValue(rule);
  mockAll({ create: { mutateAsync, isPending: false, error: null } });
  renderWithProviders(<AlertsPage />);
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: "Nueva regla" }));
  await user.type(screen.getByLabelText("Nombre"), "Batería baja");
  expect(screen.getByLabelText("Identificador")).toHaveValue("bateria-baja");
  await user.selectOptions(screen.getByLabelText("Tipo"), "battery_below");
  await user.clear(screen.getByLabelText(/^Umbral/));
  await user.type(screen.getByLabelText(/^Umbral/), "15");
  await user.selectOptions(screen.getByLabelText("Severidad"), "critical");
  await user.click(screen.getByRole("button", { name: "Guardar" }));
  await waitFor(() => expect(mutateAsync).toHaveBeenCalled());
  expect(mutateAsync.mock.calls[0][0]).toEqual({ id: "bateria-baja", name: "Batería baja", kind: "battery_below", threshold: 15, severity: "critical", enabled: true });
});

test("umbral vacío o negativo muestra el error debajo del campo", async () => {
  const mutateAsync = vi.fn();
  mockAll({ create: { mutateAsync, isPending: false, error: null } });
  renderWithProviders(<AlertsPage />);
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: "Nueva regla" }));
  await user.type(screen.getByLabelText("Nombre"), "Sin umbral");
  await user.clear(screen.getByLabelText(/^Umbral/));
  await user.click(screen.getByRole("button", { name: "Guardar" }));
  expect(await screen.findByText("El umbral debe ser un número")).toBeInTheDocument();

  await user.type(screen.getByLabelText(/^Umbral/), "-5");
  await user.click(screen.getByRole("button", { name: "Guardar" }));
  expect(await screen.findByText("El umbral no puede ser negativo")).toBeInTheDocument();
  expect(mutateAsync).not.toHaveBeenCalled();
});

test("la unidad de la etiqueta cambia con el tipo", async () => {
  mockAll();
  renderWithProviders(<AlertsPage />);
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: "Nueva regla" }));
  expect(screen.getByLabelText("Umbral (minutos)")).toBeInTheDocument();
  await user.selectOptions(screen.getByLabelText("Tipo"), "battery_below");
  expect(screen.getByLabelText("Umbral (%)")).toBeInTheDocument();
  await user.selectOptions(screen.getByLabelText("Tipo"), "storage_low");
  expect(screen.getByLabelText("Umbral (GB)")).toBeInTheDocument();
  await user.selectOptions(screen.getByLabelText("Tipo"), "noncompliant");
  expect(screen.getByLabelText("Umbral (sin umbral)")).toBeDisabled();
});

test("la vista previa muestra los disparos y no modifica la lista", async () => {
  const mutate = vi.fn();
  const evaluation = {
    at: "2026-09-06T12:00:00Z",
    rules_evaluated: 1,
    devices: 6,
    count: 1,
    firings: [{ at: "2026-09-06T12:00:00Z", rule_id: "fuera-30", rule_name: "Fuera 30 min", kind: "outside_duration", device_id: "dev-004", device_name: "Portátil Ventas", severity: "high", reason: "fuera de geocerca 45 min (umbral 30 min)", value: 45 }],
  };
  mockAll({ evaluate: { mutate, data: evaluation, isPending: false, error: null } });
  renderWithProviders(<AlertsPage />);
  await userEvent.setup().click(screen.getByRole("button", { name: "Vista previa" }));
  expect(mutate).toHaveBeenCalledTimes(1);
  const preview = screen.getByRole("region", { name: "Vista previa" });
  expect(within(preview).getByText("fuera de geocerca 45 min (umbral 30 min)")).toBeInTheDocument();
  expect(screen.getByText("1 disparos sobre 6 dispositivos")).toBeInTheDocument();
  // la vista previa no toca las reglas: la lista sigue teniendo la única que había
  expect(vi.mocked(hooks.useCreateAlert).mock.results[0].value.mutateAsync).not.toHaveBeenCalled();
  expect(vi.mocked(hooks.useUpdateAlert).mock.results[0].value.mutateAsync).not.toHaveBeenCalled();
  expect(vi.mocked(hooks.useDeleteAlert).mock.results[0].value.mutate).not.toHaveBeenCalled();
});

test("un viewer ve la lista pero no la CRUD ni la vista previa", () => {
  mockAll({}, ["incident:read"]);
  renderWithProviders(<AlertsPage />);
  expect(screen.getByText("Fuera 30 min")).toBeInTheDocument();
  for (const label of ["Nueva regla", "Vista previa", "Editar", "Eliminar"]) expect(screen.queryByRole("button", { name: label })).toBeNull();
});
