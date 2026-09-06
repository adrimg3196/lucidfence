import { screen } from "@testing-library/react";
import { Routes, Route } from "react-router";
import { renderWithProviders } from "@/test/render";
import { Shell } from "./Shell";
import { ThemeProvider } from "./theme";
import * as hooks from "@/api/hooks";

vi.mock("@/api/hooks", async (orig) => ({ ...(await orig<typeof hooks>()), useMe: vi.fn(), useLogout: vi.fn() }));

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
