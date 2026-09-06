import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "@/test/render";
import { SetupPage } from "./SetupPage";
import * as hooks from "@/api/hooks";

const navigate = vi.fn();
vi.mock("react-router", async (orig) => ({ ...(await orig<typeof import("react-router")>()), useNavigate: () => navigate }));
vi.mock("@/api/hooks", async (orig) => ({ ...(await orig<typeof hooks>()), useSetup: vi.fn() }));

test("valida campos y envía en modo demo", async () => {
  const mutateAsync = vi.fn().mockResolvedValue({});
  vi.mocked(hooks.useSetup).mockReturnValue({ mutateAsync, isPending: false, error: null } as never);
  renderWithProviders(<SetupPage />);
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: "Crear cuenta y entrar" }));
  expect(await screen.findAllByRole("alert")).not.toHaveLength(0);
  expect(mutateAsync).not.toHaveBeenCalled();
  await user.type(screen.getByLabelText("Email"), "adri@example.com");
  await user.type(screen.getByLabelText("Nombre"), "Adri");
  await user.type(screen.getByLabelText("Contraseña (mínimo 10 caracteres)"), "contraseña-larga-1");
  await user.click(screen.getByLabelText("Demo local con flota simulada"));
  await user.click(screen.getByRole("button", { name: "Crear cuenta y entrar" }));
  await waitFor(() => expect(mutateAsync).toHaveBeenCalledWith({ email: "adri@example.com", name: "Adri", password: "contraseña-larga-1", mode: "demo" }));
  expect(navigate).toHaveBeenCalledWith("/", { replace: true });
});
