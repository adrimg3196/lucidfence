import { screen, fireEvent } from "@testing-library/react";
import { renderWithProviders } from "@/test/render";
import { DataTable, type Column } from "./DataTable";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/api/client";

type Fila = { id: string; nombre: string };

const columnas: Column<Fila>[] = [
  { key: "nombre", header: "Nombre", cell: (f) => f.nombre },
  { key: "id", header: "Identificador", cell: (f) => <span className="font-mono">{f.id}</span> },
];
const filas: Fila[] = [
  { id: "pol-1", nombre: "Salida sin cifrado" },
  { id: "pol-2", nombre: "Riesgo crítico" },
];
const vacio = { title: "Sin políticas", description: "Crea la primera", action: <Button>Nueva política</Button> };

test("cargando pinta el esqueleto con la forma final de la tabla", () => {
  renderWithProviders(<DataTable columns={columnas} rows={undefined} rowKey={(f) => f.id} empty={vacio} loading skeletonRows={3} />);
  expect(screen.getByRole("status", { name: "Cargando" })).toBeInTheDocument();
  expect(screen.getByText("Nombre")).toBeInTheDocument();
  expect(screen.getByText("Identificador")).toBeInTheDocument();
  expect(screen.queryByText("pol-1")).toBeNull();
  expect(screen.queryByText("Sin políticas")).toBeNull();
});

test("vacío muestra el título, la descripción y su acción", () => {
  renderWithProviders(<DataTable columns={columnas} rows={[]} rowKey={(f) => f.id} empty={vacio} />);
  expect(screen.getByText("Sin políticas")).toBeInTheDocument();
  expect(screen.getByText("Crea la primera")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Nueva política" })).toBeInTheDocument();
});

test("error tiene role alert, el código de la API y reintenta", () => {
  const retry = vi.fn();
  renderWithProviders(
    <DataTable columns={columnas} rows={undefined} rowKey={(f) => f.id} empty={vacio} error={new ApiError(500, "internal", "error interno")} onRetry={retry} />,
  );
  expect(screen.getByRole("alert")).toHaveTextContent("error interno (internal)");
  fireEvent.click(screen.getByRole("button", { name: "Reintentar" }));
  expect(retry).toHaveBeenCalledOnce();
  expect(screen.queryByRole("table")).toBeNull();
});

test("con contenido pinta una fila por dato y usa la celda de cada columna", () => {
  renderWithProviders(<DataTable columns={columnas} rows={filas} rowKey={(f) => f.id} empty={vacio} />);
  expect(screen.getAllByRole("row")).toHaveLength(3);
  expect(screen.getByText("Salida sin cifrado")).toBeInTheDocument();
  expect(screen.getByText("pol-2")).toBeInTheDocument();
  expect(screen.queryByRole("status")).toBeNull();
});

test("el error gana a los datos ya cargados", () => {
  renderWithProviders(<DataTable columns={columnas} rows={filas} rowKey={(f) => f.id} empty={vacio} error={new Error("caído")} />);
  expect(screen.getByRole("alert")).toHaveTextContent("caído");
  expect(screen.queryByText("Salida sin cifrado")).toBeNull();
});
