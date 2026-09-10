import {
  SquaresFour,
  MapTrifold,
  DeviceMobile,
  Polygon,
  Scales,
  Warning,
  Bell,
  Lightning,
  Handshake,
  ClockCounterClockwise,
  ListChecks,
  Gear,
  type Icon,
} from "@phosphor-icons/react";
import type { Key } from "@/lib/i18n";
import { can } from "@/lib/permissions";

export type NavItem = { to: string; key: Key; icon: Icon; cap?: string };

// Cada entrada declara la capacidad que la hace visible; el servidor vuelve a
// exigirla en cada ruta (permissions.ts). Playbooks y la bandeja se recortan
// con la capacidad de actuar, no con la de leer: son superficies para decidir,
// y abrirle una bandeja de aprobaciones a quien no puede aprobar es ruido.
export const navItems: NavItem[] = [
  { to: "/", key: "nav.overview", icon: SquaresFour },
  { to: "/map", key: "nav.map", icon: MapTrifold },
  { to: "/devices", key: "nav.devices", icon: DeviceMobile },
  { to: "/fences", key: "nav.fences", icon: Polygon },
  { to: "/policies", key: "nav.policies", icon: Scales, cap: "policy:read" },
  { to: "/incidents", key: "nav.incidents", icon: Warning, cap: "incident:read" },
  { to: "/alerts", key: "nav.alerts", icon: Bell, cap: "incident:read" },
  { to: "/playbooks", key: "nav.playbooks", icon: Lightning, cap: "playbook:write" },
  { to: "/handoffs", key: "nav.handoffs", icon: Handshake, cap: "handoff:approve" },
  { to: "/events", key: "nav.events", icon: ClockCounterClockwise, cap: "device:read" },
  { to: "/actions", key: "nav.actions", icon: ListChecks, cap: "device:read" },
  { to: "/settings", key: "nav.settings", icon: Gear, cap: "engine:config" },
];

export function visibleNav(capabilities: readonly string[] | undefined): NavItem[] {
  return navItems.filter((i) => !i.cap || can(capabilities, i.cap));
}
