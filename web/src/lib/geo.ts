/// <reference types="geojson" />
import type { Device, Fence } from "@/api/hooks";

const EARTH_M = 6_371_000;

export function circleToPolygon(center: { lat: number; lng: number }, radiusM: number, steps = 64): [number, number][] {
  const ring: [number, number][] = [];
  const dLat = (radiusM / EARTH_M) * (180 / Math.PI);
  const dLng = dLat / Math.cos((center.lat * Math.PI) / 180);
  for (let i = 0; i < steps; i++) {
    const a = (i / steps) * 2 * Math.PI;
    ring.push([center.lng + dLng * Math.cos(a), center.lat + dLat * Math.sin(a)]);
  }
  ring.push(ring[0]);
  return ring;
}

export function fencesToGeoJSON(fences: Fence[]): GeoJSON.FeatureCollection {
  return {
    type: "FeatureCollection",
    features: fences
      .filter((f) => f.kind !== "polygon" || (f.polygon?.length ?? 0) >= 3)
      .map((f) => {
        const ring =
          f.kind === "circle" && f.center
            ? circleToPolygon(f.center, f.radius_m ?? 0)
            : [...(f.polygon ?? []).map((p) => [p.lng, p.lat] as [number, number]), ...(f.polygon?.length ? [[f.polygon[0].lng, f.polygon[0].lat] as [number, number]] : [])];
        return { type: "Feature", properties: { id: f.id, name: f.name, kind: f.kind }, geometry: { type: "Polygon", coordinates: [ring] } };
      }),
  };
}

export function devicesToGeoJSON(devices: Device[]): GeoJSON.FeatureCollection {
  return {
    type: "FeatureCollection",
    features: devices
      .filter((d) => d.location?.point)
      .map((d) => ({
        type: "Feature",
        properties: { id: d.id, name: d.name, fence_state: d.fence_state },
        geometry: { type: "Point", coordinates: [d.location.point!.lng, d.location.point!.lat] },
      })),
  };
}

// M1-R27 (C14): el popup del mapa pasaba el nombre del dispositivo a
// Popup.setHTML sin escapar; hoy solo lo alimenta la seed de la demo, pero en
// M2 el primer conector real trae nombres del UEM sin sanear (sumidero XSS
// clásico). Se construye el nodo con textContent, que nunca interpreta su
// contenido como marcado, y se pasa a Popup.setDOMContent en vez de setHTML.
export function devicePopupContent(name: string, fenceState: string): HTMLElement {
  const el = document.createElement("div");
  const strong = document.createElement("strong");
  strong.textContent = name;
  el.append(strong, document.createElement("br"), document.createTextNode(fenceState));
  return el;
}
