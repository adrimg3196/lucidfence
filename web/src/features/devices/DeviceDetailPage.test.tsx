import { screen } from "@testing-library/react";
import { Routes, Route } from "react-router";
import { renderWithProviders } from "@/test/render";
import { DeviceDetailPage } from "./DeviceDetailPage";
import * as hooks from "@/api/hooks";
import { ApiError } from "@/api/client";

vi.mock("@/api/hooks", async (orig) => ({
  ...(await orig<typeof hooks>()),
  useDevice: vi.fn(),
  useDeviceTrail: vi.fn(),
  useEvents: vi.fn(),
  useIncidents: vi.fn(),
  useMe: vi.fn(),
}));

const device = {
  id: "dev-001",
  name: "Tablet Campo A1",
  platform: "android",
  fence_state: "inside" as const,
  inside_fence: "demo-hq",
  route_state: "unassigned" as const,
  last_report_at: "2026-09-05T12:00:00Z",
  inventory: {
    os_version: "Android 14",
    model: "Samsung Galaxy Tab Active5",
    serial_number: "RZ8T",
    battery_level: 87,
    storage_total_gb: 128,
    storage_free_gb: 64.5,
    encryption_enabled: true,
    assigned_user: "Lucía",
    department: "Operaciones",
  },
  risk: { score: 72, severity: "high", reasons: ["dispositivo rooteado"], matched_policies: [], provenance: "tool", verified: true },
  signals: { device_posture: { rooted: true }, time_of_day: { off_hours: false }, zone_risk: { risk: null } },
  location: { point: { lat: 40.42, lng: -3.71 } },
};

function mockCommon(overrides: Partial<Record<"device" | "trail" | "events" | "incidents" | "me", unknown>> = {}) {
  vi.mocked(hooks.useDevice).mockReturnValue({ data: device, isPending: false, error: null, ...(overrides.device as object) } as never);
  vi.mocked(hooks.useDeviceTrail).mockReturnValue({
    data: { items: [{ at: "2026-09-05T12:00:00Z", point: { lat: 40.42, lng: -3.71 } }] },
    isPending: false,
    error: null,
    ...(overrides.trail as object),
  } as never);
  vi.mocked(hooks.useEvents).mockReturnValue({
    data: { items: [{ at: "2026-09-05T12:00:00Z", device_id: "dev-001", device_name: "x", from: "none:unknown", to: "demo-hq:inside" }] },
    isPending: false,
    error: null,
    ...(overrides.events as object),
  } as never);
  vi.mocked(hooks.useIncidents).mockReturnValue({ data: { items: [], total: 0 }, isPending: false, error: null, ...(overrides.incidents as object) } as never);
  vi.mocked(hooks.useMe).mockReturnValue({ data: { capabilities: [] }, ...(overrides.me as object) } as never);
}

function renderDetail() {
  renderWithProviders(
    <Routes>
      <Route path="/devices/:id" element={<DeviceDetailPage />} />
    </Routes>,
    { route: "/devices/dev-001" },
  );
}

test("muestra inventario, riesgo explicado, señales, recorrido y transiciones del dispositivo", () => {
  mockCommon();
  renderDetail();
  expect(screen.getByRole("heading", { name: "Tablet Campo A1" })).toBeInTheDocument();
  expect(screen.getByText("Samsung Galaxy Tab Active5")).toBeInTheDocument();
  expect(screen.getByText("87 %")).toBeInTheDocument();
  expect(screen.getByText("72")).toBeInTheDocument();
  expect(screen.getByText("Alto")).toBeInTheDocument();
  expect(screen.getByText("dispositivo rooteado")).toBeInTheDocument();
  expect(screen.getByText("Desconocido")).toBeInTheDocument(); // zone_risk.risk == null
  expect(screen.getByText("demo-hq:inside")).toBeInTheDocument();
});

test("recorrido, transiciones e incidentes muestran error sin romper el resto de la página", () => {
  mockCommon({
    trail: { data: undefined, error: new ApiError(500, "internal", "error interno"), refetch: vi.fn() },
    events: { data: undefined, error: new ApiError(500, "internal", "error interno"), refetch: vi.fn() },
    incidents: { data: undefined, error: new ApiError(500, "internal", "error interno"), refetch: vi.fn() },
  });
  renderDetail();
  expect(screen.getByRole("heading", { name: "Tablet Campo A1" })).toBeInTheDocument();
  const alerts = screen.getAllByRole("alert");
  expect(alerts).toHaveLength(3);
  for (const alert of alerts) expect(alert).toHaveTextContent("error interno (internal)");
});

test("recorrido, transiciones e incidentes muestran vacío explícito cuando no hay datos", () => {
  mockCommon({ trail: { data: { items: [] } }, events: { data: { items: [] } }, incidents: { data: { items: [], total: 0 } } });
  renderDetail();
  expect(screen.getByText("Sin recorrido registrado todavía")).toBeInTheDocument();
  expect(screen.getByText("Sin transiciones de este dispositivo")).toBeInTheDocument();
  expect(screen.getByText("Sin incidentes abiertos")).toBeInTheDocument();
});

test("los incidentes abiertos del dispositivo aparecen con enlace y fecha", () => {
  mockCommon({
    incidents: {
      data: {
        items: [
          {
            id: "inc-1",
            device_id: "dev-001",
            device_name: "Tablet Campo A1",
            kind: "high_risk_device",
            severity: "high",
            title: "Riesgo alto sostenido",
            recommendation: "Revisar postura",
            fence_id: "",
            assignee: "",
            status: "open",
            risk_score: 72,
            count: 3,
            evidence: [],
            opened_at: "2026-09-05T11:00:00Z",
            updated_at: "2026-09-05T11:00:00Z",
            timeline: [],
          },
        ],
        total: 1,
      },
    },
  });
  renderDetail();
  expect(screen.getByRole("link", { name: "Riesgo alto sostenido" })).toHaveAttribute("href", "/incidents/inc-1");
});
