import { SquaresFour, MapTrifold, DeviceMobile, Polygon, type Icon } from "@phosphor-icons/react";
import type { Key } from "@/lib/i18n";

export const navItems: { to: string; key: Key; icon: Icon }[] = [
  { to: "/", key: "nav.overview", icon: SquaresFour },
  { to: "/map", key: "nav.map", icon: MapTrifold },
  { to: "/devices", key: "nav.devices", icon: DeviceMobile },
  { to: "/fences", key: "nav.fences", icon: Polygon },
];
