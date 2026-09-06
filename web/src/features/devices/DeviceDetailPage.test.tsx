import { screen } from "@testing-library/react";
import { Routes, Route } from "react-router";
import { renderWithProviders } from "@/test/render";
import { DeviceDetailPage } from "./DeviceDetailPage";
import * as hooks from "@/api/hooks";
import { ApiError } from "@/api/client";

vi.mock("@/api/hooks", async (orig) => ({ ...(await orig<typeof hooks>()), useDevice: vi.fn(), useDeviceTrail: vi.fn(), useEvents: vi.fn() }));

const device = {
  id: "dev-001",
  name: "Tablet Campo A1",
  platform: "android",
  fence_state: "inside" as const,
  inside_fence: "demo-hq",
  route_state: "unassigned" as const,
  last_report_at: "2026-09-05T12:00:00Z",
  inventory: { os_version: "Android 14", model: "Samsung Galaxy Tab Active5", serial_number: "RZ8T", battery_level: 87, storage_total_gb: 128, storage_free_gb: 64.5, encryption_enabled: true, assigned_user: "Lucía", department: "Operaciones" },
  risk: { score: null, severity: "", reasons: [], matched_policies: [], provenance: "", verified: false },
  location: { point: { lat: 40.42, lng: -3.71 } },
};

function renderDetail() {
  renderWithProviders(
    <Routes>
      <Route path="/devices/:id" element={<DeviceDetailPage />} />
    </Routes>,
    { route: "/devices/dev-001" },
  );
}

test("muestra inventario, riesgo pendiente, recorrido y transiciones del dispositivo", () => {
  vi.mocked(hooks.useDevice).mockReturnValue({
    data: { id: "dev-001", name: "Tablet Campo A1", platform: "android", fence_state: "inside", inside_fence: "demo-hq", route_state: "unassigned", last_report_at: "2026-09-05T12:00:00Z",
      inventory: { os_version: "Android 14", model: "Samsung Galaxy Tab Active5", serial_number: "RZ8T", battery_level: 87, storage_total_gb: 128, storage_free_gb: 64.5, encryption_enabled: true, assigned_user: "Lucía", department: "Operaciones" },
      risk: { score: null, severity: "", reasons: [], matched_policies: [], provenance: "", verified: false }, location: { point: { lat: 40.42, lng: -3.71 } } },
    isPending: false, error: null } as never);
  vi.mocked(hooks.useDeviceTrail).mockReturnValue({ data: { items: [{ at: "2026-09-05T12:00:00Z", point: { lat: 40.42, lng: -3.71 } }] }, isPending: false, error: null } as never);
  vi.mocked(hooks.useEvents).mockReturnValue({ data: { items: [{ at: "2026-09-05T12:00:00Z", device_id: "dev-001", device_name: "x", from: "none:unknown", to: "demo-hq:inside" }, { at: "2026-09-05T12:00:00Z", device_id: "dev-002", device_name: "y", from: "a", to: "b" }] }, isPending: false, error: null } as never);
  renderWithProviders(
    <Routes>
      <Route path="/devices/:id" element={<DeviceDetailPage />} />
    </Routes>,
    { route: "/devices/dev-001" },
  );
  expect(screen.getByRole("heading", { name: "Tablet Campo A1" })).toBeInTheDocument();
  expect(screen.getByText("Samsung Galaxy Tab Active5")).toBeInTheDocument();
  expect(screen.getByText("87 %")).toBeInTheDocument();
  expect(screen.getByText(/Sin evaluar/)).toBeInTheDocument();
  expect(screen.getByText("demo-hq:inside")).toBeInTheDocument();
  expect(screen.queryByText("b")).toBeNull();
});

test("recorrido y transiciones muestran error sin romper el resto de la página", () => {
  vi.mocked(hooks.useDevice).mockReturnValue({ data: device, isPending: false, error: null } as never);
  const trailRefetch = vi.fn();
  const eventsRefetch = vi.fn();
  vi.mocked(hooks.useDeviceTrail).mockReturnValue({ data: undefined, isPending: false, error: new ApiError(500, "internal", "error interno"), refetch: trailRefetch } as never);
  vi.mocked(hooks.useEvents).mockReturnValue({ data: undefined, isPending: false, error: new ApiError(500, "internal", "error interno"), refetch: eventsRefetch } as never);
  renderDetail();
  expect(screen.getByRole("heading", { name: "Tablet Campo A1" })).toBeInTheDocument();
  const alerts = screen.getAllByRole("alert");
  expect(alerts).toHaveLength(2);
  for (const alert of alerts) expect(alert).toHaveTextContent("error interno (internal)");
});

test("recorrido y transiciones muestran vacío explícito cuando no hay datos", () => {
  vi.mocked(hooks.useDevice).mockReturnValue({ data: device, isPending: false, error: null } as never);
  vi.mocked(hooks.useDeviceTrail).mockReturnValue({ data: { items: [] }, isPending: false, error: null } as never);
  vi.mocked(hooks.useEvents).mockReturnValue({ data: { items: [] }, isPending: false, error: null } as never);
  renderDetail();
  expect(screen.getByText("Sin recorrido registrado todavía")).toBeInTheDocument();
  expect(screen.getByText("Sin transiciones de este dispositivo")).toBeInTheDocument();
});
