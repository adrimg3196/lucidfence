import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router";
import { useFieldArray, type Control } from "react-hook-form";
import { renderWithProviders } from "@/test/render";
import { PlaybookEditorPage } from "./PlaybookEditorPage";
import * as hooks from "@/api/hooks";
import * as policyForm from "@/features/policies/policyForm";

// Banco de pruebas de las filas compartidas: ConditionRows y ActionRows son de
// T23 y tienen sus propios tests; aquí se sustituyen por dos arneses que
// manipulan el MISMO estado de react-hook-form, para comprobar el aviso de
// acciones destructivas y el cuerpo que se envía sin depender de su interfaz.
type Filas = { when: { field: string; op: string; value: unknown }[]; actions: { action: string }[] };

vi.mock("@/features/policies/ConditionRows", () => ({
  ConditionRows: ({ control }: { control: unknown }) => {
    const rows = useFieldArray({ control: control as Control<Filas>, name: "when" });
    return (
      <button type="button" onClick={() => rows.append({ field: "compliant", op: "eq", value: false })}>
        añadir condición
      </button>
    );
  },
}));

vi.mock("@/features/policies/ActionRows", () => ({
  ActionRows: ({ control }: { control: unknown }) => {
    const rows = useFieldArray({ control: control as Control<Filas>, name: "actions" });
    return (
      <div>
        <button type="button" onClick={() => rows.append({ action: "lock" })}>añadir lock</button>
        <button type="button" onClick={() => rows.append({ action: "notify" })}>añadir notify</button>
        {rows.fields.map((f, i) => (
          <button key={f.id} type="button" onClick={() => rows.remove(i)}>
            quitar acción {i + 1}
          </button>
        ))}
      </div>
    );
  },
}));

// toPolicy/fromPolicy traducen filas a la gramática de T23 y tienen sus
// propios tests; aquí se estabilizan como identidad sobre `when`/`actions`
// para que el caso dorado compruebe exactamente lo que envía toPlaybook.
vi.mock("@/features/policies/policyForm", async (orig) => ({
  ...(await orig<typeof policyForm>()),
  toPolicy: (v: Filas, now: string) => ({ ...v, created_at: now, updated_at: now }),
  fromPolicy: (p: Filas) => ({ when: p.when, actions: p.actions }),
}));

vi.mock("@/api/hooks", async (orig) => ({
  ...(await orig<typeof hooks>()),
  usePlaybooks: vi.fn(),
  useCreatePlaybook: vi.fn(),
  useUpdatePlaybook: vi.fn(),
  usePolicyFields: vi.fn(),
}));

function mockEditor(items: hooks.Playbook[]) {
  const create = vi.fn().mockResolvedValue(undefined);
  const update = vi.fn().mockResolvedValue(undefined);
  vi.mocked(hooks.usePlaybooks).mockReturnValue({ data: { items, total: items.length }, isPending: false, error: null, refetch: vi.fn() } as never);
  vi.mocked(hooks.useCreatePlaybook).mockReturnValue({ mutateAsync: create, isPending: false, error: null } as never);
  vi.mocked(hooks.useUpdatePlaybook).mockReturnValue({ mutateAsync: update, isPending: false, error: null } as never);
  vi.mocked(hooks.usePolicyFields).mockReturnValue({ data: { fields: ["compliant", "fence_state"] }, isPending: false, error: null } as never);
  return { create, update };
}

test("el aviso de acciones destructivas aparece con lock y desaparece al quitarlo", async () => {
  mockEditor([]);
  renderWithProviders(<PlaybookEditorPage />, { route: "/playbooks/new" });
  const user = userEvent.setup();
  expect(screen.queryByText("Este playbook incluye acciones destructivas")).toBeNull();
  await user.click(screen.getByRole("button", { name: "añadir notify" }));
  expect(screen.queryByText("Este playbook incluye acciones destructivas")).toBeNull();
  await user.click(screen.getByRole("button", { name: "añadir lock" }));
  expect(await screen.findByText("Este playbook incluye acciones destructivas")).toBeInTheDocument();
  expect(screen.getByText(/Bloquear no se ejecutan solas/)).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "quitar acción 2" }));
  await waitFor(() => expect(screen.queryByText("Este playbook incluye acciones destructivas")).toBeNull());
});

test("crear un playbook envía el cuerpo exacto", async () => {
  const { create } = mockEditor([]);
  renderWithProviders(<PlaybookEditorPage />, { route: "/playbooks/new" });
  const user = userEvent.setup();
  await user.type(screen.getByLabelText("Nombre"), "Robo en curso");
  await user.type(screen.getByLabelText("Descripción"), "Bloqueo con aprobación humana.");
  await user.selectOptions(screen.getByLabelText("Severidad"), "critical");
  await user.click(screen.getByRole("button", { name: "añadir condición" }));
  await user.click(screen.getByRole("button", { name: "añadir lock" }));
  await user.click(screen.getByRole("button", { name: "Guardar" }));
  await waitFor(() => expect(create).toHaveBeenCalledTimes(1));
  expect(create).toHaveBeenCalledWith({
    id: "robo-en-curso",
    name: "Robo en curso",
    description: "Bloqueo con aprobación humana.",
    severity: "critical",
    enabled: true,
    when: [{ field: "compliant", op: "eq", value: false }],
    actions: [{ action: "lock" }],
    created_at: expect.any(String),
    updated_at: expect.any(String),
  });
});

test("sin condiciones ni acciones el formulario no llega a la API", async () => {
  const { create } = mockEditor([]);
  renderWithProviders(<PlaybookEditorPage />, { route: "/playbooks/new" });
  const user = userEvent.setup();
  await user.type(screen.getByLabelText("Nombre"), "Vacío");
  await user.click(screen.getByRole("button", { name: "Guardar" }));
  expect(await screen.findByText("Añade al menos una condición")).toBeInTheDocument();
  expect(screen.getByText("Añade al menos una acción")).toBeInTheDocument();
  expect(create).not.toHaveBeenCalled();
});

test("editar carga el playbook existente y actualiza sin cambiar el id", async () => {
  const existente = {
    id: "soar-noncompliant-outside",
    name: "No conforme y fuera de geocerca",
    description: "Bloqueo con aprobación humana y aviso al SOC.",
    when: [{ field: "compliant", op: "eq", value: false }],
    actions: [{ action: "lock" }],
    enabled: true,
    severity: "high",
    created_at: "2026-09-06T08:00:00Z",
    updated_at: "2026-09-06T08:00:00Z",
  } as hooks.Playbook;
  const { update } = mockEditor([existente]);
  renderWithProviders(
    <Routes>
      <Route path="/playbooks/:id" element={<PlaybookEditorPage />} />
    </Routes>,
    { route: "/playbooks/soar-noncompliant-outside" },
  );
  const user = userEvent.setup();
  await waitFor(() => expect(screen.getByLabelText("Nombre")).toHaveValue("No conforme y fuera de geocerca"));
  expect(screen.getByLabelText("Identificador")).toHaveAttribute("readonly");
  expect(screen.getByText("Este playbook incluye acciones destructivas")).toBeInTheDocument();
  await user.clear(screen.getByLabelText("Nombre"));
  await user.type(screen.getByLabelText("Nombre"), "No conforme fuera de perímetro");
  await user.click(screen.getByRole("button", { name: "Guardar" }));
  await waitFor(() => expect(update).toHaveBeenCalledTimes(1));
  expect(update.mock.calls[0][0]).toMatchObject({ id: "soar-noncompliant-outside", name: "No conforme fuera de perímetro", enabled: true });
});
