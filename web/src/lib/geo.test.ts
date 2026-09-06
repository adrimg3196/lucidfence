import { circleToPolygon, fencesToGeoJSON, devicesToGeoJSON } from "./geo";
import type { Device, Fence } from "@/api/hooks";

test("circleToPolygon devuelve un anillo cerrado de steps+1 puntos alrededor del centro", () => {
  const ring = circleToPolygon({ lat: 40.421, lng: -3.708 }, 500, 8);
  expect(ring).toHaveLength(9);
  expect(ring[0]).toEqual(ring[8]);
  for (const [lng, lat] of ring) {
    expect(Math.abs(lat - 40.421)).toBeLessThan(0.006);
    expect(Math.abs(lng + 3.708)).toBeLessThan(0.008);
  }
});

test("fencesToGeoJSON convierte círculos y polígonos", () => {
  const fences = [
    { id: "c", name: "C", kind: "circle", center: { lat: 1, lng: 2 }, radius_m: 100, rules: {}, actions: [] },
    { id: "p", name: "P", kind: "polygon", polygon: [{ lat: 0, lng: 0 }, { lat: 0, lng: 1 }, { lat: 1, lng: 1 }], rules: {}, actions: [] },
  ] as unknown as Fence[];
  const fc = fencesToGeoJSON(fences);
  expect(fc.features).toHaveLength(2);
  expect(fc.features[1].geometry).toEqual({ type: "Polygon", coordinates: [[[0, 0], [1, 0], [1, 1], [0, 0]]] });
});

test("fencesToGeoJSON omite geocercas poligonales con menos de 3 puntos", () => {
  const fences = [
    { id: "e", name: "E", kind: "polygon", polygon: [], rules: {}, actions: [] },
    { id: "d", name: "D", kind: "polygon", polygon: [{ lat: 0, lng: 0 }, { lat: 0, lng: 1 }], rules: {}, actions: [] },
  ] as unknown as Fence[];
  const fc = fencesToGeoJSON(fences);
  expect(fc.features).toHaveLength(0);
});

test("devicesToGeoJSON omite dispositivos sin ubicación", () => {
  const devices = [
    { id: "a", name: "A", fence_state: "inside", location: { point: { lat: 1, lng: 2 } } },
    { id: "b", name: "B", fence_state: "unknown", location: {} },
  ] as unknown as Device[];
  const fc = devicesToGeoJSON(devices);
  expect(fc.features).toHaveLength(1);
  expect(fc.features[0].properties).toEqual({ id: "a", name: "A", fence_state: "inside" });
});
