import { useEffect, useRef } from "react";
import * as maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import type { Device, Fence } from "@/api/hooks";
import { devicesToGeoJSON, devicePopupContent, fencesToGeoJSON } from "@/lib/geo";
import { rasterStyle } from "./style";

const colors = { inside: "#346538", outside: "#956400", unknown: "#5E635C" };

export function FleetMap({ fences, devices, tilesUrl, onDeviceClick }: { fences: Fence[]; devices: Device[]; tilesUrl: string; onDeviceClick?: (id: string) => void }) {
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const loaded = useRef(false);
  const fitted = useRef(false);
  const latest = useRef({ fences, devices });
  const sync = useRef<() => void>(() => {});

  useEffect(() => {
    latest.current = { fences, devices };
  });

  useEffect(() => {
    if (!container.current || map.current) return;
    const m = new maplibregl.Map({ container: container.current, style: rasterStyle(tilesUrl), center: [-3.708, 40.421], zoom: 12, attributionControl: {} });
    m.addControl(new maplibregl.NavigationControl(), "top-right");
    sync.current = () => {
      const fSrc = m.getSource("fences") as maplibregl.GeoJSONSource | undefined;
      const dSrc = m.getSource("devices") as maplibregl.GeoJSONSource | undefined;
      fSrc?.setData(fencesToGeoJSON(latest.current.fences));
      dSrc?.setData(devicesToGeoJSON(latest.current.devices));
      if (!fitted.current && latest.current.devices.some((d) => d.location?.point)) {
        const b = new maplibregl.LngLatBounds();
        for (const d of latest.current.devices) if (d.location?.point) b.extend([d.location.point.lng, d.location.point.lat]);
        m.fitBounds(b, { padding: 60, maxZoom: 14, duration: 0 });
        fitted.current = true;
      }
    };
    m.on("load", () => {
      m.addSource("fences", { type: "geojson", data: fencesToGeoJSON(latest.current.fences) });
      m.addSource("devices", { type: "geojson", data: devicesToGeoJSON(latest.current.devices) });
      m.addLayer({ id: "fences-fill", type: "fill", source: "fences", paint: { "fill-color": "#3E7A5E", "fill-opacity": 0.12 } });
      m.addLayer({ id: "fences-line", type: "line", source: "fences", paint: { "line-color": "#3E7A5E", "line-width": 2 } });
      m.addLayer({
        id: "devices",
        type: "circle",
        source: "devices",
        paint: {
          "circle-radius": 7,
          "circle-stroke-width": 2,
          "circle-stroke-color": "#FFFFFF",
          "circle-color": ["match", ["get", "fence_state"], "inside", colors.inside, "outside", colors.outside, colors.unknown],
        },
      });
      m.on("click", "devices", (e) => {
        const f = e.features?.[0];
        if (!f) return;
        const p = f.properties as { id: string; name: string; fence_state: string };
        // M1-R27 (C14): setDOMContent con un nodo construido vía textContent
        // en vez de setHTML con una plantilla interpolada (sumidero XSS).
        new maplibregl.Popup().setLngLat(e.lngLat).setDOMContent(devicePopupContent(p.name, p.fence_state)).addTo(m);
        onDeviceClick?.(p.id);
      });
      m.on("mouseenter", "devices", () => (m.getCanvas().style.cursor = "pointer"));
      m.on("mouseleave", "devices", () => (m.getCanvas().style.cursor = ""));
      sync.current();
      loaded.current = true;
    });
    map.current = m;
    return () => {
      m.remove();
      map.current = null;
      loaded.current = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!loaded.current) return;
    sync.current();
  }, [fences, devices]);

  return <div ref={container} className="h-full min-h-[520px] w-full rounded-[var(--radius-ui)] border border-border" />;
}
