import { screen, fireEvent } from "@testing-library/react";
import { renderWithProviders } from "@/test/render";
import { Loading } from "./Loading";
import { Empty } from "./Empty";
import { ErrorState } from "./ErrorState";
import { ApiError } from "@/api/client";

test("Loading expone role=status con etiqueta", () => {
  renderWithProviders(<Loading rows={2} />);
  expect(screen.getByRole("status", { name: "Cargando" })).toBeInTheDocument();
});

test("Empty muestra título, descripción y acción", () => {
  renderWithProviders(<Empty title="Sin geocercas" description="Crea la primera" action={<button>Crear</button>} />);
  expect(screen.getByText("Sin geocercas")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Crear" })).toBeInTheDocument();
});

test("ErrorState muestra el código de la API y reintenta", () => {
  const retry = vi.fn();
  renderWithProviders(<ErrorState error={new ApiError(403, "forbidden", "sin permiso")} onRetry={retry} />);
  expect(screen.getByRole("alert")).toHaveTextContent("sin permiso (forbidden)");
  fireEvent.click(screen.getByRole("button", { name: "Reintentar" }));
  expect(retry).toHaveBeenCalled();
});
