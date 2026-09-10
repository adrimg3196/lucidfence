import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "@/test/render";
import { EventsPage } from "./EventsPage";
import * as hooks from "@/api/hooks";

vi.mock("@/api/hooks", async (orig) => ({ ...(await orig<typeof hooks>()), useEventsPage: vi.fn() }));

const page1 = {
  items: [
    { at: "2026-09-05T12:00:00Z", device_id: "dev-001", device_name: "Tablet Campo A1", from: "none:unknown", to: "demo-hq:inside" },
    { at: "2026-09-05T12:05:00Z", device_id: "dev-002", device_name: "Portátil Ventas", from: "demo-hq:inside", to: "demo-hq:outside" },
  ],
  next_cursor: "c2",
};
const page2 = {
  items: [{ at: "2026-09-05T12:10:00Z", device_id: "dev-003", device_name: "Móvil Reparto", from: "none:unknown", to: "demo-hq:inside" }],
  next_cursor: "",
};

function mockPages() {
  vi.mocked(hooks.useEventsPage).mockImplementation(
    ((cursor?: string) =>
      cursor === "c2"
        ? { data: page2, isPending: false, isFetching: false, error: null, refetch: vi.fn() }
        : { data: page1, isPending: false, isFetching: false, error: null, refetch: vi.fn() }) as never,
  );
}

test("cargando", () => {
  vi.mocked(hooks.useEventsPage).mockReturnValue({ data: undefined, isPending: true, isFetching: true, error: null, refetch: vi.fn() } as never);
  renderWithProviders(<EventsPage />);
  expect(screen.getByRole("status")).toBeInTheDocument();
});

test("vacío", () => {
  vi.mocked(hooks.useEventsPage).mockReturnValue({ data: { items: [], next_cursor: "" }, isPending: false, isFetching: false, error: null, refetch: vi.fn() } as never);
  renderWithProviders(<EventsPage />);
  expect(screen.getByText("Sin transiciones. Ejecuta un ciclo del motor.")).toBeInTheDocument();
});

test("error", () => {
  vi.mocked(hooks.useEventsPage).mockReturnValue({ data: undefined, isPending: false, isFetching: false, error: new Error("caído"), refetch: vi.fn() } as never);
  renderWithProviders(<EventsPage />);
  expect(screen.getByRole("alert")).toHaveTextContent("caído");
});

test("cargar más envía el cursor devuelto, concatena sin duplicar y el botón desaparece al agotarse", async () => {
  mockPages();
  renderWithProviders(<EventsPage />);
  expect(screen.getByText("Tablet Campo A1")).toBeInTheDocument();
  expect(screen.getByText("Portátil Ventas")).toBeInTheDocument();
  expect(screen.getAllByRole("row")).toHaveLength(3); // cabecera + 2 filas
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: "Cargar más" }));
  await waitFor(() => expect(screen.getByText("Móvil Reparto")).toBeInTheDocument());
  expect(screen.getAllByRole("row")).toHaveLength(4); // cabecera + 3 filas
  expect(screen.getAllByText("Tablet Campo A1")).toHaveLength(1);
  expect(screen.queryByRole("button", { name: "Cargar más" })).toBeNull();
});
