import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "@/test/render";
import { LoginPage } from "./LoginPage";
import { ApiError } from "@/api/client";
import * as hooks from "@/api/hooks";

vi.mock("react-router", async (orig) => ({ ...(await orig<typeof import("react-router")>()), useNavigate: () => vi.fn() }));
vi.mock("@/api/hooks", async (orig) => ({ ...(await orig<typeof hooks>()), useLogin: vi.fn() }));

test("muestra el error de credenciales de la API", async () => {
  const mutateAsync = vi.fn().mockRejectedValue(new ApiError(401, "invalid_credentials", "email o contraseña incorrectos"));
  vi.mocked(hooks.useLogin).mockReturnValue({ mutateAsync, isPending: false, error: null } as never);
  renderWithProviders(<LoginPage />);
  const user = userEvent.setup();
  await user.type(screen.getByLabelText("Email"), "a@x.com");
  await user.type(screen.getByLabelText("Contraseña"), "lo-que-sea-largo");
  await user.click(screen.getByRole("button", { name: "Entrar" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Email o contraseña incorrectos");
});
