import { screen } from "@testing-library/react";
import { Routes, Route } from "react-router";
import { renderWithProviders } from "@/test/render";
import { AuthGate } from "./AuthGate";
import * as hooks from "@/api/hooks";

vi.mock("@/api/hooks", async (orig) => ({ ...(await orig<typeof hooks>()), useAuthStatus: vi.fn(), useMe: vi.fn() }));

function tree() {
  return (
    <Routes>
      <Route path="/setup" element={<p>SETUP</p>} />
      <Route path="/login" element={<p>LOGIN</p>} />
      <Route element={<AuthGate />}>
        <Route path="/" element={<p>PRIVADO</p>} />
      </Route>
    </Routes>
  );
}

test("redirige a /setup si falta el asistente", () => {
  vi.mocked(hooks.useAuthStatus).mockReturnValue({ data: { setup_required: true }, isPending: false, error: null } as never);
  vi.mocked(hooks.useMe).mockReturnValue({ data: null, isPending: false, error: null } as never);
  renderWithProviders(tree());
  expect(screen.getByText("SETUP")).toBeInTheDocument();
});

test("redirige a /login sin sesión", () => {
  vi.mocked(hooks.useAuthStatus).mockReturnValue({ data: { setup_required: false }, isPending: false, error: null } as never);
  vi.mocked(hooks.useMe).mockReturnValue({ data: null, isPending: false, error: null } as never);
  renderWithProviders(tree());
  expect(screen.getByText("LOGIN")).toBeInTheDocument();
});

test("muestra el contenido con sesión", () => {
  vi.mocked(hooks.useAuthStatus).mockReturnValue({ data: { setup_required: false }, isPending: false, error: null } as never);
  vi.mocked(hooks.useMe).mockReturnValue({ data: { user: { role: "owner" }, csrf: "x", capabilities: [] }, isPending: false, error: null } as never);
  renderWithProviders(tree());
  expect(screen.getByText("PRIVADO")).toBeInTheDocument();
});

test("muestra cargando mientras resuelve", () => {
  vi.mocked(hooks.useAuthStatus).mockReturnValue({ data: undefined, isPending: true, error: null } as never);
  vi.mocked(hooks.useMe).mockReturnValue({ data: undefined, isPending: true, error: null } as never);
  renderWithProviders(tree());
  expect(screen.getByRole("status")).toBeInTheDocument();
});
