import { screen } from "@testing-library/react";
import { renderWithProviders } from "@/test/render";
import { MapPage } from "./MapPage";
import * as hooks from "@/api/hooks";

const mapInstances: unknown[] = [];
vi.mock("maplibre-gl", () => {
  class Map {
    handlers: Record<string, () => void> = {};
    constructor(public opts: unknown) { mapInstances.push(this); }
    on(ev: string, a: unknown, b?: unknown) { const fn = (typeof a === "function" ? a : b) as () => void; this.handlers[ev] = fn; if (ev === "load") fn(); }
    addSource() {} getSource() { return undefined; } addLayer() {} addControl() {} fitBounds() {} remove() {} getCanvas() { return { style: {} }; }
  }
  class Popup { setLngLat() { return this; } setHTML() { return this; } addTo() { return this; } }
  class NavigationControl {}
  class LngLatBounds { extend() { return this; } isEmpty() { return false; } }
  return { default: { Map, Popup, NavigationControl, LngLatBounds }, Map, Popup, NavigationControl, LngLatBounds };
});
vi.mock("@/api/hooks", async (orig) => ({ ...(await orig<typeof hooks>()), useHealth: vi.fn(), useFences: vi.fn(), useDevices: vi.fn() }));

function mock(mapEnabled: boolean) {
  vi.mocked(hooks.useHealth).mockReturnValue({ data: { map: { enabled: mapEnabled, tiles_url: "https://t/{z}/{x}/{y}.png" } }, isPending: false, error: null } as never);
  vi.mocked(hooks.useFences).mockReturnValue({ data: { items: [], total: 0 }, isPending: false, error: null } as never);
  vi.mocked(hooks.useDevices).mockReturnValue({ data: { items: [], total: 0 }, isPending: false, error: null } as never);
}

test("renderiza leyenda y crea el mapa", () => {
  mock(true);
  renderWithProviders(<MapPage />);
  expect(screen.getByText("Dentro de geocerca")).toBeInTheDocument();
  expect(mapInstances.length).toBeGreaterThan(0);
});

test("mapa desactivado por configuración", () => {
  mock(false);
  renderWithProviders(<MapPage />);
  expect(screen.getByText(/map.enabled=false/)).toBeInTheDocument();
});
