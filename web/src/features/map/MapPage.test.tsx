import { screen, waitFor } from "@testing-library/react";
import { renderWithProviders } from "@/test/render";
import { MapPage } from "./MapPage";
import * as hooks from "@/api/hooks";

type MockMapInstance = { sources: Record<string, GeoJSON.FeatureCollection | undefined> };
const mapInstances: MockMapInstance[] = [];
vi.mock("maplibre-gl", () => {
  class Map {
    handlers: Record<string, (...args: unknown[]) => void> = {};
    sources: Record<string, GeoJSON.FeatureCollection | undefined> = {};
    constructor(public opts: unknown) { mapInstances.push(this); }
    on(ev: string, a: unknown, b?: unknown) {
      const fn = (typeof a === "function" ? a : b) as () => void;
      this.handlers[ev] = fn;
      if (ev === "load") queueMicrotask(fn);
    }
    addSource(id: string, spec: { data: GeoJSON.FeatureCollection }) { this.sources[id] = spec.data; }
    getSource(id: string) { return { setData: (d: GeoJSON.FeatureCollection) => { this.sources[id] = d; } }; }
    addLayer() {} addControl() {} fitBounds() {} remove() {} getCanvas() { return { style: {} }; }
  }
  class Popup { setLngLat() { return this; } setHTML() { return this; } addTo() { return this; } }
  class NavigationControl {}
  class LngLatBounds { extend() { return this; } isEmpty() { return false; } }
  return { default: { Map, Popup, NavigationControl, LngLatBounds }, Map, Popup, NavigationControl, LngLatBounds };
});
vi.mock("@/api/hooks", async (orig) => ({ ...(await orig<typeof hooks>()), useHealth: vi.fn(), useFences: vi.fn(), useDevices: vi.fn() }));

beforeEach(() => {
  mapInstances.length = 0;
});

function mock(mapEnabled: boolean, tilesUrl = "https://t/{z}/{x}/{y}.png") {
  vi.mocked(hooks.useHealth).mockReturnValue({ data: { map: { enabled: mapEnabled, tiles_url: tilesUrl } }, isPending: false, error: null } as never);
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

test("mapa desactivado cuando tiles_url está vacío", () => {
  mock(true, "");
  renderWithProviders(<MapPage />);
  expect(screen.getByText(/map.enabled=false/)).toBeInTheDocument();
  expect(mapInstances.length).toBe(0);
});

test("siembra las fuentes fences y devices con los datos vigentes tras el load asíncrono", async () => {
  mock(true);
  vi.mocked(hooks.useFences).mockReturnValue({
    data: { items: [{ id: "f1", name: "F1", kind: "circle", center: { lat: 40.42, lng: -3.7 }, radius_m: 300, rules: {}, actions: [] }], total: 1 },
    isPending: false,
    error: null,
  } as never);
  vi.mocked(hooks.useDevices).mockReturnValue({
    data: { items: [{ id: "d1", name: "D1", fence_state: "inside", location: { point: { lat: 40.42, lng: -3.7 } } }], total: 1 },
    isPending: false,
    error: null,
  } as never);
  renderWithProviders(<MapPage />);
  await waitFor(() => {
    const [m] = mapInstances;
    expect(m.sources.fences?.features).toHaveLength(1);
    expect(m.sources.devices?.features).toHaveLength(1);
  });
});
