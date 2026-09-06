import { render, screen } from "@testing-library/react";
import { App } from "./App";

test("App muestra el estado de carga mientras resuelve la sesión", () => {
  render(<App />);
  // Justo tras montar, auth/status y auth/me aún no han resuelto: el árbol
  // debe mostrar el estado de carga, no un contenedor vacío.
  expect(screen.getByRole("status", { name: "Cargando" })).toBeInTheDocument();
});
