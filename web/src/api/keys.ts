import { useQueryClient } from "@tanstack/react-query";

// Claves de TanStack Query de toda la aplicación. Viven aparte de hooks.ts
// para que hooks.ts pueda reexportar hooks.m2.ts sin ciclo de imports: los dos
// módulos de hooks importan de aquí y nadie importa de ellos hacia atrás.
export const keys = {
  health: ["health"] as const,
  authStatus: ["auth", "status"] as const,
  me: ["auth", "me"] as const,
  devices: (p?: { state?: string; q?: string; severity?: string }) => ["devices", p ?? {}] as const,
  device: (id: string) => ["devices", id] as const,
  trail: (id: string, limit: number) => ["devices", id, "trail", limit] as const,
  fences: ["fences"] as const,
  fence: (id: string) => ["fences", id] as const,
  engine: ["engine", "status"] as const,
  events: (limit: number) => ["events", limit] as const,
  actions: (limit: number) => ["actions", limit] as const,
  policies: ["policies"] as const,
  policy: (id: string) => ["policies", id] as const,
  // Catálogos con raíz propia: colgarlos de ["policies", ...] chocaría con
  // keys.policy("templates") y los refrescaría con cada política guardada.
  policyTemplates: ["policy-templates"] as const,
  policyFields: ["policy-fields"] as const,
  incidents: (p?: { status?: string; device_id?: string }) => ["incidents", p ?? {}] as const,
  incident: (id: string) => ["incidents", id] as const,
  incidentAnalytics: ["incident-analytics"] as const,
  alerts: ["alerts"] as const,
  alert: (id: string) => ["alerts", id] as const,
  playbooks: ["playbooks"] as const,
  playbook: (id: string) => ["playbooks", id] as const,
  handoffs: (status?: string) => ["handoffs", status ?? ""] as const,
  settings: ["settings"] as const,
  eventsPage: (cursor?: string) => ["events", "page", cursor ?? ""] as const,
  actionsPage: (cursor?: string) => ["actions", "page", cursor ?? ""] as const,
};

export function useInvalidate(...keysToInvalidate: readonly (readonly unknown[])[]) {
  const qc = useQueryClient();
  return () => Promise.all(keysToInvalidate.map((k) => qc.invalidateQueries({ queryKey: k })));
}
