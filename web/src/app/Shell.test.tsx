import { screen, fireEvent, waitFor } from "@testing-library/react";
import { Routes, Route } from "react-router";
import { renderWithProviders } from "@/test/render";
import { Shell } from "./Shell";
import { ThemeProvider } from "./theme";
import * as hooks from "@/api/hooks";
import { api } from "@/api/client";

vi.mock("@/api/hooks", async (orig) => ({ ...(await orig<typeof hooks>()), useMe: vi.fn(), useLogout: vi.fn() }));
vi.mock("@/api/client", async (orig) => {
  const actual = await orig<typeof import("@/api/client")>();
  return { ...actual, api: { ...actual.api, POST: vi.fn() } };
});

afterEach(() => {
  document.documentElement.classList.remove("dark");
  localStorage.clear();
});

test("el shell muestra la navegación y el usuario", () => {
  vi.mocked(hooks.useMe).mockReturnValue({ data: { user: { name: "Adri", email: "a@x.com", role: "owner", org: "default" }, csrf: "x", capabilities: [] } } as never);
  vi.mocked(hooks.useLogout).mockReturnValue({ mutate: vi.fn(), isPending: false } as never);
  renderWithProviders(
    <ThemeProvider>
      <Routes>
        <Route element={<Shell />}>
          <Route path="/" element={<p>HOME</p>} />
        </Route>
      </Routes>
    </ThemeProvider>,
  );
  for (const label of ["Visión general", "Mapa", "Dispositivos", "Geocercas"]) {
    expect(screen.getByRole("link", { name: label })).toBeInTheDocument();
  }
  expect(screen.getByText("Adri")).toBeInTheDocument();
  expect(screen.getByText("HOME")).toBeInTheDocument();
});

test("los botones de cabecera cambian de tema, de idioma y cierran la sesión", async () => {
  const session = { user: { name: "Adri", email: "a@x.com", role: "owner", org: "default" } };
  vi.mocked(hooks.useMe).mockImplementation(() => ({ data: session.user ? { user: session.user, csrf: "x", capabilities: [] } : null }) as never);
  const actualHooks = await vi.importActual<typeof hooks>("@/api/hooks");
  vi.mocked(hooks.useLogout).mockImplementation(actualHooks.useLogout);
  vi.mocked(api.POST).mockImplementation(async (path: unknown) => {
    if (path === "/api/v1/auth/logout") session.user = null as never;
    return { data: {}, response: { ok: true, status: 200 } } as never;
  });

  renderWithProviders(
    <ThemeProvider>
      <Routes>
        <Route element={<Shell />}>
          <Route path="/" element={<p>HOME</p>} />
        </Route>
      </Routes>
    </ThemeProvider>,
  );

  // Tema: el botón alterna la clase que theme.tsx aplica en <html>.
  expect(document.documentElement.classList.contains("dark")).toBe(false);
  fireEvent.click(screen.getByRole("button", { name: "Cambiar tema" }));
  expect(document.documentElement.classList.contains("dark")).toBe(true);

  // Idioma: el botón cambia la etiqueta de navegación de español a inglés.
  expect(screen.getByRole("link", { name: "Visión general" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "English" }));
  expect(screen.getByRole("link", { name: "Overview" })).toBeInTheDocument();

  // Salir: llama al endpoint de logout y el usuario deja de verse.
  expect(screen.getByText("Adri")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Sign out" }));
  await waitFor(() => expect(api.POST).toHaveBeenCalledWith("/api/v1/auth/logout"));
  await waitFor(() => expect(screen.queryByText("Adri")).not.toBeInTheDocument());
});
