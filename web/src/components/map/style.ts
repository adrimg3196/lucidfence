import type { StyleSpecification } from "maplibre-gl";

export function rasterStyle(tilesUrl: string): StyleSpecification {
  return {
    version: 8,
    sources: { osm: { type: "raster", tiles: [tilesUrl], tileSize: 256, attribution: "© OpenStreetMap contributors" } },
    layers: [{ id: "osm", type: "raster", source: "osm" }],
  };
}
