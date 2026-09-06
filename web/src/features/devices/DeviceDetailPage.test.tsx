import { screen } from "@testing-library/react";
import { Routes, Route } from "react-router";
import { renderWithProviders } from "@/test/render";
import { DeviceDetailPage } from "./DeviceDetailPage";
import * as hooks from "@/api/hooks";

vi.mock("@/api/hooks", async (orig) => ({ ...(await orig<typeof hooks>()), useDevice: vi.fn(), useDeviceTrail: vi.fn(), useEvents: vi.fn() }));

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
